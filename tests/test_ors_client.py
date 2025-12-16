#!/usr/bin/env python3
"""
測試 ORS Client 的完整功能
包括正常功能、錯誤處理、API 超時、503 錯誤、rate-limit 重試、快取回退等場景
"""
import json
import os
import sys
import time
from unittest.mock import Mock, patch, call
import pytest
from requests.exceptions import HTTPError, Timeout, ConnectionError
from json import JSONDecodeError
from io import StringIO

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from innsight.ors_client import (
    get_isochrones_by_minutes, 
    _fallback_cache
)
from innsight.exceptions import IsochroneError, APIError
from shapely.geometry import Polygon


# 測試常數
TEST_COORD = (8.681495, 49.41461)
TEST_ENV = {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'}
SAMPLE_GEOJSON = {
    "features": [
        {
            "type": "Feature",
            "properties": {"value": 900},
            "geometry": {
                "type": "Polygon", 
                "coordinates": [[[8.6, 49.4], [8.7, 49.4], [8.7, 49.5], [8.6, 49.5], [8.6, 49.4]]]
            }
        }
    ]
}
SAMPLE_MULTI_GEOJSON = {
    "features": [
        {
            "type": "Feature",
            "properties": {"value": 900},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        },
        {
            "type": "Feature", 
            "properties": {"value": 1800},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}
        }
    ]
}


