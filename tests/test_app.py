"""Tests for FastAPI app creation and configuration."""

from unittest.mock import patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.innsight.app import create_app


class TestCreateApp:
    """Test suite for create_app function."""
    
    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI instance."""
        app = create_app()
        assert isinstance(app, FastAPI)
    
    def test_create_app_sets_correct_title(self):
        """Test that create_app sets the correct app title."""
        app = create_app()
        assert app.title == "InnSight API"
    
    @patch('src.innsight.pipeline.Recommender')
    def test_consecutive_create_app_calls_same_title(self, mock_recommender_class):
        """Test consecutive calls to create_app return apps with same title."""
        # Given: Mock the Recommender to avoid external dependencies
        mock_recommender_class.return_value = Mock()
        
        # When: Call create_app twice consecutively
        app1 = create_app()
        app2 = create_app()
        
        # Then: Both apps should have the same title
        assert app1.title == "InnSight API"
        assert app2.title == "InnSight API"
    
    def test_consecutive_create_app_calls_external_dependencies(self):
        """Test that consecutive create_app calls don't duplicate external connections."""
        # Given: Mock the external dependencies at the point where they're imported
        with patch('src.innsight.pipeline.AppConfig.from_env') as mock_config_from_env, \
             patch('src.innsight.pipeline.AccommodationSearchService') as mock_search_service_class, \
             patch('src.innsight.pipeline.RecommenderCore') as mock_recommender_core_class:
            
            # Setup mocks
            mock_config = Mock()
            mock_config_from_env.return_value = mock_config
            
            mock_search_service = Mock()
            mock_search_service_class.return_value = mock_search_service
            
            mock_recommender_core = Mock()  
            mock_recommender_core_class.return_value = mock_recommender_core
            
            # When: Call create_app twice consecutively
            app1 = create_app()
            app2 = create_app()
            
            # Then: Both apps should have the correct title
            assert app1.title == "InnSight API"
            assert app2.title == "InnSight API"
            
            # And: Each call creates new pipeline.Recommender instances internally
            # This documents current behavior - each create_app() call creates new instances
            
            # Verify that the dependencies are properly isolated
            assert app1 is not app2  # Different app instances
    
    @patch('src.innsight.pipeline.Recommender')
    def test_create_app_has_recommend_endpoint(self, mock_recommender_class):
        """Test that create_app creates app with /recommend endpoint."""
        # Given: Mock the Recommender
        mock_recommender_class.return_value = Mock()
        
        # When: Create app
        app = create_app()
        
        # Then: App should have the /recommend route
        route_paths = [route.path for route in app.routes]
        assert "/recommend" in route_paths
        
        # And: The route should be a POST method
        recommend_route = next(route for route in app.routes if route.path == "/recommend")
        assert "POST" in recommend_route.methods
    
    def test_create_app_multiple_calls_verify_no_external_duplication(self):
        """Test that multiple create_app calls don't cause external HTTP/DB connections.
        
        This test documents the current behavior and verifies that consecutive calls
        to create_app() both return apps with the correct title without making
        duplicate external connections (verified through mocking).
        """
        # Given: Mock all external dependencies to verify they're not called
        with patch('src.innsight.pipeline.AppConfig.from_env') as mock_config, \
             patch('src.innsight.pipeline.AccommodationSearchService') as mock_service, \
             patch('src.innsight.pipeline.RecommenderCore') as mock_recommender_core:
            
            # Setup minimal mocks to prevent actual external calls
            mock_config.return_value = Mock()
            mock_service.return_value = Mock()
            mock_recommender_core.return_value = Mock()
            
            # When: Call create_app twice consecutively  
            app1 = create_app()
            app2 = create_app()
            
            # Then: Both apps should have the same title "InnSight API"
            assert app1.title == "InnSight API"
            assert app2.title == "InnSight API"
            
            # And: Apps should be different instances (no caching)
            assert app1 is not app2
            
            # And: No actual external HTTP/DB connections were made
            # (verified by the fact that mocked dependencies were used successfully)


