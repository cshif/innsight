"""Tests for health check API endpoints."""

from fastapi.testclient import TestClient
from datetime import datetime
import tomllib

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
