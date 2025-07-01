import os
import sys
from json import JSONDecodeError
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import Timeout, ConnectionError, HTTPError

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from scripts.ors_client import get_isochrones, retry_on_network_error
from shapely.geometry import Polygon


class TestRetryOnNetworkError:
    def test_retry_decorator_success_first_attempt(self):
        # Arrange
        @retry_on_network_error(max_attempts=3)
        def mock_function():
            return "success"
        
        # Act
        result = mock_function()
        
        # Assert
        assert result == "success"
    
    def test_retry_decorator_success_after_retry(self):
        # Arrange
        call_count = 0
        
        @retry_on_network_error(max_attempts=3, delay=0.01)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        # Act
        result = mock_function()
        
        # Assert
        assert result == "success"
        assert call_count == 3
    
    def test_retry_decorator_max_attempts_reached(self):
        # Arrange
        @retry_on_network_error(max_attempts=2, delay=0.01)
        def mock_function():
            raise ConnectionError("Connection failed")
        
        # Act & Assert
        with pytest.raises(ConnectionError):
            mock_function()
    
    def test_retry_decorator_http_error_429_retries(self):
        # Arrange
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
        
        # Act
        result = mock_function()
        
        # Assert
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_http_error_500_retries(self):
        # Arrange
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
        
        # Act
        result = mock_function()
        
        # Assert
        assert result == "success"
        assert call_count == 2
    
    def test_retry_decorator_http_error_400_no_retry(self):
        # Arrange
        @retry_on_network_error(max_attempts=3, delay=0.01)
        def mock_function():
            mock_response = Mock()
            mock_response.status_code = 400
            raise HTTPError(response=mock_response)
        
        # Act & Assert
        with pytest.raises(HTTPError):
            mock_function()


class TestGetIsochrones:
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_success(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {
                    "type": "Feature",
                    "properties": {"value": 600},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # Act
        result = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Polygon)
        
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
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": {
                "code": 2003,
                "message": "Parameter 'range' is out of limits"
            }
        }
        mock_post.return_value = mock_response
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="ORS API error 2003"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(99999,)
            )
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_http_error_400(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.side_effect = HTTPError(response=mock_response)
        
        # Act & Assert
        with pytest.raises(HTTPError):
            get_isochrones(
                profile="invalid-profile",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_http_error_500(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_post.return_value = mock_response
        get_isochrones.cache_clear()
        
        # Act & Assert
        with pytest.raises(HTTPError, match="Upstream temporary failure"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_connection_error(self, mock_post):
        # Arrange
        mock_post.side_effect = ConnectionError("Connection failed")
        get_isochrones.cache_clear()
        
        # Act & Assert
        with pytest.raises(ConnectionError):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_timeout_error(self, mock_post):
        # Arrange
        mock_post.side_effect = Timeout("Request timed out")
        get_isochrones.cache_clear()
        
        # Act & Assert
        with pytest.raises(Timeout):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_json_decode_error(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        get_isochrones.cache_clear()
        
        # Act & Assert
        with pytest.raises(ConnectionError, match="Invalid response format"):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        assert mock_post.call_count == 3
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_caching(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        get_isochrones.cache_clear()
        
        # Act
        result1 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        result2 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # Assert
        assert mock_post.call_count == 1
        assert result1 == result2
        assert isinstance(result1, list)
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_multiple_locations(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        
        # Act
        result = get_isochrones(
            profile="foot-walking",
            locations=((8.681495, 49.41461), (8.687872, 49.420318)),
            max_range=(300, 600)
        )
        
        # Assert
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
        
        assert result == []
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    @patch('time.time')  # Mock 時間讓快取過期
    def test_get_isochrones_fallback_cache_success_then_failure(self, mock_time, mock_post):
        # Arrange
        get_isochrones.cache_clear()
        start_time = 1000000
        mock_time.return_value = start_time
        
        # 第一次成功呼叫
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "features": [
                {
                    "type": "Feature",
                    "properties": {"value": 600},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
                }
            ]
        }
        mock_post.return_value = mock_response_success
        
        # Act - 第一次成功呼叫
        result1 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # 模擬時間過去 25 小時（超過 24 小時 TTL）
        mock_time.return_value = start_time + 25 * 3600
        
        # 第二次失敗呼叫，應該嘗試 API 然後回退到快取
        mock_post.side_effect = ConnectionError("Network error")
        
        # Act - 第二次失敗呼叫
        result2 = get_isochrones(
            profile="driving-car",
            locations=((8.681495, 49.41461),),
            max_range=(600,)
        )
        
        # Assert
        assert isinstance(result1, list)
        assert len(result1) == 1
        assert isinstance(result1[0], Polygon)
        assert result1 == result2  # 回退的快取結果應該相同
        assert mock_post.call_count == 4  # 1次成功 + 3次重試失敗
    
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_fallback_cache_no_cache_available(self, mock_post):
        # Arrange
        get_isochrones.cache_clear()
        mock_post.side_effect = ConnectionError("Network error")
        
        # Act & Assert - 沒有快取時應該拋出錯誤
        with pytest.raises(ConnectionError):
            get_isochrones(
                profile="driving-car",
                locations=((8.681495, 49.41461),),
                max_range=(600,)
            )
        
        assert mock_post.call_count == 3  # 3次重試失敗