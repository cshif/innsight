"""Tests for health check API endpoints."""

from fastapi.testclient import TestClient
from datetime import datetime
import tomllib
from unittest.mock import patch, AsyncMock

from src.innsight.app import create_app


class TestHealthEndpoint:
    """Test suite for /api/health endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_health_endpoint_exists(self):
        """Should return 200 when accessing /api/health."""
        response = self.client.get("/api/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self):
        """Should return JSON content type."""
        response = self.client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_health_endpoint_has_required_fields(self):
        """Should return status, timestamp, and version fields."""
        response = self.client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data

    def test_health_endpoint_status_is_healthy(self):
        """Should return status as 'healthy'."""
        response = self.client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_timestamp_is_valid_iso8601(self):
        """Should return valid ISO 8601 timestamp."""
        response = self.client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        timestamp = data["timestamp"]

        # Try to parse the timestamp as ISO 8601
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            assert False, f"Invalid ISO 8601 timestamp: {timestamp}"

    def test_health_endpoint_version_matches_project(self):
        """Should return version matching pyproject.toml."""
        # Read version from pyproject.toml
        with open("pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)
            expected_version = pyproject["project"]["version"]

        response = self.client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == expected_version

    def test_health_endpoint_response_is_fast(self):
        """Should respond quickly (under 100ms)."""
        import time

        start = time.time()
        response = self.client.get("/api/health")
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200
        assert elapsed < 100, f"Health check took {elapsed}ms, expected < 100ms"


class TestReadyEndpoint:
    """Test suite for /api/ready endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_all_services_healthy(self, mock_nominatim, mock_ors, mock_overpass):
        """Should return 200 and 'ready' status when all services are healthy."""
        # Mock all services as healthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": 123.0,
            "status_code": 200,
            "error": None
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_nominatim_unhealthy(self, mock_nominatim, mock_ors, mock_overpass):
        """Should return 503 and 'not_ready' status when Nominatim is unhealthy."""
        # Mock Nominatim as unhealthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": 3000.0,
            "status_code": None,
            "error": "Connection timeout"
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_multiple_services_unhealthy(self, mock_nominatim, mock_ors, mock_overpass):
        """Should return 503 when multiple services are unhealthy."""
        # Mock multiple services as unhealthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": 3000.0,
            "status_code": None,
            "error": "Connection timeout"
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": False,
            "response_time_ms": 3000.0,
            "status_code": 503,
            "error": "HTTP error: Service unavailable"
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_has_required_fields(self, mock_nominatim, mock_ors, mock_overpass):
        """Should return all required fields in response."""
        # Mock all services as healthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": 123.0,
            "status_code": 200,
            "error": None
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")
        data = response.json()

        # Check required top-level fields
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_includes_all_services(self, mock_nominatim, mock_ors, mock_overpass):
        """Should include all three external services in response."""
        # Mock all services as healthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": 123.0,
            "status_code": 200,
            "error": None
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")
        data = response.json()

        services = data["services"]
        assert "nominatim" in services
        assert "ors" in services
        assert "overpass" in services

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_service_details_when_healthy(self, mock_nominatim, mock_ors, mock_overpass):
        """Should include service details with healthy status."""
        # Mock all services as healthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": 123.0,
            "status_code": 200,
            "error": None
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")
        data = response.json()

        services = data["services"]

        # Check Nominatim details
        assert services["nominatim"]["healthy"] is True
        assert "response_time_ms" in services["nominatim"]

        # Check ORS details
        assert services["ors"]["healthy"] is True
        assert "response_time_ms" in services["ors"]

        # Check Overpass details
        assert services["overpass"]["healthy"] is True
        assert "response_time_ms" in services["overpass"]

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_service_details_when_unhealthy(self, mock_nominatim, mock_ors, mock_overpass):
        """Should include error details when service is unhealthy."""
        # Mock Nominatim as unhealthy with error
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": 3000.0,
            "status_code": None,
            "error": "Connection timeout"
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")
        data = response.json()

        services = data["services"]

        # Check Nominatim has error details
        assert services["nominatim"]["healthy"] is False
        assert "error" in services["nominatim"]
        assert services["nominatim"]["error"] == "Connection timeout"

    @patch('src.innsight.health.check_overpass_health')
    @patch('src.innsight.health.check_ors_health')
    @patch('src.innsight.health.check_nominatim_health')
    def test_ready_timestamp_is_valid_iso8601(self, mock_nominatim, mock_ors, mock_overpass):
        """Should return valid ISO 8601 timestamp."""
        # Mock all services as healthy
        mock_nominatim.return_value = {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": 123.0,
            "status_code": 200,
            "error": None
        }
        mock_ors.return_value = {
            "service": "ors",
            "healthy": True,
            "response_time_ms": 456.0,
            "status_code": 200,
            "error": None
        }
        mock_overpass.return_value = {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": 789.0,
            "status_code": 200,
            "error": None
        }

        response = self.client.get("/api/ready")
        data = response.json()

        timestamp = data["timestamp"]

        # Try to parse the timestamp as ISO 8601
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            assert False, f"Invalid ISO 8601 timestamp: {timestamp}"
