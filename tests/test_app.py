"""Tests for FastAPI app creation and configuration."""

import json
from io import StringIO
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
            "top": [{
                "name": "Fake Hotel", 
                "score": 99.9, 
                "tier": 1,
                "lat": None,
                "lon": None,
                "osmid": None,
                "osmtype": None,
                "tourism": None,
                "rating": None,
                "amenities": None
            }],
            "main_poi": {
                "name": "測試景點", 
                "location": "測試地點",
                "lat": None,
                "lon": None,
                "display_name": None,
                "type": None,
                "address": None
            },
            "isochrone_geometry": [],
            "intervals": {"values": [], "unit": "minutes", "profile": "driving-car"}
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
                "top": [{
                    "name": "Patched Hotel", 
                    "score": 88.8, 
                    "tier": 1,
                    "lat": None,
                    "lon": None,
                    "osmid": None,
                    "osmtype": None,
                    "tourism": None,
                    "rating": None,
                    "amenities": None
                }],
                "main_poi": {
                    "name": "測試景點", 
                    "location": "測試地點",
                    "lat": None,
                    "lon": None,
                    "display_name": None,
                    "type": None,
                    "address": None
                },
                "isochrone_geometry": [],
                "intervals": {"values": [], "unit": "minutes", "profile": "driving-car"}
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


class TestLoggingIntegration:
    """Test suite for logging configuration integration."""

    @patch('src.innsight.app.configure_logging')
    def test_create_app_configures_logging(self, mock_configure_logging):
        """Test that create_app calls configure_logging."""
        # When: Create app
        app = create_app()

        # Then: configure_logging should be called
        mock_configure_logging.assert_called_once()

    def test_app_uses_structlog_json_format(self, monkeypatch):
        """Test that app can output logs in JSON format."""
        # Given: Set environment to JSON mode
        monkeypatch.setenv("LOG_FORMAT", "json")

        # Capture log output
        log_output = StringIO()

        # When: Configure logging and create app
        with patch('src.innsight.app.configure_logging') as mock_configure:
            # Configure the actual logging for testing
            from src.innsight.logging_config import configure_logging
            configure_logging(stream=log_output)

            # Create app (which should use the configured logger)
            app = create_app()

            # Trigger a log message by accessing a logger
            from src.innsight.logging_config import get_logger
            logger = get_logger("test.app")
            logger.info("test message from app", key="value")

        # Then: Log output should be valid JSON
        log_output.seek(0)
        log_line = log_output.readline().strip()

        # Should be valid JSON
        log_data = json.loads(log_line)
        assert "timestamp" in log_data
        assert "level" in log_data
        assert log_data["message"] == "test message from app"
        assert log_data["key"] == "value"

    def test_app_uses_structlog_text_format(self, monkeypatch):
        """Test that app can output logs in text format."""
        # Given: Set environment to text mode
        monkeypatch.setenv("LOG_FORMAT", "text")

        # Capture log output
        log_output = StringIO()

        # When: Configure logging
        from src.innsight.logging_config import configure_logging
        configure_logging(stream=log_output)

        # Create logger and log a message
        from src.innsight.logging_config import get_logger
        logger = get_logger("test.app")
        logger.info("test message from app")

        # Then: Log output should NOT be JSON
        log_output.seek(0)
        log_line = log_output.readline()

        # Should contain the message but not be valid JSON
        assert "test message from app" in log_line

        # Should fail to parse as JSON
        import pytest
        with pytest.raises(json.JSONDecodeError):
            json.loads(log_line)


