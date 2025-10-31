"""Tests for cache statistics functions."""

import pytest
from unittest.mock import Mock

from src.innsight.health import get_cache_stats


class TestGetCacheStats:
    """Test suite for get_cache_stats function."""

    def test_get_cache_stats_calculates_hit_rate_correctly(self):
        """Should calculate cache hit rate correctly with hits and misses."""
        # Create mock Recommender with cache statistics
        mock_recommender = Mock()
        mock_recommender._cache_hits = 150
        mock_recommender._cache_misses = 50
        mock_recommender._parsing_failures = 5
        mock_recommender._cache = {"key1": "val1", "key2": "val2", "key3": "val3"}
        mock_recommender._cache_max_size = 20

        result = get_cache_stats(mock_recommender)

        assert result["cache_hits"] == 150
        assert result["cache_misses"] == 50
        assert result["cache_hit_rate"] == 0.75  # 150 / (150 + 50) = 0.75
        assert result["total_requests"] == 200  # 150 + 50
        assert result["parsing_failures"] == 5
        assert result["cache_size"] == 3
        assert result["cache_max_size"] == 20

    def test_get_cache_stats_handles_zero_requests(self):
        """Should handle zero requests without division by zero error."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 0
        mock_recommender._cache_misses = 0
        mock_recommender._parsing_failures = 0
        mock_recommender._cache = {}
        mock_recommender._cache_max_size = 20

        result = get_cache_stats(mock_recommender)

        assert result["cache_hits"] == 0
        assert result["cache_misses"] == 0
        assert result["cache_hit_rate"] == 0.0
        assert result["total_requests"] == 0
        assert result["parsing_failures"] == 0
        assert result["cache_size"] == 0
        assert result["cache_max_size"] == 20

    def test_get_cache_stats_handles_only_misses(self):
        """Should return 0.0 hit rate when there are only misses."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 0
        mock_recommender._cache_misses = 100
        mock_recommender._parsing_failures = 10
        mock_recommender._cache = {}
        mock_recommender._cache_max_size = 20

        result = get_cache_stats(mock_recommender)

        assert result["cache_hits"] == 0
        assert result["cache_misses"] == 100
        assert result["cache_hit_rate"] == 0.0
        assert result["total_requests"] == 100
        assert result["parsing_failures"] == 10

    def test_get_cache_stats_handles_only_hits(self):
        """Should return 1.0 hit rate when there are only hits."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 100
        mock_recommender._cache_misses = 0
        mock_recommender._parsing_failures = 0
        mock_recommender._cache = {"key1": "val1"}
        mock_recommender._cache_max_size = 20

        result = get_cache_stats(mock_recommender)

        assert result["cache_hits"] == 100
        assert result["cache_misses"] == 0
        assert result["cache_hit_rate"] == 1.0
        assert result["total_requests"] == 100

    def test_get_cache_stats_returns_all_required_fields(self):
        """Should return all required fields in the response."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 10
        mock_recommender._cache_misses = 5
        mock_recommender._parsing_failures = 2
        mock_recommender._cache = {"a": 1, "b": 2}
        mock_recommender._cache_max_size = 50

        result = get_cache_stats(mock_recommender)

        # Check all required fields exist
        assert "cache_hits" in result
        assert "cache_misses" in result
        assert "cache_hit_rate" in result
        assert "total_requests" in result
        assert "parsing_failures" in result
        assert "cache_size" in result
        assert "cache_max_size" in result

    def test_get_cache_stats_with_large_numbers(self):
        """Should handle large cache statistics correctly."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 9_999_999
        mock_recommender._cache_misses = 1
        mock_recommender._parsing_failures = 500
        mock_recommender._cache = {f"key{i}": i for i in range(100)}
        mock_recommender._cache_max_size = 1000

        result = get_cache_stats(mock_recommender)

        assert result["cache_hits"] == 9_999_999
        assert result["cache_misses"] == 1
        assert result["total_requests"] == 10_000_000
        # Hit rate should be very close to 1.0
        assert result["cache_hit_rate"] > 0.9999
        assert result["cache_size"] == 100

    def test_get_cache_stats_hit_rate_is_float(self):
        """Should return cache_hit_rate as a float between 0.0 and 1.0."""
        mock_recommender = Mock()
        mock_recommender._cache_hits = 75
        mock_recommender._cache_misses = 25
        mock_recommender._parsing_failures = 0
        mock_recommender._cache = {}
        mock_recommender._cache_max_size = 20

        result = get_cache_stats(mock_recommender)

        assert isinstance(result["cache_hit_rate"], float)
        assert 0.0 <= result["cache_hit_rate"] <= 1.0
        assert result["cache_hit_rate"] == 0.75
