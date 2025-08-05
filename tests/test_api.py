"""Tests for FastAPI /recommend endpoint."""

from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import geopandas as gpd

from src.innsight.app import create_app


class TestRecommendAPI:
    """Test suite for /recommend API endpoint."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_recommend_success(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test successful recommendation request."""
        # Arrange
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],
            'score': [85.0, 75.0],
            'tier': [1, 2],
            'lat': [25.0330, 25.0340],
            'lon': [121.5654, 121.5664],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'}
            ]
        })
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = mock_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "台北101",
            "filters": ["parking"],
            "top_n": 5
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["total_found"] == 2
        assert data["query"] == "台北101"
        assert len(data["accommodations"]) == 2
        
        # Check first accommodation data
        first_hotel = data["accommodations"][0]
        assert first_hotel["name"] == "Hotel A"
        assert first_hotel["score"] == 85.0
        assert first_hotel["tier"] == 1
        assert first_hotel["lat"] == 25.0330
        assert first_hotel["lon"] == 121.5654
        assert first_hotel["amenities"]["parking"] == "yes"
        
        # Verify recommender was called with correct parameters
        mock_recommender.recommend.assert_called_once_with("台北101", ["parking"], 5)
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_recommend_empty_query(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test recommendation with empty query."""
        # Act
        response = self.client.post("/recommend", json={
            "query": "",
            "top_n": 10
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "Query parameter is required"
        assert data["accommodations"] == []
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_recommend_no_results(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test recommendation when no accommodations found."""
        # Arrange
        empty_gdf = gpd.GeoDataFrame()
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = empty_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "不存在的地點"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["total_found"] == 0
        assert data["accommodations"] == []
        assert data["query"] == "不存在的地點"
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_recommend_with_exception(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test recommendation when service throws exception."""
        # Arrange
        mock_recommender = Mock()
        mock_recommender.recommend.side_effect = Exception("Search service error")
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "台北101"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "Search service error"
        assert data["accommodations"] == []
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_recommend_default_parameters(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test recommendation with default parameters."""
        # Arrange
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [1],
            'lat': [25.0330],
            'lon': [121.5654],
            'tags': [{'parking': 'yes'}]
        })
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = mock_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "台北101"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # Verify default parameters were used
        mock_recommender.recommend.assert_called_once_with("台北101", None, 10)
    
    def test_recommend_invalid_json(self):
        """Test recommendation with invalid JSON."""
        # Act
        response = self.client.post("/recommend", content="invalid json")
        
        # Assert
        assert response.status_code == 422  # Unprocessable Entity