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
    
    def test_openapi_spec_shows_correct_schema(self):
        """Test that OpenAPI spec shows correct request/response schemas."""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        paths = openapi_spec["paths"]
        components = openapi_spec["components"]["schemas"]
        
        # Check POST /recommend exists
        assert "/recommend" in paths
        post_spec = paths["/recommend"]["post"]
        
        # Check request schema references and has correct properties
        request_ref = post_spec["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert request_ref == "#/components/schemas/RecommendRequest"
        
        request_schema = components["RecommendRequest"]
        required_props = request_schema["properties"]
        assert "query" in required_props
        assert "weights" in required_props  
        assert "top_n" in required_props
        
        # Check response schema references and has correct properties
        response_ref = post_spec["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert response_ref == "#/components/schemas/RecommendResponse"
        
        response_schema = components["RecommendResponse"]  
        response_props = response_schema["properties"]
        assert "stats" in response_props
        assert "top" in response_props
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_response_format_stats_and_top(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test that response has stats (tier counts) and top (recommendations array)."""
        # Arrange
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'score': [85.0, 75.0, 65.0],
            'tier': [1, 2, 0],
            'lat': [25.0330, 25.0340, 25.0350],
            'lon': [121.5654, 121.5664, 121.5674],
            'tags': [{}, {}, {}]
        })
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = mock_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "我想去沖繩水族館 待兩天 要無障礙"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "stats" in data
        assert "top" in data
        assert "success" not in data  # Old format should not be present
        assert "accommodations" not in data  # Old format should not be present
        
        # Check stats has tier counts  
        stats = data["stats"]
        assert stats["tier_0"] == 1
        assert stats["tier_1"] == 1
        assert stats["tier_2"] == 1
        assert stats["tier_3"] == 0
        
        # Check top is array with correct length
        top = data["top"]
        assert isinstance(top, list)
        assert len(top) == 3
    
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