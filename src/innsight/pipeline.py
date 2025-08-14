"""Pipeline for FastAPI integration with Recommender."""

from typing import Dict, List, Any
import geopandas as gpd

from .config import AppConfig
from .services.accommodation_search_service import AccommodationSearchService
from .recommender import Recommender as RecommenderCore
from .exceptions import NetworkError, APIError, GeocodeError, IsochroneError, ServiceUnavailableError


class Recommender:
    """Pipeline wrapper for Recommender to work with FastAPI."""
    
    def __init__(self):
        """Initialize the recommendation pipeline."""
        config = AppConfig.from_env()
        search_service = AccommodationSearchService(config)
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
                "top": []
            }
        
        try:
            # Use the Recommender directly
            gdf = self.recommender.recommend(query, filters, top_n, weights)
            
            # Convert to serializable format
            top_results = self._serialize_gdf(gdf)
            
            # Calculate tier statistics
            stats = self._calculate_tier_stats(gdf)
            
            return {
                "stats": stats,
                "top": top_results
            }
            
        except (NetworkError, APIError, GeocodeError, IsochroneError) as e:
            # External dependency failures should be re-raised as ServiceUnavailableError
            raise ServiceUnavailableError(f"External service unavailable: {str(e)}")
        except Exception as e:
            # Other exceptions return empty results
            return {
                "stats": {"tier_0": 0, "tier_1": 0, "tier_2": 0, "tier_3": 0},
                "top": []
            }
    
    def _serialize_gdf(self, gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
        """Convert GeoDataFrame to JSON-serializable format."""
        if len(gdf) == 0:
            return []
        
        return [
            {
                "name": row.get("name", "Unknown"),
                "score": float(row.get("score", 0)) if row.get("score") is not None else 0.0,
                "tier": int(row.get("tier", 0)) if row.get("tier") is not None else 0,
                "lat": float(row.get("lat")) if row.get("lat") is not None else None,
                "lon": float(row.get("lon")) if row.get("lon") is not None else None,
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