import os, requests, logging
from json import JSONDecodeError
from requests.exceptions import Timeout, ConnectionError, HTTPError
from dotenv import load_dotenv
from typing import List, Tuple, Dict, Any

load_dotenv()


def get_isochrones(
        profile: str,
        locations: List[Tuple[float, float]],
        max_range: List[int]
) -> Dict[str, Any]:
    try:
        resp = requests.post(
            url=f"{os.getenv("ORS_URL")}/isochrones/{profile}",
            json={
                "locations": locations,
                "range": max_range,
            },
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": os.getenv("ORS_API_KEY"),
            },
            timeout=(5, 30)
        )
        resp.raise_for_status()  # ② 先擋 4xx / 5xx
        data = resp.json()       # ③ 有可能丟 JSONDecodeError

        # ④ API：JSON 裡自帶 "error"
        # ORS 就算 HTTP 200，失敗時 body 會長這樣：
        # {"error": {"code":2003,"message":"Parameter 'range' is out of limits"}}
        if isinstance(data, dict) and "error" in data:
            code = data["error"].get("code")
            msg = data["error"].get("message", repr(data["error"]))
            raise RuntimeError(f"ORS API error {code}: {msg}")

    # ① 連線
    except (Timeout, ConnectionError) as e:
        logging.error("network failure: %s", e)
        # raise RuntimeError("network unreachable")  # 直接把內建例外 re-raise 也行
        raise

    # ② HTTP 協定
    except HTTPError as e:
        status = e.response.status_code
        if status in (429,) or 500 <= status < 600:
            # 暫時性錯誤——這裡不重試，只標示給呼叫端
            raise HTTPError(f"upstream temporary failure ({status}), {e.response.text}")
        else:
            # 400/401/403/404/413… → 直接拋回讓呼叫端決定
            raise  # 保留原本 HTTPError

    # ③ 格式
    except JSONDecodeError as e:
        logging.error("invalid JSON from upstream: %s", e)
        raise JSONDecodeError(f"json decode error", e.doc, e.pos)

    else:
        return data