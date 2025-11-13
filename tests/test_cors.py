"""Tests for CORS configuration based on environment."""

import pytest
from fastapi.testclient import TestClient


def test_cors_in_production(monkeypatch):
    """Test that CORS is restricted in production environment."""
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

    # Test request from allowed origin
    response = client.get(
        "/health",
        headers={"Origin": "https://example.com"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "https://example.com"

    # Test request from disallowed origin
    response = client.get(
        "/health",
        headers={"Origin": "https://evil.com"}
    )

    # CORS middleware will not include the evil origin in headers
    assert response.status_code == 200
    # When origin is not allowed, CORS middleware doesn't add the header
    # or doesn't include the requesting origin
    if "access-control-allow-origin" in response.headers:
        assert response.headers["access-control-allow-origin"] != "https://evil.com"


def test_cors_in_development(monkeypatch):
    """Test that CORS allows all origins in development environment."""
    # Set up development environment
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("API_ENDPOINT", "http://api")
    monkeypatch.setenv("ORS_URL", "http://ors")
    monkeypatch.setenv("ORS_API_KEY", "test_key")

    # Import after setting env vars
    from innsight.app import create_app

    app = create_app()
    client = TestClient(app)

    # Test request from any origin
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"}
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    # In development, CORS should allow the requested origin (wildcard allows any)
    assert response.headers["access-control-allow-origin"] in ["*", "http://localhost:3000"]


def test_cors_allows_credentials(monkeypatch):
    """Test that CORS allows credentials."""
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("API_ENDPOINT", "http://api")
    monkeypatch.setenv("ORS_URL", "http://ors")
    monkeypatch.setenv("ORS_API_KEY", "test_key")

    from innsight.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"}
    )

    assert "access-control-allow-credentials" in response.headers
    assert response.headers["access-control-allow-credentials"] == "true"