class TestGetIsochronesByMinutes:
    """測試 get_isochrones_by_minutes 函數的完整功能"""
    
    def setup_method(self):
        """每個測試前清理快取"""
        _fallback_cache.clear()
        get_isochrones_by_minutes.cache_clear()
    
    def _create_mock_response(self, status_code=200, json_data=None, error_text="", 
                             raise_error=None):
        """建立 mock response 的輔助方法"""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = error_text
        
        if json_data is not None:
            mock_response.json.return_value = json_data
        if raise_error:
            mock_response.raise_for_status.side_effect = raise_error
        else:
            mock_response.raise_for_status.return_value = None
            
        return mock_response
    
    def _assert_basic_result_structure(self, result, expected_count=1):
        """驗證基本結果結構的輔助方法"""
        assert isinstance(result, list)
        assert len(result) == expected_count
        assert all(isinstance(iso_list, list) for iso_list in result)
        assert all(len(iso_list) == 1 for iso_list in result)
        assert all(isinstance(iso_list[0], Polygon) for iso_list in result)
    
    # === 正常功能測試 ===
    
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_success_multiple_intervals(self, mock_post):
        """測試成功取得多個時間間隔的等時圈"""
        mock_post.return_value = self._create_mock_response(json_data=SAMPLE_MULTI_GEOJSON)
        
        result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15, 30])
        
        self._assert_basic_result_structure(result, expected_count=2)
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/driving-car",
            json={
                "locations": (TEST_COORD,),
                "range": (900, 1800)  # 15*60, 30*60
            },
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8", 
                "Authorization": "test_key"
            },
            timeout=(5, 30)
        )

    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_caching_mechanism(self, mock_post):
        """測試快取機制"""
        mock_post.return_value = self._create_mock_response(json_data={"features": []})
        
        # 兩次相同調用
        result1 = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        result2 = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert mock_post.call_count == 1  # 只調用一次API
        assert result1 == result2
        assert get_isochrones_by_minutes.cache_info()['size'] == 1

    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_different_profile(self, mock_post):
        """測試不同的交通模式"""
        mock_post.return_value = self._create_mock_response(json_data={"features": []})
        
        result = get_isochrones_by_minutes(
            coord=TEST_COORD, intervals=[10], profile='foot-walking'
        )
        
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/foot-walking",
            json={"locations": (TEST_COORD,), "range": (600,)},
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "test_key"
            },
            timeout=(5, 30)
        )
        assert result == []

    # === HTTP 錯誤處理測試 ===
    
    @patch('time.sleep')
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_503_service_unavailable_no_cache(self, mock_post, mock_sleep):
        """測試 503 Service Unavailable 且無快取時拋出 IsochroneError"""
        error = HTTPError("503 Service Unavailable")
        error.response = Mock(status_code=503)
        mock_post.return_value = self._create_mock_response(
            status_code=503, error_text="Service Unavailable", raise_error=error
        )
        
        with pytest.raises(IsochroneError) as exc_info:
            get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15, 30])
        
        assert "no cache available" in str(exc_info.value)
        assert mock_post.call_count == 3  # 重試 3 次
        
        # 驗證 sleep 被正確調用 (1秒, 2秒) - 重試3次但只sleep 2次
        expected_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_calls)
        assert mock_sleep.call_count == 2

    @patch('time.sleep')
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_429_rate_limit_retry_success(self, mock_post, mock_sleep):
        """測試 429 Rate Limit 重試後成功"""
        def side_effect(*args, **kwargs):
            if mock_post.call_count <= 2:
                error = HTTPError("429 Too Many Requests")
                error.response = Mock(status_code=429)
                return self._create_mock_response(
                    status_code=429, error_text="Too Many Requests", raise_error=error
                )
            else:
                return self._create_mock_response(json_data=SAMPLE_GEOJSON)
        
        mock_post.side_effect = side_effect
        
        result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert mock_post.call_count == 3
        self._assert_basic_result_structure(result)
        
        # 驗證 sleep 被正確調用 (1秒, 2秒)
        expected_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_calls)
        assert mock_sleep.call_count == 2

    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_400_bad_request_not_retried(self, mock_post):
        """測試 400 Bad Request 不會重試"""
        error = HTTPError("400 Bad Request")
        error.response = Mock(status_code=400)
        mock_post.return_value = self._create_mock_response(
            status_code=400, error_text="Bad Request", raise_error=error
        )
        
        with pytest.raises(IsochroneError):
            get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert mock_post.call_count == 1  # 不重試

    # === 網路連線錯誤測試 ===
    
    @patch('time.sleep')
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_connection_timeout_retry_success(self, mock_post, mock_sleep):
        """測試連接超時重試後成功"""
        def side_effect(*args, **kwargs):
            if mock_post.call_count <= 2:
                raise Timeout("Connection timeout")
            else:
                return self._create_mock_response(json_data=SAMPLE_GEOJSON)
        
        mock_post.side_effect = side_effect
        
        result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert mock_post.call_count == 3
        self._assert_basic_result_structure(result)
        
        # 驗證 sleep 被正確調用 (1秒, 2秒)
        expected_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_calls)
        assert mock_sleep.call_count == 2

    @patch('time.sleep')
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_connection_error_max_retries_exceeded(self, mock_post, mock_sleep):
        """測試連接錯誤超過最大重試次數"""
        mock_post.side_effect = ConnectionError("Connection failed")
        
        with pytest.raises(IsochroneError) as exc_info:
            get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert "no cache available" in str(exc_info.value)
        assert mock_post.call_count == 3
        
        # 驗證 sleep 被正確調用 (1秒, 2秒) - 重試3次但只sleep 2次
        expected_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_calls)
        assert mock_sleep.call_count == 2

    @patch('time.sleep')
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_json_decode_error_retry_success(self, mock_post, mock_sleep):
        """測試 JSON 解析錯誤重試後成功"""
        def side_effect(*args, **kwargs):
            if mock_post.call_count <= 2:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.side_effect = JSONDecodeError("Invalid JSON", "response", 0)
                return mock_response
            else:
                return self._create_mock_response(json_data=SAMPLE_GEOJSON)
        
        mock_post.side_effect = side_effect
        
        result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        assert mock_post.call_count == 3
        self._assert_basic_result_structure(result)
        
        # 驗證 sleep 被正確調用 (1秒, 2秒)
        expected_calls = [call(1), call(2)]
        mock_sleep.assert_has_calls(expected_calls)
        assert mock_sleep.call_count == 2

    # === 快取回退測試 ===
    
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    @patch('innsight.ors_client.logger')
    def test_cache_fallback_with_warning(self, mock_logger, mock_post):
        """測試快取回退機制"""
        # 先建立快取
        mock_post.return_value = self._create_mock_response(json_data=SAMPLE_GEOJSON)
        first_result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        assert len(first_result) == 1
        
        # 模擬 API 永遠回 503
        error = HTTPError("503 Service Unavailable")
        error.response = Mock(status_code=503)
        mock_post.return_value = self._create_mock_response(
            status_code=503, error_text="Service Unavailable", raise_error=error
        )
        
        # 手動設置快取為過期狀態
        cache_key = ('_fetch_isochrones_from_api', ('driving-car', (TEST_COORD,), (900,)), ())
        if cache_key in _fallback_cache:
            cached_result, _ = _fallback_cache[cache_key]
            old_timestamp = time.time() - 25 * 3600  # 25小時前
            _fallback_cache[cache_key] = (cached_result, old_timestamp)
        
        # 再次調用，使用過期快取
        fallback_result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])

        assert len(fallback_result) == 1
        mock_logger.warning.assert_called()

        # 驗證有快取回退的 warning
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        fallback_warnings = [call for call in warning_calls if 'using stale cache' in call]
        assert len(fallback_warnings) > 0

    # === API 錯誤響應測試 ===
    
    @patch.dict(os.environ, TEST_ENV)
    @patch('requests.post')
    def test_api_error_response_handling(self, mock_post):
        """測試 API 錯誤響應處理"""
        error_json = {
            "error": {
                "code": 2004,
                "message": "Request parameters exceed the server configuration limits."
            }
        }
        mock_post.return_value = self._create_mock_response(json_data=error_json)
        
        with pytest.raises(APIError) as exc_info:
            get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])
        
        error_msg = str(exc_info.value)
        assert "ORS API error 2004" in error_msg
        assert "Request parameters exceed" in error_msg

    # === 快取管理測試 ===
    
    def test_cache_info_and_clear(self):
        """測試快取資訊和清理功能"""
        get_isochrones_by_minutes.cache_clear()

        cache_info = get_isochrones_by_minutes.cache_info()
        assert isinstance(cache_info, dict)
        assert 'size' in cache_info
        assert cache_info['size'] == 0


