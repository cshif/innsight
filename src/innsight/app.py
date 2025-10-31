from fastapi import FastAPI, Depends, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union, Tuple
import logging
import hashlib
import json
import os
import time
from datetime import datetime, UTC
import tomllib
import asyncio

from .exceptions import ServiceUnavailableError
from . import health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Read and cache version from pyproject.toml at module load time
_VERSION: str = "unknown"
try:
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        _VERSION = pyproject["project"]["version"]
except Exception as e:
    logging.warning(f"Failed to read version from pyproject.toml: {e}")

# Track application start time for uptime calculation
_START_TIME: float = time.time()


def get_version() -> str:
    """Get the application version."""
    return _VERSION

class WeightsModel(BaseModel):
    rating: Optional[float] = 1.0
    tier: Optional[float] = 1.0

class RecommendRequest(BaseModel):
    query: str = Field(..., description="Search query for accommodations")
    weights: Optional[WeightsModel] = None
    top_n: Optional[int] = Field(default=20, ge=1, le=20, description="Maximum number of results (1-20)")
    filters: Optional[List[str]] = None

class AccommodationModel(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    tier: int = Field(ge=0, le=3)
    lat: Optional[float] = None
    lon: Optional[float] = None
    osmid: Optional[str] = None
    osmtype: Optional[str] = None
    tourism: Optional[str] = None
    rating: Optional[float] = None
    amenities: Optional[dict] = None

class StatsModel(BaseModel):
    tier_0: int = 0
    tier_1: int = 0  
    tier_2: int = 0
    tier_3: int = 0

class MainPoiModel(BaseModel):
    name: str
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    display_name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[dict] = None

class IntervalsModel(BaseModel):
    values: List[int]
    unit: str = "minutes"
    profile: str = "driving-car"

class PolygonGeometry(BaseModel):
    """GeoJSON Polygon 幾何體"""
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[Tuple[float, float]]]  # [[(lon, lat), (lon, lat), ...]]

class MultiPolygonGeometry(BaseModel):
    """GeoJSON MultiPolygon 幾何體"""
    type: Literal["MultiPolygon"] = "MultiPolygon"  
    coordinates: List[List[List[Tuple[float, float]]]]  # [[[[(lon, lat), (lon, lat), ...]], [...]]]

# Union 讓 API 支援兩種格式
IsochroneGeometry = Union[PolygonGeometry, MultiPolygonGeometry]

class RecommendResponse(BaseModel):
    stats: StatsModel
    top: List[AccommodationModel]
    main_poi: MainPoiModel
    isochrone_geometry: List[IsochroneGeometry] = Field(
        default_factory=list,
        description="Travel time isochrones in GeoJSON format"
    )
    intervals: IntervalsModel = Field(default_factory=lambda: IntervalsModel(values=[]))

class ErrorResponse(BaseModel):
    error: str
    message: str

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

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add X-Content-Type-Options header
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Add X-Frame-Options header
        response.headers["X-Frame-Options"] = "DENY"

        # Add Referrer-Policy header
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add Strict-Transport-Security header (only in production)
        env = os.getenv("ENV", "local")  # Default to "local" if not set
        if env == "prod":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

        # Add Content-Security-Policy header (strict API policy)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # Add Permissions-Policy header (disable all browser features)
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=(), ambient-light-sensor=()"

        # Add Cross-Origin-Opener-Policy header
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Add Cross-Origin-Resource-Policy header
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        return response

def create_app() -> FastAPI:
    app = FastAPI(title="InnSight API", root_path="/api")

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify your frontend domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Parse Error",
                "message": f"Request validation failed: {str(exc)}"
            }
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_exception_handler(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "message": str(exc)
            }
        )

    from .pipeline import Recommender
    def get_recommender() -> Recommender:
        return Recommender()

    @app.get("/health")
    async def health_check():
        """Basic health check endpoint.

        Returns the application health status, current timestamp, and version.
        This endpoint is designed for liveness probes in Kubernetes/Docker environments.
        """
        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
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
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
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
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
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
