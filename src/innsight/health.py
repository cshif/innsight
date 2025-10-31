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


async def _check_service_health(
    service_name: str,
    base_url: str,
    timeout: float = 3.0
) -> HealthCheckResult:
    """
    Generic health check for external services.

    Args:
        service_name: Name of the service being checked
        base_url: Base URL of the service
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
            "service": service_name,
            "healthy": True,
            "response_time_ms": elapsed_ms,
            "status_code": response.status_code,
            "error": None
        }

    except httpx.TimeoutException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": service_name,
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Request timeout: {str(e)}"
        }

    except httpx.ConnectError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": service_name,
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Connection error: {str(e)}"
        }

    except httpx.HTTPStatusError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": service_name,
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": e.response.status_code,
            "error": f"HTTP error: {str(e)}"
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "service": service_name,
            "healthy": False,
            "response_time_ms": elapsed_ms,
            "status_code": None,
            "error": f"Unexpected error: {str(e)}"
        }


async def check_nominatim_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of Nominatim API.

    Args:
        base_url: Base URL of the Nominatim API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    return await _check_service_health("nominatim", base_url, timeout)


async def check_ors_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of OpenRouteService API.

    Args:
        base_url: Base URL of the ORS API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    return await _check_service_health("ors", base_url, timeout)


async def check_overpass_health(base_url: str, timeout: float = 3.0) -> HealthCheckResult:
    """
    Check health of Overpass API.

    Args:
        base_url: Base URL of the Overpass API
        timeout: Request timeout in seconds (default: 3.0)

    Returns:
        HealthCheckResult dictionary with service status
    """
    return await _check_service_health("overpass", base_url, timeout)


def get_cache_stats(recommender) -> dict:
    """
    Get cache statistics from Recommender instance.

    Args:
        recommender: Recommender instance with cache statistics

    Returns:
        Dictionary with cache statistics:
        {
            "cache_hits": int,
            "cache_misses": int,
            "cache_hit_rate": float,  # 0.0-1.0
            "total_requests": int,
            "parsing_failures": int,
            "cache_size": int,
            "cache_max_size": int
        }
    """
    cache_hits = recommender._cache_hits
    cache_misses = recommender._cache_misses
    total_requests = cache_hits + cache_misses

    # Calculate hit rate, avoiding division by zero
    if total_requests > 0:
        cache_hit_rate = cache_hits / total_requests
    else:
        cache_hit_rate = 0.0

    return {
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": cache_hit_rate,
        "total_requests": total_requests,
        "parsing_failures": recommender._parsing_failures,
        "cache_size": len(recommender._cache),
        "cache_max_size": recommender._cache_max_size
    }
