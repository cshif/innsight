"""Unit tests for GeocodeService."""

import pytest
from unittest.mock import Mock, patch

from src.innsight.services.geocode_service import GeocodeService
from src.innsight.config import AppConfig
from src.innsight.exceptions import GeocodeError


class TestGeocodeService:
    """Test cases for GeocodeService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.config.api_endpoint = "http://example.com"
        self.config.nominatim_user_agent = "test"
        self.config.nominatim_timeout = 10
        self.service = GeocodeService(self.config)

    def test_client_lazy_initialization(self):
        """Test that client is lazily initialized."""
        assert self.service._client is None
        
        with patch('src.innsight.services.geocode_service.NominatimClient') as mock_client_class:
            client = self.service.client
            
            mock_client_class.assert_called_once_with(
                api_endpoint="http://example.com",
                user_agent="test", 
                timeout=10
            )
            assert self.service._client is not None

    def test_geocode_location_success(self):
        """Test successful geocoding."""
        mock_client = Mock()
        mock_client.geocode.return_value = [(25.0, 123.0)]
        self.service._client = mock_client
        
        result = self.service.geocode_location("Okinawa")
        
        assert result == (25.0, 123.0)
        mock_client.geocode.assert_called_once_with("Okinawa")

    def test_geocode_location_no_results(self):
        """Test geocoding with no results raises GeocodeError."""
        mock_client = Mock()
        mock_client.geocode.return_value = []
        self.service._client = mock_client
        
        with pytest.raises(GeocodeError, match="找不到地點"):
            self.service.geocode_location("NonexistentPlace")