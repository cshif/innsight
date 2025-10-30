"""Health check functions for external APIs."""

import time
from typing import TypedDict

import httpx


class HealthCheckResult(TypedDict):
    """Result of a health check operation."""
    service: str
    healthy: bool
    response_time_ms: float
    status_code: int | None
    error: str | None


async def check_nominatim_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of Nominatim API.

    Args:
        base_url: Base URL of the Nominatim API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(base_url)
            response.raise_for_status()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "service": "nominatim",
            "healthy": True,
            "response_time_ms": elapsed_ms,
            "status_code": response.status_code,
            "error": None
        }

    except httpx.TimeoutException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Request timeout: {str(e)}"
        }

    except httpx.ConnectError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Connection error: {str(e)}"
        }

    except httpx.HTTPStatusError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": e.response.status_code,
            "error": f"HTTP error: {str(e)}"
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "nominatim",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Unexpected error: {str(e)}"
        }


async def check_ors_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of OpenRouteService API.

    Args:
        base_url: Base URL of the ORS API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(base_url)
            response.raise_for_status()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "service": "ors",
            "healthy": True,
            "response_time_ms": elapsed_ms,
            "status_code": response.status_code,
            "error": None
        }

    except httpx.TimeoutException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "ors",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Request timeout: {str(e)}"
        }

    except httpx.ConnectError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "ors",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Connection error: {str(e)}"
        }

    except httpx.HTTPStatusError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "ors",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": e.response.status_code,
            "error": f"HTTP error: {str(e)}"
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "ors",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Unexpected error: {str(e)}"
        }


async def check_overpass_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of Overpass API.

    Args:
        base_url: Base URL of the Overpass API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(base_url)
            response.raise_for_status()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "service": "overpass",
            "healthy": True,
            "response_time_ms": elapsed_ms,
            "status_code": response.status_code,
            "error": None
        }

    except httpx.TimeoutException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "overpass",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Request timeout: {str(e)}"
        }

    except httpx.ConnectError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "overpass",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Connection error: {str(e)}"
        }

    except httpx.HTTPStatusError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "overpass",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": e.response.status_code,
            "error": f"HTTP error: {str(e)}"
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": "overpass",
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Unexpected error: {str(e)}"
        }