class TestStructuredLogging:
    """Test suite for structured logging in ORS client."""

    def setup_method(self):
        """Clear cache before each test."""
        _fallback_cache.clear()
        get_isochrones_by_minutes.cache_clear()

    def test_api_success_logged_with_latency(self, monkeypatch, app_config):
        """Test that successful API call logs include latency."""
        monkeypatch.setenv("LOG_FORMAT", "json")

        from innsight.logging_config import configure_logging

        log_output = StringIO()
        configure_logging(app_config, stream=log_output)

        # Mock successful API call
        with patch.dict(os.environ, TEST_ENV):
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = SAMPLE_GEOJSON
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                # When: Call API
                result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])

        # Then: Should succeed
        assert len(result) == 1

        # And: Log should contain success with latency
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the success log
        success_logs = [line for line in log_lines if 'succeeded' in line.lower()]
        assert len(success_logs) > 0, "No API success log found"

        # Parse the JSON log
        log_data = json.loads(success_logs[0].strip())

        # Verify structured fields
        assert log_data["message"] == "External API call succeeded"
        assert log_data["service"] == "openrouteservice"
        assert "endpoint" in log_data
        assert "profile" in log_data
        assert log_data["profile"] == "driving-car"
        assert "latency_ms" in log_data
        assert log_data["latency_ms"] > 0
        assert log_data["success"] is True

    def test_retry_logged_with_details(self, monkeypatch, app_config):
        """Test that retry attempts log structured details."""
        monkeypatch.setenv("LOG_FORMAT", "json")

        from innsight.logging_config import configure_logging

        log_output = StringIO()
        configure_logging(app_config, stream=log_output)

        # Mock: First call fails with Timeout, second succeeds
        with patch.dict(os.environ, TEST_ENV):
            with patch('requests.post') as mock_post:
                # First call raises Timeout
                timeout_error = Timeout("Connection timed out")

                # Second call succeeds
                success_response = Mock()
                success_response.status_code = 200
                success_response.json.return_value = SAMPLE_GEOJSON
                success_response.raise_for_status.return_value = None

                mock_post.side_effect = [timeout_error, success_response]

                # When: Call API (will retry once)
                with patch('time.sleep'):  # Skip actual sleep
                    result = get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])

        # Then: Should eventually succeed
        assert len(result) == 1

        # And: Log should contain retry warning
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the retry log
        retry_logs = [line for line in log_lines if 'retrying' in line.lower() or 'retry' in line.lower()]
        assert len(retry_logs) > 0, "No retry log found"

        # Parse the JSON log
        log_data = json.loads(retry_logs[0].strip())

        # Verify structured fields
        assert "retry" in log_data["message"].lower() or "retrying" in log_data["message"].lower()
        assert log_data["service"] == "openrouteservice"
        assert "attempt" in log_data
        assert log_data["attempt"] == 1
        assert "max_attempts" in log_data
        assert log_data["max_attempts"] == 3
        assert "error_type" in log_data
        assert log_data["error_type"] == "Timeout"
        assert "retry_delay_seconds" in log_data

    def test_failure_logged_with_error_type(self, monkeypatch, app_config):
        """Test that final failure logs include error type and total attempts."""
        monkeypatch.setenv("LOG_FORMAT", "json")

        from innsight.logging_config import configure_logging

        log_output = StringIO()
        configure_logging(app_config, stream=log_output)

        # Mock: All attempts fail with Timeout
        with patch.dict(os.environ, TEST_ENV):
            with patch('requests.post') as mock_post:
                mock_post.side_effect = Timeout("Connection timed out")

                # When: Call API (will fail after retries)
                with patch('time.sleep'):  # Skip actual sleep
                    with pytest.raises(IsochroneError):
                        get_isochrones_by_minutes(coord=TEST_COORD, intervals=[15])

        # Then: Log should contain final failure
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the error log (should be last retry-related log before exception)
        error_logs = [line for line in log_lines if '"level": "error"' in line or '"level":"error"' in line]
        assert len(error_logs) > 0, "No error log found"

        # Parse the JSON log
        log_data = json.loads(error_logs[0].strip())

        # Verify structured fields
        assert "failed" in log_data["message"].lower()
        assert log_data["service"] == "openrouteservice"
        assert "error_type" in log_data
        assert log_data["error_type"] == "Timeout"
        assert "total_attempts" in log_data
        assert log_data["total_attempts"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])