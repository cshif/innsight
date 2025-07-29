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