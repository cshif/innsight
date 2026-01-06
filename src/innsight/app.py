from fastapi import FastAPI, Depends, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import hashlib
import json
import os
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
import tomllib
import asyncio

from .exceptions import ServiceUnavailableError
from . import health
from .models import (
    RecommendRequest,
    RecommendResponse,
    ErrorResponse
)
from .middleware import SecurityHeadersMiddleware, RequestTracingMiddleware
from .logging_config import configure_logging, get_logger
from .config import AppConfig

# Get module logger
logger = get_logger(__name__)

# Read and cache version from pyproject.toml at module load time
_VERSION: str = "unknown"
try:
    # Calculate project root directory (3 levels up from this file)
    # Current file: /path/to/src/innsight/app.py
    # Project root: /path/to/
    project_root = Path(__file__).parent.parent.parent
    pyproject_path = project_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
        _VERSION = pyproject["project"]["version"]
except FileNotFoundError:
    # pyproject.toml not found - will log warning when logger is configured
    pass
except Exception:
    # Other errors (parsing, missing keys, etc.)
    pass

# Track application start time for uptime calculation
_START_TIME: float = time.time()


def get_version() -> str:
    """Get the application version."""
    return _VERSION


def _generate_etag(content: dict) -> str:
    """Generate ETag from response content.

    Args:
        content: Dictionary representing the response content

    Returns:
        ETag string in HTTP format (quoted hash)
    """
    # Serialize to JSON with sorted keys for consistency
    json_str = json.dumps(content, sort_keys=True, ensure_ascii=False)

    # Generate MD5 hash
    hash_obj = hashlib.md5(json_str.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()

    # Return in HTTP ETag format (quoted)
    return f'"{hash_hex}"'


def create_app() -> FastAPI:
    # Load configuration from environment
    config = AppConfig.from_env()

    # Configure structured logging
    configure_logging(config)

    # Warn if version couldn't be read
    if _VERSION == "unknown":
        logger.warning(
            "Failed to read application version from pyproject.toml",
            version=_VERSION
        )

    app = FastAPI(title="InnSight API", root_path="/api")

    # Initialize Rate Limiter
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"] if config.is_development else ["60/minute"]
    )
    app.state.limiter = limiter

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add request tracing middleware (executes before SecurityHeadersMiddleware)
    app.add_middleware(RequestTracingMiddleware)

    # Add CORS middleware with dynamic configuration based on environment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        """Application startup event handler."""
        logger.info(
            "Application started successfully",
            version=get_version(),
            environment=config.env,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            start_time=datetime.now(UTC).isoformat().replace("+00:00", "Z")
        )

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event handler."""
        uptime = int(time.time() - _START_TIME)
        logger.info(
            "Application shutting down",
            uptime_seconds=uptime,
            uptime_human=f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s"
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        logger.warning(
            "Request validation failed",
            error_type="RequestValidationError",
            error_message=str(exc),
            endpoint=request.url.path,
            method=request.method,
            status_code=400
        )

        return JSONResponse(
            status_code=400,
            content={
                "error": "Parse Error",
                "message": f"Request validation failed: {str(exc)}"
            }
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_exception_handler(request, exc):
        logger.error(
            "Service unavailable",
            error_type="ServiceUnavailableError",
            error_message=str(exc),
            endpoint=request.url.path,
            method=request.method,
            status_code=503
        )

        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "message": str(exc)
            }
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        logger.warning(
            "Rate limit exceeded",
            endpoint=request.url.path,
            client_ip=get_remote_address(request),
            status_code=429
        )

        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate Limit Exceeded",
                "message": "Too many requests. Please try again later."
            },
            headers={"Retry-After": "60"}
        )

    from .pipeline import Recommender
    def get_recommender() -> Recommender:
        return Recommender()

    @limiter.limit("30/minute")
    @app.get("/health")
    async def health_check(request: Request):
        """Basic health check endpoint.

        Returns the application health status, current timestamp, and version.
        This endpoint is designed for liveness probes in Kubernetes/Docker environments.
        """
        return {
            "status": "healthy",
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "version": get_version()
        }

    @app.get("/ready")
    async def readiness_check():
        """Readiness check endpoint.

        Checks if all external service dependencies are healthy.
        Returns 200 if all services are available, 503 if any service is unavailable.
        This endpoint is designed for readiness probes in Kubernetes/Docker environments.
        """
        # Get service URLs from environment variables
        nominatim_url = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
        ors_url = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org")
        overpass_url = os.getenv("OVERPASS_BASE_URL", "https://overpass-api.de/api")

        # Check all services concurrently
        nominatim_result, ors_result, overpass_result = await asyncio.gather(
            health.check_nominatim_health(nominatim_url),
            health.check_ors_health(ors_url),
            health.check_overpass_health(overpass_url)
        )

        # Determine overall readiness
        all_healthy = (
            nominatim_result["healthy"] and
            ors_result["healthy"] and
            overpass_result["healthy"]
        )

        status_code = 200 if all_healthy else 503
        status = "ready" if all_healthy else "not_ready"

        response_data = {
            "status": status,
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "services": {
                "nominatim": nominatim_result,
                "ors": ors_result,
                "overpass": overpass_result
            }
        }

        return JSONResponse(status_code=status_code, content=response_data)

    @app.get("/status")
    async def status_check(r: Recommender = Depends(get_recommender)):
        """Detailed status endpoint.

        Returns comprehensive system status including:
        - Application health and uptime
        - External service availability
        - Cache statistics
        - Parsing failures

        This endpoint is designed for monitoring dashboards and management interfaces.
        """
        # Get service URLs from environment variables
        nominatim_url = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
        ors_url = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org")
        overpass_url = os.getenv("OVERPASS_BASE_URL", "https://overpass-api.de/api")

        # Check all services concurrently
        nominatim_result, ors_result, overpass_result = await asyncio.gather(
            health.check_nominatim_health(nominatim_url),
            health.check_ors_health(ors_url),
            health.check_overpass_health(overpass_url)
        )

        # Get cache statistics
        cache_stats = health.get_cache_stats(r)

        # Calculate uptime
        uptime_seconds = int(time.time() - _START_TIME)

        # Determine overall status
        all_services_healthy = (
            nominatim_result["healthy"] and
            ors_result["healthy"] and
            overpass_result["healthy"]
        )
        status = "operational" if all_services_healthy else "degraded"

        # Build response
        response_data = {
            "status": status,
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "version": get_version(),
            "uptime_seconds": uptime_seconds,
            "external_services": {
                "nominatim": nominatim_result,
                "ors": ors_result,
                "overpass": overpass_result
            },
            "cache": {
                "hits": cache_stats["cache_hits"],
                "misses": cache_stats["cache_misses"],
                "hit_rate": cache_stats["cache_hit_rate"],
                "total_requests": cache_stats["total_requests"],
                "size": cache_stats["cache_size"],
                "max_size": cache_stats["cache_max_size"]
            },
            "parsing_failures": cache_stats["parsing_failures"]
        }

        return response_data

    @app.post("/recommend", response_model=RecommendResponse)
    @limiter.limit("100/minute" if config.is_development else "10/minute")
    async def recommend(req: RecommendRequest, request: Request, response: Response, r: Recommender = Depends(get_recommender)):
        # Get recommendation result
        result = r.run(req.model_dump())

        # Generate ETag from response content
        etag = _generate_etag(result)

        # Set HTTP caching headers
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["ETag"] = etag

        # Check If-None-Match header
        if_none_match = request.headers.get("if-none-match")
        if if_none_match:
            should_return_304 = False

            # Check for wildcard (matches any version)
            if if_none_match.strip() == "*":
                should_return_304 = True
            else:
                # Parse multiple ETags (comma-separated)
                client_etags = [e.strip() for e in if_none_match.split(',')]
                # Check if current ETag matches any of the client's ETags
                if etag in client_etags:
                    should_return_304 = True

            if should_return_304:
                # Return 304 Not Modified with no body
                return Response(status_code=304, headers={
                    "Cache-Control": "no-cache, must-revalidate",
                    "ETag": etag
                })

        return result

    return app

# Create the app instance for FastAPI CLI
app = create_app()


def main() -> int:
    """Entry point for running the API server via CLI command."""
    import uvicorn

    uvicorn.run(
        "innsight.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
