"""Main accommodation search service that orchestrates the search process."""

from typing import List
import geopandas as gpd

from ..config import AppConfig
from ..rating_service import RatingService
from ..exceptions import NoAccommodationError
from .query_service import QueryService
from .geocode_service import GeocodeService
from .accommodation_service import AccommodationService
from .isochrone_service import IsochroneService
from .tier_service import TierService


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
        
        # Sort by score in descending order
        gdf = self.sort_accommodations(gdf)
        
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
    
    def format_accommodations_as_markdown(self, accommodations_df: gpd.GeoDataFrame) -> str:
        """Format accommodations as markdown output."""
        if len(accommodations_df) == 0:
            return "# 住宿推薦結果\n\n沒有找到符合條件的住宿。"
        
        lines = ["# 住宿推薦結果", ""]
        
        # Display top 10 results (assuming input is already sorted)
        for idx, (_, row) in enumerate(accommodations_df.head(10).iterrows(), 1):
            # Accommodation header
            name = row.get('name', '未知住宿')
            lines.append(f"## {idx}. {name}")
            
            # Basic info
            score_raw = row.get('score', 0)
            # Format score to 1 decimal place
            score = f"{float(score_raw):.1f}" if score_raw is not None else "0.0"
            tier = row.get('tier', 0)
            rating = row.get('rating', 'N/A')
            
            lines.append(f"**分數:** {score}")
            lines.append(f"**等級:** {tier}")
            lines.append(f"**評分:** {rating}")
            
            # Amenities
            lines.append("**設施:**")
            tags = row.get('tags', {})
            
            # Format amenities with Chinese names and emoji
            amenity_map = {
                'parking': '停車場',
                'wheelchair': '無障礙',
                'kids': '親子友善',
                'pet': '寵物友善'
            }
            
            for amenity_key, amenity_name in amenity_map.items():
                if amenity_key in tags:
                    emoji = "✅" if tags[amenity_key] == 'yes' else "❌"
                    lines.append(f"- {amenity_name}: {emoji}")
            
            # Add empty line between accommodations (except for the last one)
            if idx < min(10, len(accommodations_df)):
                lines.append("")
        
        return "\n".join(lines)