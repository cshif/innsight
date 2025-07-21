"""Unit tests for overpass_client module with comprehensive mocking."""

import pytest
from unittest.mock import Mock, patch
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import os

from src.innsight.overpass_client import fetch_overpass
from src.innsight.exceptions import NetworkError, APIError


class TestOverpassClient:
    """Test cases for overpass_client with mocked API calls."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_query = """
        [out:json][timeout:25];
        nwr(around:100,26.2042,127.6792)["tourism"="hotel"];
        out center;
        """

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_success(self, mock_post):
        """Test successful Overpass API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 123456,
                    "lat": 26.2042,
                    "lon": 127.6792,
                    "tags": {
                        "tourism": "hotel",
                        "name": "Test Hotel"
                    }
                },
                {
                    "type": "way",
                    "id": 789012,
                    "center": {
                        "lat": 26.2100,
                        "lon": 127.6800
                    },
                    "tags": {
                        "tourism": "guest_house",
                        "name": "Test Guesthouse"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(self.test_query)
        
        assert len(result) == 2
        assert result[0]["type"] == "node"
        assert result[0]["id"] == 123456
        assert result[0]["tags"]["name"] == "Test Hotel"
        assert result[1]["type"] == "way"
        assert result[1]["id"] == 789012
        assert result[1]["tags"]["name"] == "Test Guesthouse"
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # The request should be made with data parameter
        assert call_args[1]['data'] == {"data": self.test_query}
        assert call_args[1]['timeout'] == 30

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_empty_results(self, mock_post):
        """Test Overpass API request with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": []
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(self.test_query)
        
        assert result == []

    @patch('src.innsight.overpass_client.requests.post')
    @patch.dict('os.environ', {'OVERPASS_URL': 'https://overpass-api.de/api/interpreter'})
    def test_fetch_overpass_http_error(self, mock_post):
        """Test Overpass API request with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 429  # Too Many Requests
        http_error = requests.HTTPError("Too Many Requests")
        http_error.response = mock_response  # Add response to the exception
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response
        
        # For HTTP 429, the code will retry and eventually raise the error
        with pytest.raises(requests.HTTPError):
            fetch_overpass(self.test_query)

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_timeout(self, mock_post):
        """Test Overpass API request timeout."""
        mock_post.side_effect = Timeout("Request timed out")
        
        with pytest.raises(NetworkError, match="Connection timeout or failure"):
            fetch_overpass(self.test_query)

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_connection_error(self, mock_post):
        """Test Overpass API connection error."""
        mock_post.side_effect = ConnectionError("Connection failed")
        
        with pytest.raises(NetworkError, match="Connection timeout or failure"):
            fetch_overpass(self.test_query)

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_invalid_json(self, mock_post):
        """Test Overpass API with invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        with pytest.raises(APIError, match="Invalid response format"):
            fetch_overpass(self.test_query)

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_missing_elements_key(self, mock_post):
        """Test Overpass API response without elements key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "version": "0.7.56.8",
            "generator": "Overpass API 0.7.56.8"
            # Missing "elements" key
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(self.test_query)
        
        assert result == []

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_malformed_elements(self, mock_post):
        """Test Overpass API with malformed elements."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 123456,
                    "lat": 26.2042,
                    "lon": 127.6792,
                    "tags": {
                        "tourism": "hotel",
                        "name": "Valid Hotel"
                    }
                },
                {
                    # Missing required fields like type, id
                    "tags": {
                        "tourism": "guest_house"
                    }
                },
                {
                    "type": "way",
                    "id": 789012,
                    "center": {
                        "lat": 26.2100,
                        "lon": 127.6800
                    },
                    "tags": {
                        "tourism": "apartment",
                        "name": "Valid Apartment"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(self.test_query)
        
        # Should return all elements, including malformed ones
        # (client is responsible for validation)
        assert len(result) == 3
        assert result[0]["tags"]["name"] == "Valid Hotel"
        assert result[2]["tags"]["name"] == "Valid Apartment"

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_large_response(self, mock_post):
        """Test Overpass API with large number of results."""
        # Generate a large number of mock elements
        elements = []
        for i in range(1000):
            elements.append({
                "type": "node",
                "id": 100000 + i,
                "lat": 26.2042 + (i * 0.001),
                "lon": 127.6792 + (i * 0.001),
                "tags": {
                    "tourism": "hotel",
                    "name": f"Hotel {i}"
                }
            })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": elements
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(self.test_query)
        
        assert len(result) == 1000
        assert result[0]["tags"]["name"] == "Hotel 0"
        assert result[999]["tags"]["name"] == "Hotel 999"

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_server_error(self, mock_post):
        """Test Overpass API server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.HTTPError("Internal Server Error")
        http_error.response = mock_response  # Add response to the exception
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            fetch_overpass(self.test_query)

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_query_error_response(self, mock_post):
        """Test Overpass API query syntax error."""
        mock_response = Mock()
        mock_response.status_code = 400
        http_error = requests.HTTPError("Bad Request")
        http_error.response = mock_response  # Add response to the exception
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response
        
        bad_query = "[invalid syntax"
        
        with pytest.raises(requests.HTTPError):
            fetch_overpass(bad_query)

    def test_fetch_overpass_empty_query(self):
        """Test Overpass API with empty query."""
        with patch('src.innsight.overpass_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"elements": []}
            mock_post.return_value = mock_response
            
            result = fetch_overpass("")
            
            assert result == []
            mock_post.assert_called_once()

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_unicode_query(self, mock_post):
        """Test Overpass API with Unicode characters in query."""
        unicode_query = """
        [out:json][timeout:25];
        nwr(around:100,35.6762,139.6503)["name"~"東京"];
        out center;
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 123456,
                    "lat": 35.6762,
                    "lon": 139.6503,
                    "tags": {
                        "tourism": "hotel",
                        "name": "東京ホテル"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = fetch_overpass(unicode_query)
        
        assert len(result) == 1
        assert result[0]["tags"]["name"] == "東京ホテル"
        
        # Verify Unicode query was sent correctly
        call_args = mock_post.call_args
        assert "東京" in call_args[1]['data']['data']

    @patch('src.innsight.overpass_client.requests.post')
    def test_fetch_overpass_request_exception(self, mock_post):
        """Test Overpass API with generic request exception."""
        mock_post.side_effect = RequestException("Generic request error")
        
        # RequestException is not specifically caught by fetch_overpass,
        # so it will bubble up as-is
        with pytest.raises(RequestException):
            fetch_overpass(self.test_query)