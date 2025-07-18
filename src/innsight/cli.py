"""CLI entry point for innsight command."""

import argparse
from typing import List, Optional, Tuple
import sys
import os
import pandas as pd
import geopandas as gpd

# Import modules from the same package
from .nominatim_client import NominatimClient
from .overpass_client import fetch_overpass
from .ors_client import get_isochrones_by_minutes
from .tier import assign_tier
from .parser import parse_query, extract_location_from_query
from .exceptions import GeocodeError, ParseError


def _setup_argument_parser() -> argparse.ArgumentParser:
    """Setup and return command line argument parser."""
    parser = argparse.ArgumentParser(
        prog='innsight',
        description='innsight <query>',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('query', help='完整中文需求句')
    return parser


def _validate_environment() -> str:
    """Validate required environment variables and return API endpoint."""
    api_endpoint = os.getenv("API_ENDPOINT")
    if not api_endpoint:
        raise ValueError("API_ENDPOINT environment variable not set")
    return api_endpoint


def _extract_search_term(query: str) -> str:
    """Extract and validate search term from query."""
    parsed_query = parse_query(query)
    location = extract_location_from_query(parsed_query, query)
    poi = parsed_query.get('poi', '')
    
    if not location and not poi:
        raise ParseError("無法判斷地名或主行程")
    
    return location if location else poi


def _geocode_location(api_endpoint: str, search_term: str) -> Tuple[float, float]:
    """Geocode search term and return coordinates."""
    nominatim_client = NominatimClient(api_endpoint)
    geocode_results = nominatim_client.geocode(search_term)
    
    if not geocode_results:
        raise GeocodeError("找不到地點")
    
    return geocode_results[0]


def _build_overpass_query(lat: float, lon: float) -> str:
    """Build Overpass API query for accommodations."""
    return f"""
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


def _process_accommodations(elements: List[dict]) -> pd.DataFrame:
    """Process accommodation elements into DataFrame."""
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
    
    return pd.DataFrame(rows)


def _get_isochrones_with_fallback(coord: Tuple[float, float], intervals: List[int]) -> List:
    """Get isochrones with fallback handling."""
    try:
        return get_isochrones_by_minutes(coord, intervals)
    except Exception as e:
        # Check if we can use cached data
        if "cache" in str(e).lower():
            print("使用快取資料", file=sys.stderr)
            try:
                return get_isochrones_by_minutes(coord, intervals)
            except:
                return None
        return None


def _assign_tiers(df: pd.DataFrame, isochrones_list: List) -> gpd.GeoDataFrame:
    """Assign tiers to accommodations based on isochrones."""
    if isochrones_list and all(isochrones_list):
        return assign_tier(df, isochrones_list)
    else:
        # If no isochrones, assign tier 0 to all
        gdf = df.copy()
        gdf['tier'] = 0
        return gdf


def _output_results(gdf: gpd.GeoDataFrame) -> None:
    """Output results to stdout."""
    accommodation_count = len(gdf)
    print(f"找到 {accommodation_count} 筆住宿")
    
    if accommodation_count > 0:
        for _, row in gdf.iterrows():
            name = row.get('name', 'Unknown')
            tier = row.get('tier', 0)
            print(f"name: {name}, tier: {tier}")


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    # Setup argument parser
    parser = _setup_argument_parser()
    
    if argv is None:
        argv = sys.argv[1:]
    
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code or 0
    
    try:
        # Validate environment
        api_endpoint = _validate_environment()
        
        # Extract search term from query
        search_term = _extract_search_term(args.query)
        
        # Geocode location
        lat, lon = _geocode_location(api_endpoint, search_term)
        
        # Fetch accommodations
        overpass_query = _build_overpass_query(lat, lon)
        elements = fetch_overpass(overpass_query)
        
        # Process accommodations
        df = _process_accommodations(elements)
        
        if len(df) == 0:
            print("找到 0 筆住宿")
            return 0
        
        # Get isochrones
        coord = (float(lon), float(lat))
        intervals = [15, 30, 60]
        isochrones_list = _get_isochrones_with_fallback(coord, intervals)
        
        if isochrones_list is None:
            print("找到 0 筆住宿")
            return 0
        
        # Assign tiers
        gdf = _assign_tiers(df, isochrones_list)
        
        # Output results
        _output_results(gdf)
        
        return 0
        
    except ValueError as e:
        # Handle environment validation errors
        print(str(e), file=sys.stderr)
        return 1
    except ParseError as e:
        print(str(e), file=sys.stderr)
        return 1
    except GeocodeError as e:
        print("找不到地點", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())