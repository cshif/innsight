import os, requests, logging, time
from functools import wraps
from json import JSONDecodeError
from requests.exceptions import Timeout, ConnectionError, HTTPError
from dotenv import load_dotenv
from typing import Tuple, List, Dict
from shapely.geometry import Polygon

load_dotenv()


def retry_on_network_error(max_attempts=3, delay=1, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (Timeout, ConnectionError, HTTPError, JSONDecodeError) as e:
                    # Handle specific error transformations
                    if isinstance(e, HTTPError):
                        status = e.response.status_code
                        if not (status == 429 or 500 <= status < 600):
                            raise
                        # Transform retryable HTTP errors for final attempt
                        if attempt == max_attempts - 1:
                            new_error = HTTPError(f"Upstream temporary failure ({status}): {e.response.text}")
                            new_error.response = e.response
                            raise new_error
                    elif isinstance(e, JSONDecodeError):
                        # Transform JSONDecodeError for final attempt
                        if attempt == max_attempts - 1:
                            raise ConnectionError(f"Invalid response format: {str(e)}")
                    
                    if attempt == max_attempts - 1:
                        logging.error("Max retry attempts (%d) reached for %s", max_attempts, func.__name__)
                        raise
                    
                    logging.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %ds...",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        str(e),
                        current_delay
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None

        return wrapper
    return decorator


# 自定義快取儲存
_fallback_cache: Dict[Tuple, Tuple[List[Polygon], float]] = {}  # (key, (result, timestamp))


def fallback_cache(maxsize=128, ttl_hours=24):
    """
    快取裝飾器，失敗時回退到過期快取
    - maxsize: 最大快取項目數
    - ttl_hours: 快取有效期（小時）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 建立快取鍵
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            # 檢查是否有有效的快取
            if key in _fallback_cache:
                cached_result, cached_time = _fallback_cache[key]
                age_hours = (current_time - cached_time) / 3600
                
                # 如果快取仍在有效期內，直接返回
                if age_hours <= ttl_hours:
                    return cached_result
            
            try:
                # 嘗試執行函數
                result = func(*args, **kwargs)
                # 成功時更新快取
                _fallback_cache[key] = (result, current_time)
                
                # 清理過期快取項目
                if len(_fallback_cache) > maxsize:
                    expired_keys = [
                        k for k, (_, timestamp) in _fallback_cache.items()
                        if current_time - timestamp > ttl_hours * 3600
                    ]
                    for expired_key in expired_keys:
                        _fallback_cache.pop(expired_key, None)
                    
                    # 如果還是太多，移除最舊的項目
                    if len(_fallback_cache) > maxsize:
                        oldest_key = min(_fallback_cache.keys(), 
                                       key=lambda k: _fallback_cache[k][1])
                        _fallback_cache.pop(oldest_key, None)
                
                return result
                
            except Exception as e:
                # 失敗時檢查是否有快取可回退（包括過期的快取）
                if key in _fallback_cache:
                    cached_result, cached_time = _fallback_cache[key]
                    age_hours = (current_time - cached_time) / 3600
                    logging.warning(
                        "API call failed, falling back to cached result (%.1f hours old): %s",
                        age_hours, str(e)
                    )
                    return cached_result
                else:
                    # 沒有快取時重新拋出例外
                    raise
        
        # 新增清理快取的方法
        wrapper.cache_clear = lambda: _fallback_cache.clear()
        wrapper.cache_info = lambda: {
            'size': len(_fallback_cache),
            'items': {k: (len(v[0]), v[1]) for k, v in _fallback_cache.items()}
        }
        
        return wrapper
    return decorator


@fallback_cache(maxsize=128, ttl_hours=24)
@retry_on_network_error(max_attempts=3, delay=1, backoff=2)
def get_isochrones(
        profile: str,
        locations: Tuple[Tuple[float, float], ...],
        max_range: Tuple[int, ...]
) -> List[Polygon]:
    resp = requests.post(
        url=f"{os.getenv('ORS_URL')}/isochrones/{profile}",
        json={"locations": locations, "range": max_range},
        headers={
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": os.getenv("ORS_API_KEY"),
        },
        timeout=(5, 30)
    )
    resp.raise_for_status()
    data = resp.json()

    # 檢查 API 錯誤
    if isinstance(data, dict) and "error" in data:
        code = data["error"].get("code")
        msg = data["error"].get("message", repr(data["error"]))
        raise RuntimeError(f"ORS API error {code}: {msg}")

    # 轉換 GeoJSON 特徵為 Shapely 多邊形
    polygons = []
    if "features" in data:
        for feature in data["features"]:
            if feature.get("geometry", {}).get("type") == "Polygon":
                coords = feature["geometry"]["coordinates"][0]  # 外環座標
                polygons.append(Polygon(coords))
    
    return polygons