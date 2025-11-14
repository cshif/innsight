"""Tests for rate limiting functionality."""

import pytest
from fastapi.testclient import TestClient


class TestRateLimiting:
    """Test rate limiting on API endpoints."""

    def test_rate_limit_on_recommend_endpoint(self, monkeypatch):
        """Test that /recommend endpoint is rate limited to 10 requests per minute in production."""
        # Set up production environment
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("FRONTEND_URL", "https://example.com")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test_key")

        # Import after setting env vars
        from innsight.app import create_app

        app = create_app()
        client = TestClient(app)

        # Valid request payload
        payload = {
            "query": "台北火鍋",
            "latitude": 25.0330,
            "longitude": 121.5654
        }

        # Make 10 requests (should all succeed or fail with validation error, but not rate limit)
        responses = []
        for i in range(10):
            response = client.post("/recommend", json=payload)
            responses.append(response.status_code)

        # First 10 requests should not be rate limited
        # They might return 200 (success) or 400 (validation error), but not 429
        assert all(status_code != 429 for status_code in responses), \
            f"First 10 requests should not be rate limited, got: {responses}"

        # 11th request should be rate limited
        response = client.post("/recommend", json=payload)
        assert response.status_code == 429, \
            f"11th request should be rate limited (429), got: {response.status_code}"

        # Check error response format
        data = response.json()
        assert "error" in data
        assert "Rate Limit" in data["error"]
        assert "message" in data

        # Check Retry-After header
        assert "retry-after" in response.headers or "Retry-After" in response.headers
