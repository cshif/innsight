from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import requests
from dotenv import load_dotenv

from .exceptions import GeocodeError

load_dotenv()


@dataclass
class NominatimClient:
    api_endpoint: str
    user_agent: str = ""
    timeout: int = 10

    def __post_init__(self) -> None:
        if not self.api_endpoint:
            raise ValueError("API endpoint must not be empty")

    def geocode(self, query: str) -> List[Tuple[float, float]]:
        url = f"{self.api_endpoint}/search"
        params = {"format": "json", "q": query}

        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            coords: List[tuple[float, float]] = []
            for item in data:
                try:
                    coords.append((float(item["lat"]), float(item["lon"])))
                except (KeyError, ValueError):
                    continue
            return coords
        except requests.exceptions.RequestException as exc:
            raise GeocodeError(f"Network error: {exc}") from exc
        except ValueError as exc:
            raise GeocodeError("Invalid JSON received from API") from exc
