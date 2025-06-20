import os

from scripts.nominatim_client import NominatimClient, NominatimError
from scripts.overpass_client import fetch_overpass


def main(argv: list[str] | None = None) -> None:  # noqa: D401
    import argparse

    parser = argparse.ArgumentParser(description="Query a Nominatim instance")
    parser.add_argument("--place", required=True, help="Query string to search for")
    # parser.add_argument("--radius", default=1000)

    args = parser.parse_args(argv)

    api_endpoint = os.getenv("API_ENDPOINT")
    if not api_endpoint:
        parser.error("API_ENDPOINT environment variable not set")

    nominatim_client = NominatimClient(api_endpoint)
    try:
        data = nominatim_client.geocode(args.place)
        if not data:
            parser.error(f"No results found for {args.place}")
        lat = float(data[0][0])
        lon = float(data[0][1])
        query = f"""
            [out:json][timeout:25];

            // 1. 找 100 公尺內水族館
            nwr(around:100,{lat},{lon})["tourism"="aquarium"]->.aquarium;

            // 2. 直接查 admin_level=7 area（可根據需要調整 admin_level）
            is_in({lat},{lon})->.areas;
            area.areas[boundary="administrative"][admin_level=7]->.mainArea;

            // 3. 取這個 area 對應的 relation
            rel(pivot.mainArea)->.mainRel;

            // 4. 找主行政區的邊界 ways
            way(r.mainRel)->.borderWays;

            // 5. 找和主行政區接壤的其他 admin_level=7 行政區（即鄰居）
            rel(bw.borderWays)[boundary="administrative"][admin_level=7]->.neighborRels;

            // 6. relation 轉 area id
            rel.neighborRels->.tmpRels;
            (.tmpRels; map_to_area;)->.neighborAreas;

            // 7. 查所有鄰近 area 內的旅宿
            nwr(area.neighborAreas)[tourism~"hotel|guest_house|hostel|motel|apartment|camp_site|caravan_site"];
            out center;
            """
        elements = fetch_overpass(query)
    except NominatimError as exc:
        parser.error(str(exc))
    else:
        print(data, f"共抓到 {len(elements)} 筆")


if __name__ == "__main__":  # pragma: no cover
    main()