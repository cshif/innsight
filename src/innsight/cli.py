"""CLI entry point for innsight command."""

import argparse
from typing import List, Optional
import sys
import os
import pandas as pd

# Import modules from the same package
from .nominatim_client import NominatimClient, NominatimError
from .overpass_client import fetch_overpass
from .ors_client import get_isochrones_by_minutes
from .tier import assign_tier
from .parser import parse_query, extract_location_from_query, ParseError


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='innsight',
        description='innsight <query>',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('query', help='完整中文需求句')
    
    if argv is None:
        argv = sys.argv[1:]
    
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code or 0
    
    # Environment variable validation
    api_endpoint = os.getenv("API_ENDPOINT")
    if not api_endpoint:
        print("API_ENDPOINT environment variable not set", file=sys.stderr)
        return 1
    
    try:
        # Parse query
        parsed_query = parse_query(args.query)
        
        # Extract location from query
        location = extract_location_from_query(parsed_query, args.query)
        poi = parsed_query.get('poi', '')
        
        # Validate that we have either place or POI
        if not location and not poi:
            print("無法判斷地名或主行程", file=sys.stderr)
            return 1
        
        # Use POI if location is empty
        search_term = location if location else poi
        
        # Geocode
        nominatim_client = NominatimClient(api_endpoint)
        geocode_results = nominatim_client.geocode(search_term)
        
        if not geocode_results:
            print("找不到地點", file=sys.stderr)
            return 1
        
        lat, lon = geocode_results[0]
        
        # Fetch accommodations
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
        
        # Process accommodations
        rows = []
        for el in elements:
            lat_el = el.get("lat") or el.get("center", {}).get("lat")
            lon_el = el.get("lon") or el.get("center", {}).get("lon")

            row = {
                "osmid": el["id"],
                "osmtype": el["type"],
                "lat": lat_el,
                "lon": lon_el,
                "tourism": el.get("tags", {}).get("tourism"),
                "name": el.get("tags", {}).get("name"),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        
        if len(df) == 0:
            print("找到 0 筆住宿")
            return 0
        
        # Get isochrones
        coord = (float(lon), float(lat))
        intervals = [15, 30, 60]
        
        try:
            isochrones_list = get_isochrones_by_minutes(coord, intervals)
        except Exception as e:
            # Check if we can use cached data
            if "cache" in str(e).lower():
                print("使用快取資料", file=sys.stderr)
                # Try to get cached data
                try:
                    isochrones_list = get_isochrones_by_minutes(coord, intervals)
                except:
                    print("找到 0 筆住宿")
                    return 0
            else:
                print("找到 0 筆住宿")
                return 0
        
        # Assign tiers
        if isochrones_list and all(isochrones_list):
            gdf = assign_tier(df, isochrones_list)
        else:
            # If no isochrones, assign tier 0 to all
            gdf = df.copy()
            gdf['tier'] = 0
        
        # Output results
        accommodation_count = len(gdf)
        print(f"找到 {accommodation_count} 筆住宿")
        
        # Output table with name and tier
        if accommodation_count > 0:
            # Simple table format
            for _, row in gdf.iterrows():
                name = row.get('name', 'Unknown')
                tier = row.get('tier', 0)
                print(f"name: {name}, tier: {tier}")
        
        return 0
        
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 1
    except NominatimError as e:
        print("找不到地點", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())