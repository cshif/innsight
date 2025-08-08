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
    def test_field_types_and_ranges(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test that fields have correct types and ranges: score 0-100 float, tier 0-3 int, name str."""
        # Arrange
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Test Hotel'],
            'score': [85.5],  # Float in range 0-100
            'tier': [2],      # Int in range 0-3
            'lat': [25.0330],
            'lon': [121.5654],
            'tags': [{}]
        })
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = mock_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "test query"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Check that we have at least one result
        assert len(data["top"]) >= 1
        first_result = data["top"][0]
        
        # Check field types and ranges
        assert isinstance(first_result["name"], str)
        assert isinstance(first_result["score"], float)
        assert isinstance(first_result["tier"], int)
        
        # Check score is in range 0-100
        assert 0.0 <= first_result["score"] <= 100.0
        
        # Check tier is in range 0-3  
        assert 0 <= first_result["tier"] <= 3
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_field_validation_edge_cases(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test that Pydantic validates fields correctly at boundaries."""
        # Arrange - create data with edge values
        mock_gdf = gpd.GeoDataFrame({
            'name': ['Edge Hotel'],
            'score': [0.0],  # Minimum valid score
            'tier': [3],     # Maximum valid tier
            'lat': [25.0330],
            'lon': [121.5654],
            'tags': [{}]
        })
        
        mock_recommender = Mock()
        mock_recommender.recommend.return_value = mock_gdf
        mock_recommender_class.return_value = mock_recommender
        
        # Act
        response = self.client.post("/recommend", json={
            "query": "test query"
        })
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        first_result = data["top"][0]
        
        # Check boundary values are accepted
        assert first_result["score"] == 0.0
        assert first_result["tier"] == 3
    
    @patch('src.innsight.pipeline.AppConfig.from_env')
    @patch('src.innsight.pipeline.AccommodationSearchService')
    @patch('src.innsight.pipeline.RecommenderCore')
    def test_custom_weights_support(self, mock_recommender_class, mock_search_service_class, mock_config):
        """Test that custom weights are passed to recommender and affect results."""
        # Arrange - Create two different result sets for different weight calls
        default_gdf = gpd.GeoDataFrame({
            'name': ['Hotel B', 'Hotel A'],  # Hotel B has higher score, so it's first
            'score': [85.0, 75.0],
            'tier': [2, 1],
            'lat': [25.0340, 25.0330],
            'lon': [121.5664, 121.5654],
            'tags': [{}, {}]
        })
        
        weighted_gdf = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],  # Hotel A has higher score with weights, so it's first
            'score': [85.0, 75.0],
            'tier': [1, 2],
            'lat': [25.0330, 25.0340], 
            'lon': [121.5654, 121.5664],
            'tags': [{}, {}]
        })
        
        mock_recommender = Mock()
        # Return different results based on weights parameter
        def side_effect(*args, **kwargs):
            # Check the 4th argument (weights) - it's query, filters, top_n, weights
            if len(args) > 3 and args[3] is not None:  # weights parameter
                return weighted_gdf
            return default_gdf
            
        mock_recommender.recommend.side_effect = side_effect
        mock_recommender_class.return_value = mock_recommender
        
        # Act - Make request without weights
        response1 = self.client.post("/recommend", json={
            "query": "test query"
        })
        
        # Act - Make request with weights
        response2 = self.client.post("/recommend", json={
            "query": "test query",
            "weights": {"rating": 10, "tier": 1}
        })
        
        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Results should be different due to weights
        first_hotel_1 = data1["top"][0]["name"]
        first_hotel_2 = data2["top"][0]["name"]
        assert first_hotel_1 != first_hotel_2
        
        # Verify weights were passed correctly
        assert mock_recommender.recommend.call_count == 2
        # First call should have None weights (4th argument)
        first_call_args = mock_recommender.recommend.call_args_list[0][0]
        assert len(first_call_args) >= 4 and first_call_args[3] is None
        
        # Second call should have weights (4th argument)
        second_call_args = mock_recommender.recommend.call_args_list[1][0] 
        assert len(second_call_args) >= 4 and second_call_args[3] is not None
    
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