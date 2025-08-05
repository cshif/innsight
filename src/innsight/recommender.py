"""Recommender class that provides a unified interface for accommodation recommendations."""

from typing import List, Optional
import geopandas as gpd

from .services.accommodation_search_service import AccommodationSearchService


class Recommender:
    """Unified interface for accommodation recommendations."""
    
    def __init__(self, search_service: AccommodationSearchService):
        """Initialize recommender with search service dependency.
        
        Args:
            search_service: Service for searching accommodations
        """
        self.search_service = search_service
    
    def recommend(self, query: str, filters: Optional[List[str]] = None, top_n: int = 10) -> gpd.GeoDataFrame:
        """Get accommodation recommendations based on query and preferences.
        
        Args:
            query: Search query string
            filters: Optional list of filter conditions (e.g., ["parking", "wheelchair"])
            top_n: Maximum number of results to return
            
        Returns:
            GeoDataFrame containing recommended accommodations
        """
        # Get accommodations using existing search service
        accommodations = self.search_service.search_accommodations(query)
        
        # Apply ranking with filters if accommodations found
        if len(accommodations) > 0:
            accommodations = self.search_service.rank_accommodations(
                accommodations, 
                filters=filters, 
                top_n=top_n
            )
        
        return accommodations