import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from scripts.ors_client import get_isochrones_by_minutes
from shapely.geometry import Polygon


class TestGetIsochronesByMinutes:
    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_by_minutes_success(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
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
        mock_post.return_value = mock_response
        
        # Act
        result = get_isochrones_by_minutes(
            coord=(8.681495, 49.41461),
            intervals=[15, 30]
        )
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 2  # 兩個時間間隔
        assert all(isinstance(iso_list, list) for iso_list in result)
        assert all(len(iso_list) == 1 for iso_list in result)  # 每個間隔一個多邊形
        assert all(isinstance(iso_list[0], Polygon) for iso_list in result)
        
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/driving-car",
            json={
                "locations": ((8.681495, 49.41461),),
                "range": (900, 1800)  # 15*60, 30*60
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
    def test_get_isochrones_by_minutes_caching(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        get_isochrones_by_minutes.cache_clear()
        
        # Act - 兩次相同調用
        result1 = get_isochrones_by_minutes(
            coord=(8.681495, 49.41461),
            intervals=[15]
        )
        
        result2 = get_isochrones_by_minutes(
            coord=(8.681495, 49.41461), 
            intervals=[15]
        )
        
        # Assert
        assert mock_post.call_count == 1  # 只調用一次API，第二次使用快取
        assert result1 == result2
        
        # 檢查快取資訊 - 快取發生在底層 _fetch_isochrones_from_api 函數上
        cache_info = get_isochrones_by_minutes.cache_info()
        assert cache_info['size'] == 1

    @patch.dict(os.environ, {'ORS_URL': 'https://api.openrouteservice.org/v2/directions', 'ORS_API_KEY': 'test_key'})
    @patch('requests.post')
    def test_get_isochrones_by_minutes_different_profile(self, mock_post):
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"features": []}
        mock_post.return_value = mock_response
        
        # Act
        result = get_isochrones_by_minutes(
            coord=(8.681495, 49.41461),
            intervals=[10],
            profile='foot-walking'
        )
        
        # Assert
        mock_post.assert_called_once_with(
            url="https://api.openrouteservice.org/v2/directions/isochrones/foot-walking",
            json={
                "locations": ((8.681495, 49.41461),),
                "range": (600,)  # 10*60
            },
            headers={
                "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "test_key"
            },
            timeout=(5, 30)
        )
        
        assert result == []