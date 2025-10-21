"""Tests for Pipeline class."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import geopandas as gpd
import pandas as pd

from src.innsight.pipeline import Recommender


class TestRecommenderPipeline:
    """Test suite for Recommender Pipeline class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Start patches
        self.config_patcher = patch('src.innsight.pipeline.AppConfig.from_env')
        self.search_service_patcher = patch('src.innsight.pipeline.AccommodationSearchService')
        self.geocode_service_patcher = patch('src.innsight.pipeline.GeocodeService')
        self.isochrone_service_patcher = patch('src.innsight.pipeline.IsochroneService')
        self.recommender_core_patcher = patch('src.innsight.pipeline.RecommenderCore')

        self.mock_config = self.config_patcher.start()
        self.mock_search_service = self.search_service_patcher.start()
        self.mock_geocode_service = self.geocode_service_patcher.start()
        self.mock_isochrone_service = self.isochrone_service_patcher.start()
        self.mock_recommender_core = self.recommender_core_patcher.start()

        # Set up mock config with actual values (not Mock objects)
        mock_config_instance = Mock()
        mock_config_instance.recommender_cache_ttl_seconds = 1800
        mock_config_instance.recommender_cache_maxsize = 20
        mock_config_instance.recommender_cache_cleanup_interval = 60
        self.mock_config.return_value = mock_config_instance

        # Create the Recommender instance
        self.recommender = Recommender()

    def teardown_method(self):
        """Clean up patches after each test method."""
        self.config_patcher.stop()
        self.search_service_patcher.stop()
        self.geocode_service_patcher.stop()
        self.isochrone_service_patcher.stop()
        self.recommender_core_patcher.stop()

    def test_merge_filters_with_parsed_and_api_filters(self):
        """Test merging parsed filters with API filters."""
        # Given: parsed filters and API filters
        parsed_filters = ["parking", "kids"]
        api_filters = ["wheelchair", "pet"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should combine both lists
        assert result == ["parking", "kids", "wheelchair", "pet"]

    def test_merge_filters_with_duplicates(self):
        """Test merging filters removes duplicates while preserving order."""
        # Given: overlapping filters
        parsed_filters = ["parking", "kids", "wheelchair"]
        api_filters = ["wheelchair", "pet", "parking"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should remove duplicates, keeping first occurrence
        assert result == ["parking", "kids", "wheelchair", "pet"]

    def test_merge_filters_with_empty_parsed_filters(self):
        """Test merging with empty parsed filters."""
        # Given: empty parsed filters
        parsed_filters = []
        api_filters = ["wheelchair", "pet"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should return API filters only
        assert result == ["wheelchair", "pet"]

    def test_merge_filters_with_empty_api_filters(self):
        """Test merging with empty API filters."""
        # Given: empty API filters
        parsed_filters = ["parking", "kids"]
        api_filters = []
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should return parsed filters only
        assert result == ["parking", "kids"]

    def test_merge_filters_with_both_empty(self):
        """Test merging with both filter lists empty."""
        # Given: both lists empty
        parsed_filters = []
        api_filters = []
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should return empty list
        assert result == []

    def test_merge_filters_with_none_parsed_filters(self):
        """Test merging when parsed filters is None."""
        # Given: None parsed filters
        parsed_filters = None
        api_filters = ["wheelchair", "pet"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should handle None gracefully
        assert result == ["wheelchair", "pet"]

    def test_merge_filters_with_none_api_filters(self):
        """Test merging when API filters is None."""
        # Given: None API filters
        parsed_filters = ["parking", "kids"]
        api_filters = None
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should handle None gracefully
        assert result == ["parking", "kids"]

    def test_merge_filters_with_both_none(self):
        """Test merging when both filter lists are None."""
        # Given: both lists None
        parsed_filters = None
        api_filters = None
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should return empty list
        assert result == []

    def test_merge_filters_preserves_order(self):
        """Test that merging preserves the order (parsed first, then API)."""
        # Given: filters with specific order
        parsed_filters = ["kids", "parking"]
        api_filters = ["pet", "wheelchair"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should preserve order (parsed first)
        assert result == ["kids", "parking", "pet", "wheelchair"]

    def test_merge_filters_complex_duplicate_scenario(self):
        """Test complex scenario with multiple duplicates."""
        # Given: complex overlap scenario
        parsed_filters = ["parking", "kids", "pet", "wheelchair"]
        api_filters = ["wheelchair", "parking", "kids", "pet"]
        
        # When: merging filters
        result = self.recommender._merge_filters(parsed_filters, api_filters)
        
        # Then: should keep original order from parsed, no duplicates
        assert result == ["parking", "kids", "pet", "wheelchair"]

    @patch('src.innsight.pipeline.parse_query')
    @patch('src.innsight.pipeline.extract_location_from_query') 
    def test_run_integrates_parsed_filters_with_api_filters(self, mock_extract_location, mock_parse_query):
        """Test that run() method correctly integrates parsed and API filters."""
        # Given: query with parsed filters and API filters
        query_data = {
            "query": "台北101附近有停車位的親子住宿",
            "filters": ["wheelchair", "pet"],
            "top_n": 10
        }
        
        # Mock parse_query to return filters
        mock_parse_query.return_value = {
            'filters': ['parking', 'kids'],
            'poi': '台北101',
            'place': '台北'
        }
        mock_extract_location.return_value = '台北'
        
        # Mock geocode service
        self.recommender.geocode_service.geocode_location_detailed = Mock(return_value={
            'lat': 25.034, 'lon': 121.565, 'display_name': '台北101'
        })
        
        # Mock recommender core to capture the merged filters
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [2],
            'lat': [25.034],
            'lon': [121.565],
            'osmid': ['123'],
            'osmtype': ['way'],
            'tourism': ['hotel'],
            'rating': [4.5],
            'tags': [{}]
        })
        self.recommender.recommender.recommend_by_coordinates = Mock(return_value=mock_gdf)
        
        # Mock isochrone service
        self.recommender.isochrone_service.get_isochrones_with_fallback = Mock(return_value=[])
        self.recommender.config.default_isochrone_intervals = [15, 30]
        
        # When: running the pipeline
        result = self.recommender.run(query_data)
        
        # Then: should call recommend_by_coordinates with merged filters
        expected_merged_filters = ['parking', 'kids', 'wheelchair', 'pet']
        self.recommender.recommender.recommend_by_coordinates.assert_called_once_with(
            25.034, 121.565, expected_merged_filters, 10, None
        )
        
        # And: should return successful result
        assert result['stats']['tier_2'] == 1
        assert len(result['top']) == 1
        assert result['top'][0]['name'] == 'Hotel A'

    @patch('src.innsight.pipeline.parse_query')
    @patch('src.innsight.pipeline.extract_location_from_query')
    def test_run_handles_empty_parsed_filters(self, mock_extract_location, mock_parse_query):
        """Test that run() method handles empty parsed filters correctly."""
        # Given: query with no parsed filters but API filters
        query_data = {
            "query": "台北住宿推薦",
            "filters": ["wheelchair", "pet"],
            "top_n": 10
        }
        
        # Mock parse_query to return no filters and no poi (so it falls back to recommend)
        mock_parse_query.return_value = {
            'filters': [],
            'poi': '',
            'place': None  # This will cause search_term to be empty
        }
        mock_extract_location.return_value = None  # No location extracted
        
        # Mock empty geodataframe  
        mock_gdf = gpd.GeoDataFrame()
        self.recommender.recommender.recommend = Mock(return_value=mock_gdf)
        
        # When: running the pipeline
        result = self.recommender.run(query_data)
        
        # Then: should call recommend with only API filters (since no coordinates available)
        expected_merged_filters = ['wheelchair', 'pet']
        self.recommender.recommender.recommend.assert_called_once_with(
            "台北住宿推薦", expected_merged_filters, 10, None
        )

    @patch('src.innsight.pipeline.parse_query')
    def test_run_handles_parse_query_failure(self, mock_parse_query):
        """Test that run() method handles parse_query failures gracefully."""
        # Given: query that causes parse_query to fail
        query_data = {
            "query": "some query",
            "filters": ["wheelchair"],
            "top_n": 10
        }
        
        # Mock parse_query to raise exception
        mock_parse_query.side_effect = Exception("Parse error")
        
        # Mock empty geodataframe
        mock_gdf = gpd.GeoDataFrame()
        self.recommender.recommender.recommend = Mock(return_value=mock_gdf)
        
        # When: running the pipeline
        result = self.recommender.run(query_data)
        
        # Then: should still use API filters (parsed_filters defaults to [])
        expected_merged_filters = ['wheelchair']
        self.recommender.recommender.recommend.assert_called_once_with(
            "some query", expected_merged_filters, 10, None
        )