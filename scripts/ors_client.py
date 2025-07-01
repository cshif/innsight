import os, requests, logging, time
from functools import lru_cache, wraps
from json import JSONDecodeError
from requests.exceptions import Timeout, ConnectionError, HTTPError
from dotenv import load_dotenv
from typing import Tuple, List
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


@lru_cache(maxsize=128)
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