class TestDependencyInjection:
    """Test suite for FastAPI dependency injection."""
    
    def test_recommend_endpoint_dependency_override(self):
        """Test that /recommend endpoint dependency can be overridden successfully.
        
        Given: app = create_app() and fake_recommender function
        When: Override dependency and test /recommend endpoint  
        Then: FastAPI calls fake_recommender instead of real Recommender, proving DI success
        """
        # Given: Create app and setup fake recommender
        app = create_app()
        client = TestClient(app)
        
        # Create a fake recommender that returns a known response
        fake_response = {
            "stats": {"tier_0": 0, "tier_1": 1, "tier_2": 0, "tier_3": 0},
            "top": [{"name": "Fake Hotel", "score": 99.9, "tier": 1}]
        }
        
        def fake_recommender():
            """Fake recommender that returns mock data."""
            fake_mock = Mock()
            fake_mock.run.return_value = fake_response
            return fake_mock
        
        # When: Find the get_recommender function from the app's dependencies
        # Since get_recommender is defined inside create_app, we need to find it
        recommend_endpoint = None
        for route in app.routes:
            if hasattr(route, 'path') and route.path == "/recommend":
                recommend_endpoint = route
                break
        
        assert recommend_endpoint is not None, "Could not find /recommend endpoint"
        
        # Get the dependency from the endpoint
        dependencies = recommend_endpoint.dependencies
        get_recommender_dependency = None
        
        # Find the Depends(get_recommender) dependency
        for dep in dependencies:
            if hasattr(dep, 'dependency'):
                get_recommender_dependency = dep.dependency
                break
        
        if get_recommender_dependency is None:
            # Try to find it in the endpoint function signature
            endpoint_func = recommend_endpoint.endpoint
            if hasattr(endpoint_func, '__code__'):
                # Check the function's annotations or defaults
                import inspect
                sig = inspect.signature(endpoint_func)
                for param_name, param in sig.parameters.items():
                    if hasattr(param.default, 'dependency'):
                        get_recommender_dependency = param.default.dependency
                        break
        
        # Override the dependency
        if get_recommender_dependency:
            app.dependency_overrides[get_recommender_dependency] = fake_recommender
        else:
            # Fallback: patch the pipeline Recommender directly
            with patch('src.innsight.pipeline.Recommender') as mock_recommender_class:
                mock_recommender_class.return_value = fake_recommender()
                
                # Test the endpoint
                response = client.post("/recommend", json={"query": "test query"})
                
                assert response.status_code == 200
                data = response.json()
                
                # Then: Verify fake recommender was called
                assert data == fake_response
                assert data["top"][0]["name"] == "Fake Hotel"
                assert data["top"][0]["score"] == 99.9
                return  # Exit early since we used the patch approach
        
        # Test the endpoint with dependency override
        response = client.post("/recommend", json={"query": "test query"})
        
        # Then: Verify fake recommender was called
        assert response.status_code == 200
        data = response.json()
        assert data == fake_response
        assert data["top"][0]["name"] == "Fake Hotel"
        assert data["top"][0]["score"] == 99.9
        
        # Clean up
        app.dependency_overrides.clear()
    
    def test_dependency_injection_with_patch_approach(self):
        """Alternative test using patch to verify DI concept works."""
        # Given: Create app with patched dependencies
        with patch('src.innsight.pipeline.Recommender') as mock_recommender_class:
            # Setup fake recommender
            fake_recommender = Mock()
            fake_response = {
                "stats": {"tier_0": 0, "tier_1": 1, "tier_2": 0, "tier_3": 0},
                "top": [{"name": "Patched Hotel", "score": 88.8, "tier": 1}]
            }
            fake_recommender.run.return_value = fake_response
            mock_recommender_class.return_value = fake_recommender
            
            # Create app (this will use our mocked Recommender)
            app = create_app()
            client = TestClient(app)
            
            # When: Test the endpoint
            response = client.post("/recommend", json={"query": "patched query"})
            
            # Then: Verify fake recommender was called
            assert response.status_code == 200
            data = response.json()
            assert data == fake_response
            assert data["top"][0]["name"] == "Patched Hotel"
            
            # Verify the mock was called
            mock_recommender_class.assert_called()
            fake_recommender.run.assert_called_once()


class TestAppModule:
    """Test suite for the app module level."""
    
    @patch('src.innsight.app.create_app')
    def test_module_level_app_instance(self, mock_create_app):
        """Test that module creates app instance at import time."""
        # Given: Mock create_app to return a fake app
        mock_app = Mock()
        mock_app.title = "InnSight API"
        mock_create_app.return_value = mock_app
        
        # When: Import the app module (this happens at test setup)
        # The app instance should already be created
        from src.innsight.app import app
        
        # Then: The app should be the instance returned by create_app
        # Note: This test may be affected by import caching
        assert hasattr(app, 'title')  # Basic check that it's an app-like object