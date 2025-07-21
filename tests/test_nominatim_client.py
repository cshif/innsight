"""Unit tests for nominatim_client module with comprehensive mocking."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from src.innsight.nominatim_client import NominatimClient
from src.innsight.exceptions import GeocodeError


class TestNominatimClient:
    """Test cases for NominatimClient with mocked API calls."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_endpoint = "http://test-nominatim.example.com"
        self.user_agent = "test-agent"
        self.timeout = 10
        self.client = NominatimClient(
            api_endpoint=self.api_endpoint,
            user_agent=self.user_agent,
            timeout=self.timeout
        )

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_success_single_result(self, mock_get):
        """Test successful geocoding with single result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "26.2042",
                "lon": "127.6792",
                "display_name": "Okinawa, Japan"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("Okinawa")
        
        assert result == [(26.2042, 127.6792)]
        mock_get.assert_called_once()
        
        # Check request parameters
        call_args = mock_get.call_args
        assert call_args[1]['params']['q'] == 'Okinawa'
        assert call_args[1]['params']['format'] == 'json'
        assert call_args[1]['headers']['User-Agent'] == self.user_agent
        assert call_args[1]['timeout'] == self.timeout

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_success_multiple_results(self, mock_get):
        """Test successful geocoding with multiple results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "26.2042",
                "lon": "127.6792", 
                "display_name": "Okinawa Prefecture, Japan"
            },
            {
                "lat": "26.3344",
                "lon": "127.8056",
                "display_name": "Okinawa City, Japan"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("Okinawa")
        
        assert len(result) == 2
        assert result[0] == (26.2042, 127.6792)
        assert result[1] == (26.3344, 127.8056)

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_no_results(self, mock_get):
        """Test geocoding with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        result = self.client.geocode("NonexistentPlace")
        
        assert result == []

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_http_error_status(self, mock_get):
        """Test geocoding with HTTP error status."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("Not found")
        mock_get.return_value = mock_response
        
        with pytest.raises(GeocodeError, match="Network error"):
            self.client.geocode("BadQuery")

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_request_timeout(self, mock_get):
        """Test geocoding with request timeout."""
        mock_get.side_effect = Timeout("Request timed out")
        
        with pytest.raises(GeocodeError, match="Network error"):
            self.client.geocode("SlowQuery")

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_connection_error(self, mock_get):
        """Test geocoding with connection error."""
        mock_get.side_effect = ConnectionError("Connection failed")
        
        with pytest.raises(GeocodeError, match="Network error"):
            self.client.geocode("ConnFailQuery")

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_invalid_json_response(self, mock_get):
        """Test geocoding with invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with pytest.raises(GeocodeError, match="Invalid JSON received from API"):
            self.client.geocode("BadJSONQuery")

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_missing_coordinates(self, mock_get):
        """Test geocoding with missing lat/lon in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "display_name": "Incomplete Location"
                # Missing lat/lon
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("IncompleteQuery")
        
        assert result == []

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_partial_coordinates(self, mock_get):
        """Test geocoding with partial coordinates in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "26.2042",
                # Missing lon
                "display_name": "Partial Location"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("PartialQuery")
        
        assert result == []

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_invalid_coordinates(self, mock_get):
        """Test geocoding with invalid coordinate values."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "invalid_lat",
                "lon": "invalid_lon",
                "display_name": "Invalid Coordinates"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("InvalidCoordQuery")
        
        assert result == []

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_mixed_valid_invalid_results(self, mock_get):
        """Test geocoding with mix of valid and invalid results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "26.2042",
                "lon": "127.6792",
                "display_name": "Valid Location"
            },
            {
                "lat": "invalid",
                "lon": "127.8056",
                "display_name": "Invalid Location"
            },
            {
                "lat": "26.3344",
                "lon": "127.8056", 
                "display_name": "Another Valid Location"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("MixedQuery")
        
        # Should return only valid coordinates
        assert len(result) == 2
        assert result[0] == (26.2042, 127.6792)
        assert result[1] == (26.3344, 127.8056)

    def test_client_initialization(self):
        """Test client initialization with different parameters."""
        client = NominatimClient(
            api_endpoint="http://custom.endpoint.com",
            user_agent="custom-agent",
            timeout=30
        )
        
        assert client.api_endpoint == "http://custom.endpoint.com"
        assert client.user_agent == "custom-agent"
        assert client.timeout == 30

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_empty_query(self, mock_get):
        """Test geocoding with empty query string."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        result = self.client.geocode("")
        
        assert result == []
        # Should still make the request
        mock_get.assert_called_once()

    @patch('src.innsight.nominatim_client.requests.get')
    def test_geocode_unicode_query(self, mock_get):
        """Test geocoding with Unicode characters in query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "35.6762",
                "lon": "139.6503",
                "display_name": "Tokyo, Japan"
            }
        ]
        mock_get.return_value = mock_response
        
        result = self.client.geocode("東京")
        
        assert result == [(35.6762, 139.6503)]
        
        # Check that Unicode query was passed correctly
        call_args = mock_get.call_args
        assert call_args[1]['params']['q'] == '東京'