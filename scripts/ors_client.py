import os
import requests
from dotenv import load_dotenv
from typing import List

load_dotenv()


def get_isochrones(locations: List[List[float]], max_range: List[int]) -> None:
    resp = requests.post(
        url = f"{os.getenv("ORS_URL")}/isochrones/driving-car",
        json = {
            "locations": locations,
            "range": max_range,
        },
        headers={
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": os.getenv("ORS_API_KEY"),
        },
    )
    print(resp.json()["features"][0]["geometry"])