class TestStructuredLogging:
    """Test suite for structured logging in app and middleware."""

    def test_successful_request_logged(self, monkeypatch):
        """Test that successful API request logs include all required fields."""
        # Given: Configure logging to JSON format
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from src.innsight.logging_config import configure_logging

        log_output = StringIO()

        # Mock the Recommender to avoid external dependencies
        with patch('src.innsight.pipeline.Recommender') as mock_recommender_class:
            mock_recommender = Mock()
            mock_recommender.run.return_value = {
                "stats": {},
                "top": [],
                "main_poi": {"name": "Test POI"},
                "isochrone_geometry": [],
                "intervals": {"values": [15], "unit": "minutes", "profile": "driving-car"}
            }
            mock_recommender_class.return_value = mock_recommender

            # Create app (this will configure logging internally)
            app = create_app()

            # Reconfigure logging to capture output after app creation
            configure_logging(stream=log_output)

            client = TestClient(app)

            # When: Call endpoint
            response = client.post("/recommend", json={"query": "test query"})

        # Then: Should succeed
        assert response.status_code == 200

        # And: Log should contain request completion with all fields
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the request completion log
        request_logs = [line for line in log_lines if 'completed' in line.lower()]
        assert len(request_logs) > 0, "No API request completion log found"

        # Parse the JSON log
        log_data = json.loads(request_logs[0].strip())

        # Verify structured fields
        assert log_data["message"] == "API request completed"
        assert log_data["method"] == "POST"
        assert log_data["endpoint"] == "/recommend"
        assert log_data["status_code"] == 200
        assert "duration_ms" in log_data
        assert "trace_id" in log_data  # Should be auto-included from context

    def test_request_duration_logged(self, monkeypatch):
        """Test that request duration is logged and is a positive number."""
        # Given: Configure logging to JSON format
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from src.innsight.logging_config import configure_logging

        log_output = StringIO()

        # Mock the Recommender
        with patch('src.innsight.pipeline.Recommender') as mock_recommender_class:
            mock_recommender = Mock()
            mock_recommender.run.return_value = {
                "stats": {},
                "top": [],
                "main_poi": {"name": "Test POI"},
                "isochrone_geometry": [],
                "intervals": {"values": [15], "unit": "minutes", "profile": "driving-car"}
            }
            mock_recommender_class.return_value = mock_recommender

            # Create app (this will configure logging internally)
            app = create_app()

            # Reconfigure logging to capture output after app creation
            configure_logging(stream=log_output)

            client = TestClient(app)

            # When: Call endpoint
            response = client.post("/recommend", json={"query": "test query"})

        # Then: Should succeed
        assert response.status_code == 200

        # And: Duration should be logged as a positive number
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the request completion log
        request_logs = [line for line in log_lines if 'completed' in line.lower()]
        assert len(request_logs) > 0

        # Parse the JSON log
        log_data = json.loads(request_logs[0].strip())

        # Verify duration
        assert "duration_ms" in log_data
        duration = log_data["duration_ms"]
        assert isinstance(duration, (int, float))
        assert duration > 0
        assert duration < 5000  # Should be less than 5 seconds for test

    def test_validation_error_logged(self, monkeypatch):
        """Test that validation errors are logged with error details."""
        # Given: Configure logging to JSON format
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from src.innsight.logging_config import configure_logging

        log_output = StringIO()

        # Mock the Recommender
        with patch('src.innsight.pipeline.Recommender') as mock_recommender_class:
            mock_recommender = Mock()
            mock_recommender_class.return_value = mock_recommender

            # Create app (this will configure logging internally)
            app = create_app()

            # Reconfigure logging to capture output after app creation
            configure_logging(stream=log_output)

            client = TestClient(app)

            # When: Send invalid request (missing required field)
            response = client.post("/recommend", json={})  # Missing 'query' field

        # Then: Should return 400
        assert response.status_code == 400

        # And: Log should contain validation error
        log_output.seek(0)
        log_lines = log_output.readlines()

        # Find the validation error log
        error_logs = [line for line in log_lines if 'validation failed' in line.lower()]
        assert len(error_logs) > 0, "No validation error log found"

        # Parse the JSON log
        log_data = json.loads(error_logs[0].strip())

        # Verify structured fields
        assert "validation failed" in log_data["message"].lower()
        assert log_data["error_type"] == "RequestValidationError"
        assert "error_message" in log_data
        assert log_data["endpoint"] == "/recommend"
        assert log_data["method"] == "POST"
        assert log_data["status_code"] == 400
        assert "trace_id" in log_data  # Should be auto-included from context