"""Pipeline for FastAPI integration with Recommender."""

from typing import Dict, List, Any, Optional
import geopandas as gpd
import math
from shapely.geometry import Polygon

from .config import AppConfig
from .services.accommodation_search_service import AccommodationSearchService
from .services.geocode_service import GeocodeService
from .services.isochrone_service import IsochroneService
from .recommender import Recommender as RecommenderCore
from .exceptions import NetworkError, APIError, GeocodeError, IsochroneError, ServiceUnavailableError
from .parser import parse_query, extract_location_from_query


class Recommender:
    """Pipeline wrapper for Recommender to work with FastAPI."""
    
    def __init__(self):
        """Initialize the recommendation pipeline."""
        config = AppConfig.from_env()
        search_service = AccommodationSearchService(config)
        self.geocode_service = GeocodeService(config)
        self.isochrone_service = IsochroneService(config)
        self.config = config
        self.recommender = RecommenderCore(search_service)
    
    def run(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the recommendation pipeline.
        
        Args:
            query_data: Dictionary containing query parameters
                - query: str - Search query
                - filters: List[str] - Optional filters
                - top_n: int - Optional maximum results
        
        Returns:
            Dictionary with recommendation results
        """
        query = query_data.get("query", "")
        filters = query_data.get("filters")
        top_n = query_data.get("top_n", 20)
        weights = query_data.get("weights")
        
        if not query:
            # Return empty results for empty query instead of error
            return {
                "stats": {"tier_0": 0, "tier_1": 0, "tier_2": 0, "tier_3": 0},
                "top": [],
                "main_poi": self._build_main_poi_data("未知景點", None, None),
                "isochrone_geometry": [],
                "intervals": {"values": [], "unit": "minutes", "profile": "driving-car"}
            }
        
        # Parse query to extract main POI information (只解析一次)
        try:
            parsed_query = parse_query(query)
            location = extract_location_from_query(parsed_query, query)
            poi = parsed_query.get('poi', '')
            parsed_filters = parsed_query.get('filters', [])
            
            # Determine the main POI name and search term
            if poi:
                main_poi_name = poi
                search_term = poi
            elif location:
                # If no POI found, try to extract attraction from the original query
                main_poi_name = self._extract_attraction_from_query(query) or location
                search_term = main_poi_name
            else:
                main_poi_name = "未知景點"
                search_term = ""
            
            # Get detailed geocoding information for the main POI
            poi_details = None
            main_poi_lat = None
            main_poi_lon = None
            
            if search_term:
                poi_details = self.geocode_service.geocode_location_detailed(search_term)
                if poi_details:
                    main_poi_lat = poi_details.get("lat")
                    main_poi_lon = poi_details.get("lon")
                
        except Exception:
            # If parsing fails, use defaults
            main_poi_name = "未知景點"
            location = None
            poi_details = None
            main_poi_lat = None
            main_poi_lon = None
            parsed_filters = []
        
        # Merge parsed filters with API-provided filters
        merged_filters = self._merge_filters(parsed_filters, filters)
        
        # Search for accommodations
        try:
            # If we have main POI coordinates, use them for accommodation search
            if main_poi_lat is not None and main_poi_lon is not None:
                gdf = self.recommender.recommend_by_coordinates(
                    main_poi_lat, main_poi_lon, merged_filters, top_n, weights
                )
            else:
                # Fallback to original query-based search
                gdf = self.recommender.recommend(query, merged_filters, top_n, weights)
            
            # Convert to serializable format
            top_results = self._serialize_gdf(gdf)
            
            # Calculate tier statistics
            stats = self._calculate_tier_stats(gdf)
            
            # Get isochrone geometry data
            isochrone_geometry = []
            intervals_data = {"values": [], "unit": "minutes", "profile": "driving-car"}
            
            if main_poi_lat is not None and main_poi_lon is not None:
                coord = (float(main_poi_lon), float(main_poi_lat))
                intervals = self.config.default_isochrone_intervals
                isochrones_list = self.isochrone_service.get_isochrones_with_fallback(coord, intervals)
                
                if isochrones_list:
                    isochrone_geometry = self._convert_isochrones_to_geojson(isochrones_list)
                    intervals_data = {
                        "values": intervals,
                        "unit": "minutes", 
                        "profile": "driving-car"
                    }
            
            return {
                "stats": stats,
                "top": top_results,
                "main_poi": self._build_main_poi_data(main_poi_name, location, poi_details),
                "isochrone_geometry": isochrone_geometry,
                "intervals": intervals_data
            }
            
        except (NetworkError, APIError, GeocodeError, IsochroneError) as e:
            # External dependency failures should be re-raised as ServiceUnavailableError
            raise ServiceUnavailableError(f"External service unavailable: {str(e)}")
        except Exception as e:
            # Other exceptions return empty results
            return {
                "stats": {"tier_0": 0, "tier_1": 0, "tier_2": 0, "tier_3": 0},
                "top": [],
                "main_poi": self._build_main_poi_data(main_poi_name, location, poi_details),
                "isochrone_geometry": [],
                "intervals": {"values": [], "unit": "minutes", "profile": "driving-car"}
            }
    
    def _merge_filters(self, parsed_filters: List[str], api_filters: Optional[List[str]]) -> List[str]:
        """Merge parsed filters with API-provided filters and remove duplicates.
        
        Args:
            parsed_filters: Filters extracted from query text
            api_filters: Filters provided via API parameters
            
        Returns:
            List of unique filter strings
        """
        # Handle None values
        if parsed_filters is None:
            parsed_filters = []
        if api_filters is None:
            api_filters = []
            
        # Combine both lists and remove duplicates while preserving order
        combined = parsed_filters + api_filters
        unique_filters = []
        seen = set()
        
        for filter_item in combined:
            if filter_item not in seen:
                unique_filters.append(filter_item)
                seen.add(filter_item)
                
        return unique_filters
    
    def _serialize_gdf(self, gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
        """Convert GeoDataFrame to JSON-serializable format."""
        if len(gdf) == 0:
            return []
        
        def safe_float(value):
            """Safely convert value to float, handling NaN cases."""
            if value is None:
                return None
            try:
                f_val = float(value)
                return None if math.isnan(f_val) or math.isinf(f_val) else f_val
            except (ValueError, TypeError):
                return None
        
        def safe_int(value):
            """Safely convert value to int, handling NaN cases."""
            if value is None:
                return 0
            try:
                f_val = float(value)
                if math.isnan(f_val) or math.isinf(f_val):
                    return 0
                return int(f_val)
            except (ValueError, TypeError):
                return 0

        return [
            {
                "name": row.get("name", "Unknown"),
                "score": safe_float(row.get("score")) or 0.0,
                "tier": safe_int(row.get("tier")),
                "lat": safe_float(row.get("lat")),
                "lon": safe_float(row.get("lon")),
                "osmid": str(row.get("osmid")) if row.get("osmid") is not None else None,
                "osmtype": row.get("osmtype"),
                "tourism": row.get("tourism"),
                "rating": safe_float(row.get("rating")),
                "amenities": row.get("tags", {})
            }
            for _, row in gdf.iterrows()
        ]
    
    def _calculate_tier_stats(self, gdf: gpd.GeoDataFrame) -> Dict[str, int]:
        """Calculate tier statistics from GeoDataFrame."""
        if len(gdf) == 0:
            return {"tier_0": 0, "tier_1": 0, "tier_2": 0, "tier_3": 0}
        
        # Count occurrences of each tier
        tier_counts = gdf['tier'].value_counts().to_dict()
        
        return {
            "tier_0": tier_counts.get(0, 0),
            "tier_1": tier_counts.get(1, 0), 
            "tier_2": tier_counts.get(2, 0),
            "tier_3": tier_counts.get(3, 0)
        }
    
    def _build_main_poi_data(self, main_poi_name: str, location: Optional[str], poi_details: Optional[dict]) -> dict:
        """Build main POI data structure."""
        def safe_float(value):
            """Safely convert value to float, handling NaN cases."""
            if value is None:
                return None
            try:
                f_val = float(value)
                return None if math.isnan(f_val) or math.isinf(f_val) else f_val
            except (ValueError, TypeError):
                return None
        
        if poi_details:
            return {
                "name": main_poi_name,
                "location": location,
                "lat": safe_float(poi_details.get("lat")),
                "lon": safe_float(poi_details.get("lon")),
                "display_name": poi_details.get("display_name"),
                "type": poi_details.get("type"),
                "address": poi_details.get("address")
            }
        else:
            return {
                "name": main_poi_name,
                "location": location,
                "lat": None,
                "lon": None,
                "display_name": None,
                "type": None,
                "address": None
            }
    
    def _extract_attraction_from_query(self, query: str) -> Optional[str]:
        """Extract attraction name from query text."""
        # Common attraction keywords
        attraction_keywords = [
            "水族館", "博物館", "美術館", "動物園", "遊樂園", "主題樂園",
            "城堡", "神社", "寺廟", "公園", "廣場", "塔", "橋", "海灘",
            "溫泉", "滑雪場", "商場", "百貨", "市場", "街道", "老街"
        ]
        
        # Look for attraction keywords in the query
        for keyword in attraction_keywords:
            if keyword in query:
                # Find the position of the keyword
                keyword_pos = query.find(keyword)
                
                # Look for potential attraction name before the keyword
                # e.g., "沖繩水族館" from "我想去沖繩水族館"
                start_pos = max(0, keyword_pos - 10)  # Look up to 10 chars before
                potential_name = ""
                
                # Extract characters before the keyword that could be part of the attraction name
                for i in range(keyword_pos - 1, start_pos - 1, -1):
                    char = query[i]
                    # Include Chinese characters, letters, and numbers, but exclude common verbs/particles
                    if (char.isalnum() or '\u4e00' <= char <= '\u9fff') and char not in ['去', '到', '想', '的', '在', '和', '與']:
                        potential_name = char + potential_name
                    else:
                        break
                
                # Combine the potential prefix with the keyword
                full_name = potential_name + keyword
                
                # Return the full name if it looks reasonable, otherwise just the keyword
                if len(full_name) > len(keyword) and len(full_name) <= 20:
                    return full_name
                else:
                    return keyword
        
        return None
    
    def _convert_isochrones_to_geojson(self, isochrones_list: List[List[Polygon]]) -> List[Dict[str, Any]]:
        """Convert isochrone polygons to GeoJSON format."""
        geojson_geometries = []
        
        for isochrone_group in isochrones_list:
            if not isochrone_group:
                continue
                
            if len(isochrone_group) == 1:
                # Single polygon
                polygon = isochrone_group[0]
                if isinstance(polygon, Polygon):
                    coords = [list(polygon.exterior.coords)]
                    geojson_geometries.append({
                        "type": "Polygon",
                        "coordinates": coords
                    })
            else:
                # Multiple polygons - use MultiPolygon
                all_coords = []
                for polygon in isochrone_group:
                    if isinstance(polygon, Polygon):
                        all_coords.append([list(polygon.exterior.coords)])
                
                if all_coords:
                    geojson_geometries.append({
                        "type": "MultiPolygon", 
                        "coordinates": all_coords
                    })
        
        return geojson_geometries