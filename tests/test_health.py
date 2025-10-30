"""Tests for external API health check functions."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

# Import functions that will be implemented
# from innsight.health import (
#     check_nominatim_health,
#     check_ors_health,
#     check_overpass_health,
#     HealthCheckResult
# )


class TestNominatimHealthCheck:
    """Test health checks for Nominatim API."""

    async def test_nominatim_returns_healthy_on_success(self):
        """Should return healthy status when API responds with 200."""
        # This test will fail until we implement the function
        from innsight.health import check_nominatim_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_get.return_value = mock_response

            result = await check_nominatim_health("https://nominatim.example.com")

            assert result["service"] == "nominatim"
            assert result["healthy"] is True
            assert result["status_code"] == 200
            assert result["response_time_ms"] > 0
            assert result["error"] is None

    async def test_nominatim_returns_unhealthy_on_timeout(self):
        """Should return unhealthy status when API times out."""
        from innsight.health import check_nominatim_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            result = await check_nominatim_health("https://nominatim.example.com", timeout=3.0)

            assert result["service"] == "nominatim"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None
            assert "timeout" in result["error"].lower()

    async def test_nominatim_returns_unhealthy_on_http_error(self):
        """Should return unhealthy status when API returns 4xx/5xx."""
        from innsight.health import check_nominatim_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 503

            # Create the exception with the response
            http_error = httpx.HTTPStatusError(
                "Service unavailable",
                request=AsyncMock(),
                response=mock_response
            )

            # Make raise_for_status raise the exception
            def raise_error():
                raise http_error

            mock_response.raise_for_status = raise_error
            mock_get.return_value = mock_response

            result = await check_nominatim_health("https://nominatim.example.com")

            assert result["service"] == "nominatim"
            assert result["healthy"] is False
            assert result["status_code"] == 503
            assert result["error"] is not None

    async def test_nominatim_returns_unhealthy_on_connection_error(self):
        """Should return unhealthy status when connection fails."""
        from innsight.health import check_nominatim_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await check_nominatim_health("https://nominatim.example.com")

            assert result["service"] == "nominatim"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None
            assert "connection" in result["error"].lower()


class TestORSHealthCheck:
    """Test health checks for OpenRouteService API."""

    async def test_ors_returns_healthy_on_success(self):
        """Should return healthy status when API responds with 200."""
        from innsight.health import check_ors_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.3
            mock_get.return_value = mock_response

            result = await check_ors_health("https://ors.example.com")

            assert result["service"] == "ors"
            assert result["healthy"] is True
            assert result["status_code"] == 200
            assert result["response_time_ms"] > 0
            assert result["error"] is None

    async def test_ors_returns_unhealthy_on_timeout(self):
        """Should return unhealthy status when API times out."""
        from innsight.health import check_ors_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            result = await check_ors_health("https://ors.example.com", timeout=3.0)

            assert result["service"] == "ors"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None
            assert "timeout" in result["error"].lower()

    async def test_ors_returns_unhealthy_on_http_error(self):
        """Should return unhealthy status when API returns 4xx/5xx."""
        from innsight.health import check_ors_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 500

            # Create the exception with the response
            http_error = httpx.HTTPStatusError(
                "Internal server error",
                request=AsyncMock(),
                response=mock_response
            )

            # Make raise_for_status raise the exception
            def raise_error():
                raise http_error

            mock_response.raise_for_status = raise_error
            mock_get.return_value = mock_response

            result = await check_ors_health("https://ors.example.com")

            assert result["service"] == "ors"
            assert result["healthy"] is False
            assert result["status_code"] == 500
            assert result["error"] is not None

    async def test_ors_returns_unhealthy_on_connection_error(self):
        """Should return unhealthy status when connection fails."""
        from innsight.health import check_ors_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await check_ors_health("https://ors.example.com")

            assert result["service"] == "ors"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None


class TestOverpassHealthCheck:
    """Test health checks for Overpass API."""

    async def test_overpass_returns_healthy_on_success(self):
        """Should return healthy status when API responds with 200."""
        from innsight.health import check_overpass_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.4
            mock_get.return_value = mock_response

            result = await check_overpass_health("https://overpass.example.com")

            assert result["service"] == "overpass"
            assert result["healthy"] is True
            assert result["status_code"] == 200
            assert result["response_time_ms"] > 0
            assert result["error"] is None

    async def test_overpass_returns_unhealthy_on_timeout(self):
        """Should return unhealthy status when API times out."""
        from innsight.health import check_overpass_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            result = await check_overpass_health("https://overpass.example.com", timeout=3.0)

            assert result["service"] == "overpass"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None
            assert "timeout" in result["error"].lower()

    async def test_overpass_returns_unhealthy_on_http_error(self):
        """Should return unhealthy status when API returns 4xx/5xx."""
        from innsight.health import check_overpass_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 429

            # Create the exception with the response
            http_error = httpx.HTTPStatusError(
                "Too many requests",
                request=AsyncMock(),
                response=mock_response
            )

            # Make raise_for_status raise the exception
            def raise_error():
                raise http_error

            mock_response.raise_for_status = raise_error
            mock_get.return_value = mock_response

            result = await check_overpass_health("https://overpass.example.com")

            assert result["service"] == "overpass"
            assert result["healthy"] is False
            assert result["status_code"] == 429
            assert result["error"] is not None

    async def test_overpass_returns_unhealthy_on_connection_error(self):
        """Should return unhealthy status when connection fails."""
        from innsight.health import check_overpass_health

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await check_overpass_health("https://overpass.example.com")

            assert result["service"] == "overpass"
            assert result["healthy"] is False
            assert result["status_code"] is None
            assert result["error"] is not None
