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
from .exceptions import GeocodeError, ParseError, NoAccommodationError
from .rating_service import RatingService


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

            tags = el.get("tags", {})
            row = {
                "osmid": el["id"],
                "osmtype": el["type"],
                "lat": lat_el,
                "lon": lon_el,
                "tourism": tags.get("tourism"),
                "name": tags.get("name"),
                "rating": self._extract_rating(tags),
                "tags": self._extract_amenity_tags(tags),
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
    
    def _extract_rating(self, tags: dict) -> Optional[float]:
        """Extract rating from OSM tags."""
        # Try different rating fields
        rating_fields = ['rating', 'stars', 'quality']
        for field in rating_fields:
            if field in tags:
                try:
                    return float(tags[field])
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_amenity_tags(self, tags: dict) -> dict:
        """Extract amenity tags for scoring."""
        # Define extraction rules for each amenity
        extraction_rules = {
            'parking': {
                'direct_keys': ['parking'],
                'conditional_keys': [('parking:fee', 'no', 'yes')],  # If parking:fee=no, then parking=yes
                'indicator_keys': []
            },
            'wheelchair': {
                'direct_keys': ['wheelchair'],
                'conditional_keys': [],
                'indicator_keys': []
            },
            'kids': {
                'direct_keys': [],
                'conditional_keys': [],
                'indicator_keys': ['family_friendly', 'kids', 'children']
            },
            'pet': {
                'direct_keys': [],
                'conditional_keys': [],
                'indicator_keys': ['pets', 'pets_allowed', 'dogs']
            }
        }
        
        amenity_tags = {}
        
        for amenity, rules in extraction_rules.items():
            value = None
            
            # Check direct keys first
            for key in rules['direct_keys']:
                if key in tags:
                    value = tags[key]
                    break
            
            # Check conditional keys
            if value is None:
                for key, condition_value, result_value in rules['conditional_keys']:
                    if key in tags and tags[key] == condition_value:
                        value = result_value
                        break
            
            # Check indicator keys (return 'yes' if any match)
            if value is None:
                for key in rules['indicator_keys']:
                    if key in tags and tags[key] in ['yes', 'true']:
                        value = 'yes'
                        break
            
            amenity_tags[amenity] = value
            
        return amenity_tags


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
        self.rating_service = RatingService(config)
    
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
        gdf = self.tier_service.assign_tiers(df, isochrones_list)
        
        # Calculate scores
        gdf['score'] = gdf.apply(self.rating_service.score, axis=1)
        
        return gdf
    
    def filter_accommodations(self, accommodations_df: gpd.GeoDataFrame, user_conditions: dict) -> gpd.GeoDataFrame:
        """Filter accommodations based on user conditions."""
        if not user_conditions:
            return accommodations_df
        
        filtered_df = accommodations_df.copy()
        
        for condition, required in user_conditions.items():
            if required:
                # Filter to keep only accommodations where the condition is 'yes'
                mask = filtered_df['tags'].apply(lambda tags: tags.get(condition) == 'yes')
                filtered_df = filtered_df[mask]
        
        # Ensure we return a GeoDataFrame if input was a GeoDataFrame
        if isinstance(accommodations_df, gpd.GeoDataFrame) and not isinstance(filtered_df, gpd.GeoDataFrame):
            filtered_df = gpd.GeoDataFrame(filtered_df)
        return filtered_df
    
    def sort_accommodations(self, accommodations_df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Sort accommodations by score in descending order."""
        if len(accommodations_df) == 0:
            return accommodations_df
        
        sorted_df = accommodations_df.sort_values('score', ascending=False).reset_index(drop=True)
        # Ensure we return a GeoDataFrame if input was a GeoDataFrame
        if isinstance(accommodations_df, gpd.GeoDataFrame) and not isinstance(sorted_df, gpd.GeoDataFrame):
            sorted_df = gpd.GeoDataFrame(sorted_df)
        return sorted_df
    
    def _validate_accommodation_data(self, df: gpd.GeoDataFrame) -> None:
        """Validate accommodation data types and ranges."""
        if len(df) == 0:
            return
            
        # Validate required columns exist
        required_columns = ['name', 'score', 'tier']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Use vectorized operations for better performance
        # Validate score ranges (more efficient than row iteration)
        if 'score' in df.columns:
            score_mask = df['score'].notna()
            if score_mask.any():
                invalid_scores = ((df['score'] < 0) | (df['score'] > 100)) & score_mask
                if invalid_scores.any():
                    first_invalid = df[invalid_scores].index[0]
                    raise ValueError(f"Row {first_invalid}: score must be between 0-100, got {df.loc[first_invalid, 'score']}")
        
        # Validate tier ranges
        if 'tier' in df.columns:
            tier_mask = df['tier'].notna()
            if tier_mask.any():
                invalid_tiers = ((df['tier'] < 0) | (df['tier'] > 3)) & tier_mask
                if invalid_tiers.any():
                    first_invalid = df[invalid_tiers].index[0]
                    raise ValueError(f"Row {first_invalid}: tier must be between 0-3, got {df.loc[first_invalid, 'tier']}")
        
        # Only validate types for a sample if needed (for performance)
        if len(df) > 100:
            # Sample validation for large datasets
            sample_df = df.head(10)
        else:
            sample_df = df
            
        # Validate name types on sample
        for idx, row in sample_df.iterrows():
            if not isinstance(row.get('name'), (str, type(None))):
                raise TypeError(f"Row {idx}: name must be str or None, got {type(row.get('name'))}")
    
    def rank_accommodations(self, df: gpd.GeoDataFrame, filters: List[str] = None, top_n: int = None) -> gpd.GeoDataFrame:
        """
        Rank accommodations by applying filters and sorting by score.
        
        Args:
            df: DataFrame containing accommodation data
            filters: List of filter conditions (e.g., ["parking", "wheelchair"])
            top_n: Maximum number of results to return
            
        Returns:
            GeoDataFrame with filtered and sorted accommodations
            
        Raises:
            NoAccommodationError: When no accommodations match the criteria
        """
        if len(df) == 0:
            raise NoAccommodationError("No accommodations available to rank")
        
        # Validate input data
        self._validate_accommodation_data(df)
        
        result_df = df.copy()
        
        # Apply filters if provided
        if filters:
            user_conditions = {filter_name: True for filter_name in filters}
            result_df = self.filter_accommodations(result_df, user_conditions)
            
            if len(result_df) == 0:
                raise NoAccommodationError(f"No accommodations match the specified filters: {filters}")
        
        # Sort by score in descending order
        result_df = self.sort_accommodations(result_df)
        
        # Apply top_n limit if specified
        if top_n is not None and top_n > 0:
            result_df = result_df.head(top_n)
            # Ensure we return a GeoDataFrame if input was a GeoDataFrame
            if isinstance(df, gpd.GeoDataFrame) and not isinstance(result_df, gpd.GeoDataFrame):
                result_df = gpd.GeoDataFrame(result_df)
        
        return result_df