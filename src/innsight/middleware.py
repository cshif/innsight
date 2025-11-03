"""Custom middleware for FastAPI application."""

import os
import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .logging_config import bind_trace_id, clear_trace_id


def _generate_trace_id() -> str:
    """Generate a unique trace ID for the request.

    Returns:
        A trace ID in the format 'req_<8 hex characters>'
        Example: 'req_7f3a9b2c'
    """
    random_hex = secrets.token_hex(4)  # 4 bytes = 8 hex characters
    return f"req_{random_hex}"


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


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add unique trace ID to each request.

    This middleware:
    1. Generates a unique trace_id for each request
    2. Stores it in request.state.trace_id for use in the application
    3. Binds it to the logging context (all logs will include trace_id)
    4. Returns it in the X-Trace-ID response header
    5. Cleans up the logging context after the request

    The trace_id format is: req_<8 hex characters>
    Example: req_7f3a9b2c
    """

    async def dispatch(self, request: Request, call_next):
        # Generate unique trace ID
        trace_id = _generate_trace_id()

        # Store in request state for use in application
        request.state.trace_id = trace_id

        # Bind to logging context (all logs will include trace_id)
        bind_trace_id(trace_id)

        try:
            # Process the request
            response = await call_next(request)

            # Add trace ID to response header
            response.headers["X-Trace-ID"] = trace_id

            return response
        finally:
            # Always clear context, even if an exception occurs
            # This prevents context leakage between requests
            clear_trace_id()