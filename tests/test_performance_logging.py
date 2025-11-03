"""
Test suite for performance metrics logging in the recommendation pipeline.

This test suite validates:
1. Total request duration is logged
2. Individual stage durations are logged
3. Duration format is in milliseconds with proper precision
4. Cache hits skip unnecessary stages
"""

import json
import time
from unittest.mock import Mock, patch, MagicMock
import pytest
import structlog
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from innsight.pipeline import Recommender


class TestPerformanceLogging:
    """Test performance metrics logging in recommendation pipeline."""

    def setup_method(self):
        """Setup for each test method."""
        with patch('innsight.pipeline.AppConfig.from_env') as mock_config:
            mock_config.return_value = self._create_mock_config()
            self.recommender = Recommender()

    def _create_mock_config(self):
        """Create a mock config for testing."""
        config = Mock()
        config.recommender_cache_maxsize = 20
        config.recommender_cache_ttl_seconds = 1800
        config.recommender_cache_cleanup_interval = 60
        config.default_isochrone_intervals = [15, 30, 60]
        config.rating_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        config.max_tier_value = 3
        config.max_rating_value = 5
        config.max_score = 100
        config.default_missing_score = 50
        return config

    def _create_mock_gdf(self, n=10):
        """Create a mock GeoDataFrame with accommodation data."""
        data = {
            'name': [f'Hotel {i}' for i in range(n)],
            'score': [80.0 + i for i in range(n)],
            'tier': [i % 4 for i in range(n)],
            'lat': [23.8 + i * 0.01 for i in range(n)],
            'lon': [120.9 + i * 0.01 for i in range(n)],
            'osmid': [f'osm_{i}' for i in range(n)],
            'osmtype': ['node'] * n,
            'tourism': ['hotel'] * n,
            'rating': [4.0 + (i % 10) * 0.1 for i in range(n)],
            'tags': [{}] * n,
            'geometry': [Point(120.9 + i * 0.01, 23.8 + i * 0.01) for i in range(n)]
        }
        return gpd.GeoDataFrame(data, geometry='geometry')

    def _create_mock_isochrones(self):
        """Create mock isochrone polygons."""
        # Create simple polygon for testing
        polygon = Polygon([(120.9, 23.8), (120.91, 23.8), (120.91, 23.81), (120.9, 23.81)])
        return [[polygon]]

    def test_request_duration_logged(self, monkeypatch):
        """Test that total request duration is logged."""
        # Arrange: Capture log output
        log_output = []

        def mock_info(*args, **kwargs):
            log_output.append({'args': args, 'kwargs': kwargs})

        # Mock logger
        mock_logger = Mock()
        mock_logger.info = mock_info
        monkeypatch.setattr('innsight.pipeline.logger', mock_logger)

        # Mock all service dependencies
        mock_gdf = self._create_mock_gdf(10)

        with patch.object(self.recommender.geocode_service, 'geocode_location_detailed') as mock_geocode, \
             patch.object(self.recommender.isochrone_service, 'get_isochrones_with_fallback') as mock_isochrone, \
             patch.object(self.recommender.recommender, 'recommend_by_coordinates') as mock_recommend, \
             patch('innsight.pipeline.parse_query') as mock_parse:

            # Setup mocks
            mock_parse.return_value = {'poi': '日月潭', 'place': None, 'filters': []}
            mock_geocode.return_value = {'lat': 23.8, 'lon': 120.9, 'display_name': '日月潭'}
            mock_isochrone.return_value = self._create_mock_isochrones()
            mock_recommend.return_value = mock_gdf

            # Act
            query_data = {"query": "日月潭附近的住宿"}
            result = self.recommender.run(query_data)

        # Assert
        completion_logs = [log for log in log_output if log['args'] and 'pipeline completed' in log['args'][0].lower()]
        assert len(completion_logs) > 0, "Should log pipeline completion"

        completion_log = completion_logs[0]
        assert 'total_duration_ms' in completion_log['kwargs'], "Should include total_duration_ms"
        assert completion_log['kwargs']['total_duration_ms'] > 0, "Duration should be positive"
        assert 'Recommendation pipeline completed' in completion_log['args'][0] or \
               'recommendation pipeline completed' in completion_log['args'][0].lower(), \
               "Should have completion message"

    def test_stage_durations_logged(self, monkeypatch):
        """Test that individual stage durations are logged."""
        # Arrange: Capture log output
        log_output = []

        def mock_info(*args, **kwargs):
            log_output.append({'args': args, 'kwargs': kwargs})

        mock_logger = Mock()
        mock_logger.info = mock_info
        monkeypatch.setattr('innsight.pipeline.logger', mock_logger)

        # Mock all service dependencies
        mock_gdf = self._create_mock_gdf(10)

        with patch.object(self.recommender.geocode_service, 'geocode_location_detailed') as mock_geocode, \
             patch.object(self.recommender.isochrone_service, 'get_isochrones_with_fallback') as mock_isochrone, \
             patch.object(self.recommender.recommender, 'recommend_by_coordinates') as mock_recommend, \
             patch('innsight.pipeline.parse_query') as mock_parse:

            # Setup mocks
            mock_parse.return_value = {'poi': '日月潭', 'place': None, 'filters': []}
            mock_geocode.return_value = {'lat': 23.8, 'lon': 120.9, 'display_name': '日月潭'}
            mock_isochrone.return_value = self._create_mock_isochrones()
            mock_recommend.return_value = mock_gdf

            # Act
            query_data = {"query": "日月潭附近的住宿"}
            result = self.recommender.run(query_data)

        # Assert
        completion_logs = [log for log in log_output if log['args'] and 'pipeline completed' in log['args'][0].lower()]
        assert len(completion_logs) > 0, "Should log pipeline completion"

        completion_log = completion_logs[0]
        assert 'stages' in completion_log['kwargs'], "Should include stages dict"

        stages = completion_log['kwargs']['stages']
        assert 'geocoding_ms' in stages, "Should include geocoding_ms"
        assert 'isochrone_ms' in stages, "Should include isochrone_ms"
        assert 'search_ms' in stages, "Should include search_ms"

        assert stages['geocoding_ms'] >= 0, "Geocoding duration should be non-negative"
        assert stages['isochrone_ms'] >= 0, "Isochrone duration should be non-negative"
        assert stages['search_ms'] >= 0, "Search duration should be non-negative"

    def test_duration_format_milliseconds(self, monkeypatch):
        """Test that durations are in milliseconds with proper precision."""
        # Arrange: Capture log output
        log_output = []

        def mock_info(*args, **kwargs):
            log_output.append({'args': args, 'kwargs': kwargs})

        mock_logger = Mock()
        mock_logger.info = mock_info
        monkeypatch.setattr('innsight.pipeline.logger', mock_logger)

        # Mock all service dependencies
        mock_gdf = self._create_mock_gdf(10)

        with patch.object(self.recommender.geocode_service, 'geocode_location_detailed') as mock_geocode, \
             patch.object(self.recommender.isochrone_service, 'get_isochrones_with_fallback') as mock_isochrone, \
             patch.object(self.recommender.recommender, 'recommend_by_coordinates') as mock_recommend, \
             patch('innsight.pipeline.parse_query') as mock_parse:

            # Setup mocks
            mock_parse.return_value = {'poi': '日月潭', 'place': None, 'filters': []}
            mock_geocode.return_value = {'lat': 23.8, 'lon': 120.9, 'display_name': '日月潭'}
            mock_isochrone.return_value = self._create_mock_isochrones()
            mock_recommend.return_value = mock_gdf

            # Act
            query_data = {"query": "日月潭附近的住宿"}
            result = self.recommender.run(query_data)

        # Assert
        completion_logs = [log for log in log_output if log['args'] and 'pipeline completed' in log['args'][0].lower()]
        assert len(completion_logs) > 0, "Should log pipeline completion"

        completion_log = completion_logs[0]
        total_duration = completion_log['kwargs']['total_duration_ms']
        stages = completion_log['kwargs']['stages']

        # Check that all durations are numeric
        assert isinstance(total_duration, (int, float)), "total_duration_ms should be numeric"
        assert isinstance(stages['geocoding_ms'], (int, float)), "geocoding_ms should be numeric"
        assert isinstance(stages['isochrone_ms'], (int, float)), "isochrone_ms should be numeric"
        assert isinstance(stages['search_ms'], (int, float)), "search_ms should be numeric"

        # Check reasonable ranges (should be less than 1 second in mock environment)
        assert 0 < total_duration < 10000, "Total duration should be reasonable"
        assert 0 <= stages['geocoding_ms'] < 1000, "Geocoding duration should be reasonable"
        assert 0 <= stages['isochrone_ms'] < 1000, "Isochrone duration should be reasonable"
        assert 0 <= stages['search_ms'] < 1000, "Search duration should be reasonable"

    def test_cache_hit_skips_stages(self, monkeypatch):
        """Test that cache hits skip geocoding/isochrone/search stages."""
        # Arrange: Capture log output
        log_output = []

        def mock_info(*args, **kwargs):
            log_output.append({'args': args, 'kwargs': kwargs})

        def mock_debug(*args, **kwargs):
            pass  # Ignore debug logs

        mock_logger = Mock()
        mock_logger.info = mock_info
        mock_logger.debug = mock_debug
        monkeypatch.setattr('innsight.pipeline.logger', mock_logger)

        # Mock all service dependencies
        mock_gdf = self._create_mock_gdf(10)

        with patch.object(self.recommender.geocode_service, 'geocode_location_detailed') as mock_geocode, \
             patch.object(self.recommender.isochrone_service, 'get_isochrones_with_fallback') as mock_isochrone, \
             patch.object(self.recommender.recommender, 'recommend_by_coordinates') as mock_recommend, \
             patch('innsight.pipeline.parse_query') as mock_parse:

            # Setup mocks
            mock_parse.return_value = {'poi': '日月潭', 'place': None, 'filters': []}
            mock_geocode.return_value = {'lat': 23.8, 'lon': 120.9, 'display_name': '日月潭'}
            mock_isochrone.return_value = self._create_mock_isochrones()
            mock_recommend.return_value = mock_gdf

            # Act: First call to populate cache
            query_data = {"query": "日月潭附近的住宿"}
            result1 = self.recommender.run(query_data)

            # Clear log output
            log_output.clear()

            # Second call should hit cache
            result2 = self.recommender.run(query_data)

        # Assert
        completion_logs = [log for log in log_output if log['args'] and 'pipeline completed' in log['args'][0].lower()]
        assert len(completion_logs) > 0, "Should log pipeline completion for cache hit"

        cache_hit_log = completion_logs[0]
        assert 'cache_hit' in cache_hit_log['kwargs'], "Should include cache_hit field"
        assert cache_hit_log['kwargs']['cache_hit'] is True, "cache_hit should be True"

        stages = cache_hit_log['kwargs']['stages']
        # Cache hit should NOT include expensive stages (search, isochrone)
        # but MAY include parsing and geocoding (executed before cache check)
        assert 'search_ms' not in stages, "Cache hit should skip search_ms"
        assert 'isochrone_ms' not in stages, "Cache hit should skip isochrone_ms"

        # parsing_ms and geocoding_ms may be present (executed before cache check)
        # This is acceptable as they're needed to build the cache key

        # Total duration should be very small for cache hits
        total_duration = cache_hit_log['kwargs']['total_duration_ms']
        assert total_duration < 100, "Cache hit should be very fast (< 100ms)"
