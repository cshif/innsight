import os
import pytest
from unittest.mock import Mock, patch
from requests.exceptions import Timeout, ConnectionError, HTTPError
from json import JSONDecodeError

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from scripts.ors_client import get_isochrones, retry_on_network_error


class TestRetryOnNetworkError:
    def test_retry_decorator_success_first_attempt(self):
        @retry_on_network_error(max_attempts=3)
        def mock_function():
            return "success"
        
        result = mock_function()
        assert result == "success"
    
    def test_retry_decorator_success_after_retry(self):
        call_count = 0
        
        @retry_on_network_error(max_attempts=3, delay=0.01)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = mock_function()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_decorator_max_attempts_reached(self):
        @retry_on_network_error(max_attempts=2, delay=0.01)
        def mock_function():
            raise ConnectionError("Connection failed")
        
        with pytest.raises(ConnectionError):
            mock_function()
    
    def test_retry_decorator_http_error_429_retries(self):
        call_count = 0
        
        @retry_on_network_error(max_attempts=2, delay=0.01)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                mock_response = Mock()
                mock_response.status_code = 429
                raise HTTPError(response=mock_response)
            return "success"
        
        result = mock_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_http_error_500_retries(self):
        call_count = 0
        
        @retry_on_network_error(max_attempts=2, delay=0.01)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                mock_response = Mock()
                mock_response.status_code = 500
                raise HTTPError(response=mock_response)
            return "success"
        
        result = mock_function()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_http_error_400_no_retry(self):
        @retry_on_network_error(max_attempts=3, delay=0.01)
        def mock_function():
            mock_response = Mock()
            mock_response.status_code = 400
            raise HTTPError(response=mock_response)
        
        with pytest.raises(HTTPError):
            mock_function()


class TestGetIsochrones:
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {
                    "type": "Feature",
                    "properties": {"value": 600},
                    "geometry": {"type": "Polygon", "coordinates": []}
                }
            ]
        }
        mock_post.return_value = mock_response
        
        result = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        assert "features" in result
        assert len(result["features"]) == 1
        
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/driving-car",
            json={
                "locations": ((8.681495, 49.41461),),
                "range": (600,)
            },
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "test_key"
            },
            timeout=(5, 30)
        )
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_api_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": {
                "code": 2003,
                "message": "Parameter 'range' is out of limits"
            }
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="ORS API error 2003"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(99999,)
            )
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_http_error_400(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.side_effect = HTTPError(response=mock_response)
        
        with pytest.raises(HTTPError):
            get_isochrones(
                profile="invalid-profile",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_http_error_500(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        
        # Clear cache to ensure fresh test
        get_isochrones.cache_clear()
        
        with pytest.raises(HTTPError, match="Upstream temporary failure"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        # Should retry 3 times
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_connection_error(self, mock_post):
        mock_post.side_effect = ConnectionError("Connection failed")
        
        # Clear cache to ensure fresh test
        get_isochrones.cache_clear()
        
        with pytest.raises(ConnectionError):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        # Should retry 3 times
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_timeout_error(self, mock_post):
        mock_post.side_effect = Timeout("Request timed out")
        
        # Clear cache to ensure fresh test
        get_isochrones.cache_clear()
        
        with pytest.raises(Timeout):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        # Should retry 3 times
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_json_decode_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.raise_for_status.return_value = None  # Don't raise HTTPError
        mock_post.return_value = mock_response
        
        # Clear cache to ensure fresh test
        get_isochrones.cache_clear()
        
        # JSONDecodeError is now converted to ConnectionError
        with pytest.raises(ConnectionError, match="Invalid response format"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        # Should retry 3 times due to retry decorator
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_caching(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        
        # Clear cache first
        get_isochrones.cache_clear()
        
        # Make first call
        result1 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # Make second call with same parameters
        result2 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # Should only make one HTTP request due to caching
        assert mock_post.call_count == 1
        assert result1 == result2
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_multiple_locations(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        
        result = get_isochrones(
            profile="foot-walking",
            locations=((8.681495, 49.41461), (8.687872, 49.420318)),
            max_range=(300, 600)
        )
        
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/foot-walking",
            json={
                "locations": ((8.681495, 49.41461), (8.687872, 49.420318)),
                "range": (300, 600)
            },
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "test_key"
            },
            timeout=(5, 30)
        )
        
        assert result == {"features": []}