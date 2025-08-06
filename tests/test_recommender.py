"""Tests for Recommender class."""

import pytest
import pandas as pd
import geopandas as gpd
from unittest.mock import Mock

from src.innsight.recommender import Recommender
from src.innsight.exceptions import NoAccommodationError


class TestRecommender:
    """Test suite for Recommender class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_search_service = Mock()
        # Configure config mock to return expected default values
        self.mock_search_service.config.default_top_n = 10
        self.recommender = Recommender(self.mock_search_service)
    
    def test_recommend_basic_flow(self):
        """Test basic recommendation flow without filters."""
        # Arrange
        expected_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],
            'score': [85.0, 75.0],
            'tier': [1, 2]
        })
        
        self.mock_search_service.search_accommodations.return_value = expected_gdf
        self.mock_search_service.rank_accommodations.return_value = expected_gdf
        
        # Act
        result = self.recommender.recommend("台北101")
        
        # Assert
        self.mock_search_service.search_accommodations.assert_called_once_with("台北101")
        self.mock_search_service.rank_accommodations.assert_called_once_with(
            expected_gdf, filters=None, top_n=10
        )
        assert result.equals(expected_gdf)
    
    def test_recommend_with_filters(self):
        """Test recommendation with filters applied."""
        # Arrange
        initial_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'score': [85.0, 75.0, 65.0],
            'tier': [1, 2, 3]
        })
        filtered_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [1]
        })
        
        self.mock_search_service.search_accommodations.return_value = initial_gdf
        self.mock_search_service.rank_accommodations.return_value = filtered_gdf
        
        # Act
        result = self.recommender.recommend("台北101", filters=["parking", "wheelchair"])
        
        # Assert
        self.mock_search_service.rank_accommodations.assert_called_once_with(
            initial_gdf, filters=["parking", "wheelchair"], top_n=10
        )
        assert result.equals(filtered_gdf)
    
    def test_recommend_with_custom_top_n(self):
        """Test recommendation with custom top_n limit."""
        # Arrange
        expected_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],
            'score': [85.0, 75.0],
            'tier': [1, 2]
        })
        
        self.mock_search_service.search_accommodations.return_value = expected_gdf
        self.mock_search_service.rank_accommodations.return_value = expected_gdf.head(5)
        
        # Act
        result = self.recommender.recommend("台北101", top_n=5)
        
        # Assert
        self.mock_search_service.rank_accommodations.assert_called_once_with(
            expected_gdf, filters=None, top_n=5
        )
    
    def test_recommend_empty_search_results(self):
        """Test recommendation when search returns no results."""
        # Arrange
        empty_gdf = gpd.GeoDataFrame()
        self.mock_search_service.search_accommodations.return_value = empty_gdf
        
        # Act
        result = self.recommender.recommend("不存在的地點")
        
        # Assert
        self.mock_search_service.search_accommodations.assert_called_once_with("不存在的地點")
        self.mock_search_service.rank_accommodations.assert_not_called()
        assert len(result) == 0
        assert isinstance(result, gpd.GeoDataFrame)
    
    def test_recommend_handles_ranking_exception(self):
        """Test recommendation handles exceptions from ranking service."""
        # Arrange
        initial_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [1]
        })
        
        self.mock_search_service.search_accommodations.return_value = initial_gdf
        self.mock_search_service.rank_accommodations.side_effect = NoAccommodationError("No matches")
        
        # Act & Assert
        with pytest.raises(NoAccommodationError):
            self.recommender.recommend("台北101", filters=["非常嚴格的條件"])
    
    def test_recommend_preserves_geodataframe_type(self):
        """Test that recommendation preserves GeoDataFrame type."""
        # Arrange
        expected_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [1]
        })
        
        self.mock_search_service.search_accommodations.return_value = expected_gdf
        self.mock_search_service.rank_accommodations.return_value = expected_gdf
        
        # Act
        result = self.recommender.recommend("台北101")
        
        # Assert
        assert isinstance(result, gpd.GeoDataFrame)