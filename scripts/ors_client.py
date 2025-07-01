import os, requests, logging, time
from functools import lru_cache, wraps
from json import JSONDecodeError
from requests.exceptions import Timeout, ConnectionError, HTTPError
from dotenv import load_dotenv
from typing import Tuple, Dict, Any

load_dotenv()


def retry_on_network_error(max_attempts=3, delay=1, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except (Timeout, ConnectionError, HTTPError) as e:
                    attempt += 1
                    
                    # 如果是 HTTPError，只對 429 和 5xx 錯誤重試
                    if isinstance(e, HTTPError):
                        status = e.response.status_code
                        if not ((status == 429) or (500 <= status < 600)):
                            raise
                    
                    if attempt >= max_attempts:
                        logging.error("Max retry attempts (%d) reached for %s", max_attempts, func.__name__)
                        raise
                    
                    logging.warning("Attempt %d/%d failed for %s: %s. Retrying in %ds...", 
                                  attempt, max_attempts, func.__name__, str(e), current_delay)
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
            return None
        return wrapper
    return decorator


@lru_cache(maxsize=128)
@retry_on_network_error(max_attempts=3, delay=1, backoff=2)
def get_isochrones(
        profile: str,
        locations: Tuple[Tuple[float, float], ...],
        max_range: Tuple[int, ...]
) -> Dict[str, Any]:
    try:
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

        return data

    except HTTPError as e:
        # 只處理需要特殊邏輯的 HTTP 錯誤
        if e.response and e.response.status_code in (429,) or (500 <= e.response.status_code < 600):
            new_error = HTTPError(f"Upstream temporary failure ({e.response.status_code}): {e.response.text}")
            new_error.response = e.response
            raise new_error
        raise  # 其他 HTTP 錯誤直接拋出

    except JSONDecodeError as e:
        # 簡單處理：記錄並重新拋出為可重試的錯誤
        logging.error("Invalid JSON from upstream: %s", e)
        # 讓 retry decorator 將其視為網絡錯誤
        raise ConnectionError(f"Invalid response format: {str(e)}")

    # 其他異常（Timeout, ConnectionError）讓 retry decorator 自動處理