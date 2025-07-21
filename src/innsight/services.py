"""Service layer for business logic."""

from typing import List, Tuple, Optional
import pandas as pd
import geopandas as gpd

from .config import AppConfig
from .nominatim_client import NominatimClient
from .overpass_client import fetch_overpass
from .ors_client import get_isochrones_by_minutes
from .tier import assign_tier
from .parser import parse_query, extract_location_from_query
from .exceptions import GeocodeError, ParseError


class QueryService:
    """Service for parsing and extracting information from user queries."""
    
    def extract_search_term(self, query: str) -> str:
        """Extract and validate search term from query."""
        parsed_query = parse_query(query)
        location = extract_location_from_query(parsed_query, query)
        poi = parsed_query.get('poi', '')
        
        if not location and not poi:
            raise ParseError("無法判斷地名或主行程")
        
        return location if location else poi


class GeocodeService:
    """Service for geocoding locations."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None
    
    @property
    def client(self) -> NominatimClient:
        """Lazy initialization of NominatimClient."""
        if self._client is None:
            self._client = NominatimClient(
                api_endpoint=self.config.api_endpoint,
                user_agent=self.config.nominatim_user_agent,
                timeout=self.config.nominatim_timeout
            )
        return self._client
    
    def geocode_location(self, search_term: str) -> Tuple[float, float]:
        """Geocode search term and return coordinates."""
        geocode_results = self.client.geocode(search_term)
        
        if not geocode_results:
            raise GeocodeError("找不到地點")
        
        return geocode_results[0]


class AccommodationService:
    """Service for finding and processing accommodations."""
    
    def build_overpass_query(self, lat: float, lon: float) -> str:
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
    
    def fetch_accommodations(self, lat: float, lon: float) -> pd.DataFrame:
        """Fetch accommodations from Overpass API."""
        query = self.build_overpass_query(lat, lon)
        elements = fetch_overpass(query)
        return self.process_accommodation_elements(elements)
    
    def process_accommodation_elements(self, elements: List[dict]) -> pd.DataFrame:
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


class IsochroneService:
    """Service for isochrone calculation and caching."""
    
    def __init__(self, config: AppConfig):
        self.config = config
    
    def get_isochrones_with_fallback(self, coord: Tuple[float, float], intervals: List[int]) -> Optional[List]:
        """Get isochrones with fallback handling."""
        try:
            return get_isochrones_by_minutes(coord, intervals)
        except Exception as e:
            # Check if we can use cached data
            if "cache" in str(e).lower():
                import sys
                print("使用快取資料", file=sys.stderr)
                try:
                    return get_isochrones_by_minutes(coord, intervals)
                except:
                    return None
            return None


class TierService:
    """Service for tier assignment."""
    
    def assign_tiers(self, df: pd.DataFrame, isochrones_list: Optional[List]) -> gpd.GeoDataFrame:
        """Assign tiers to accommodations based on isochrones."""
        if isochrones_list and all(isochrones_list):
            return assign_tier(df, isochrones_list)
        else:
            # If no isochrones, assign tier 0 to all
            gdf = df.copy()
            gdf['tier'] = 0
            return gdf


class AccommodationSearchService:
    """High-level service that coordinates the accommodation search process."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.query_service = QueryService()
        self.geocode_service = GeocodeService(config)
        self.accommodation_service = AccommodationService()
        self.isochrone_service = IsochroneService(config)
        self.tier_service = TierService()
    
    def search_accommodations(self, query: str) -> gpd.GeoDataFrame:
        """Search for accommodations based on user query."""
        # Extract search term
        search_term = self.query_service.extract_search_term(query)
        
        # Geocode location
        lat, lon = self.geocode_service.geocode_location(search_term)
        
        # Fetch accommodations
        df = self.accommodation_service.fetch_accommodations(lat, lon)
        
        if len(df) == 0:
            return gpd.GeoDataFrame()
        
        # Get isochrones
        coord = (float(lon), float(lat))
        intervals = [15, 30, 60]
        isochrones_list = self.isochrone_service.get_isochrones_with_fallback(coord, intervals)
        
        if isochrones_list is None:
            return gpd.GeoDataFrame()
        
        # Assign tiers
        return self.tier_service.assign_tiers(df, isochrones_list)