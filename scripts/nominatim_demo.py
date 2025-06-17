from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()


class NominatimError(Exception):
    """"""


@dataclass
class NominatimClient:
    api_endpoint: str
    user_agent: str = ""
    timeout: int = 10

    def __post_init__(self) -> None:
        if not self.api_endpoint:
            raise ValueError("API endpoint must not be empty")

    def search(self, query: str) -> List[Tuple[float, float]]:
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
            raise NominatimError(f"Network error: {exc}") from exc
        except ValueError as exc:
            raise NominatimError("Invalid JSON received from API") from exc


def main(argv: list[str] | None = None) -> None:  # noqa: D401
    import argparse

    parser = argparse.ArgumentParser(description="Query a Nominatim instance")
    parser.add_argument("--place", required=True, help="Query string to search for")

    args = parser.parse_args(argv)

    api_endpoint = os.getenv("API_ENDPOINT")
    if not api_endpoint:
        parser.error("API_ENDPOINT environment variable not set")

    client = NominatimClient(api_endpoint)
    try:
        data = client.search(args.place)
    except NominatimError as exc:
        parser.error(str(exc))
    else:
        print(data)


if __name__ == "__main__":  # pragma: no cover
    main()
