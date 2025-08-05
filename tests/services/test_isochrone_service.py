"""Unit tests for IsochroneService."""

from unittest.mock import Mock, patch

from src.innsight.services.isochrone_service import IsochroneService
from src.innsight.config import AppConfig


class TestIsochroneService:
    """Test cases for IsochroneService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.service = IsochroneService(self.config)

    def test_get_isochrones_with_fallback_success(self):
        """Test successful isochrone retrieval."""
        with patch('src.innsight.services.isochrone_service.get_isochrones_by_minutes') as mock_get:
            mock_isochrones = [{'geometry': 'polygon1'}, {'geometry': 'polygon2'}]
            mock_get.return_value = mock_isochrones
            
            result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15, 30])
            
            assert result == mock_isochrones
            mock_get.assert_called_once_with((123.0, 25.0), [15, 30])

    def test_get_isochrones_with_fallback_cache_error(self):
        """Test fallback handling for cache errors."""
        with patch('src.innsight.services.isochrone_service.get_isochrones_by_minutes') as mock_get:
            mock_get.side_effect = [Exception("cache error"), [{'geometry': 'polygon'}]]
            
            with patch('sys.stderr'):
                result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
                
            assert result == [{'geometry': 'polygon'}]

    def test_get_isochrones_with_fallback_non_cache_error(self):
        """Test handling of non-cache errors."""
        with patch('src.innsight.services.isochrone_service.get_isochrones_by_minutes') as mock_get:
            mock_get.side_effect = Exception("network error")
            
            result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
            
            assert result is None
    
    def test_get_isochrones_with_fallback_cache_double_exception(self):
        """Test cache fallback when second call also fails (covers lines 26-27)."""
        with patch('src.innsight.services.isochrone_service.get_isochrones_by_minutes') as mock_get:
            # First call fails with cache error, second call also fails
            mock_get.side_effect = [
                Exception("cache error occurred"),  # First call triggers cache logic
                Exception("cache retry failed")     # Second call in cache fallback also fails
            ]
            
            with patch('sys.stderr'):  # Suppress stderr output
                result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
            
            # Should return None when both calls fail
            assert result is None
            # Verify both calls were made
            assert mock_get.call_count == 2
    
    def test_get_isochrones_with_fallback_cache_success_on_retry(self):
        """Test cache fallback succeeds on retry."""
        with patch('src.innsight.services.isochrone_service.get_isochrones_by_minutes') as mock_get:
            # First call fails with cache error, second call succeeds
            mock_isochrones = [{'geometry': 'cached_polygon'}]
            mock_get.side_effect = [
                Exception("Cache timeout error"),  # First call triggers cache logic
                mock_isochrones                    # Second call succeeds
            ]
            
            with patch('sys.stderr'):  # Suppress stderr output
                result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
            
            # Should return the successful result
            assert result == mock_isochrones
            # Verify both calls were made
            assert mock_get.call_count == 2