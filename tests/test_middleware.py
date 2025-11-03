"""Tests for middleware components."""

import re
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from src.innsight.app import create_app


class TestRequestTracingMiddleware:
    """Test suite for RequestTracingMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a fresh app for each test
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_trace_id_generated(self):
        """Test that every request gets a trace_id."""
        # When: Send a request
        response = self.client.get("/health")

        # Then: Response should contain X-Trace-ID header
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] is not None
        assert len(response.headers["X-Trace-ID"]) > 0

    def test_trace_id_unique(self):
        """Test that different requests get different trace_ids."""
        # When: Send two requests
        response1 = self.client.get("/health")
        response2 = self.client.get("/health")

        # Then: Both should have trace_ids
        assert "X-Trace-ID" in response1.headers
        assert "X-Trace-ID" in response2.headers

        # And: The trace_ids should be different
        trace_id_1 = response1.headers["X-Trace-ID"]
        trace_id_2 = response2.headers["X-Trace-ID"]
        assert trace_id_1 != trace_id_2

    def test_trace_id_in_response_header(self):
        """Test that response header contains X-Trace-ID."""
        # When: Send a request
        response = self.client.get("/health")

        # Then: X-Trace-ID header should exist and have a value
        assert "X-Trace-ID" in response.headers
        trace_id = response.headers["X-Trace-ID"]
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

    def test_trace_id_format(self):
        """Test that trace_id format is req_<8 hex characters>."""
        # When: Send a request
        response = self.client.get("/health")

        # Then: trace_id should match the expected format
        assert "X-Trace-ID" in response.headers
        trace_id = response.headers["X-Trace-ID"]

        # Format: req_<8 hex characters>
        pattern = r'^req_[0-9a-f]{8}$'
        assert re.match(pattern, trace_id), \
            f"trace_id '{trace_id}' does not match pattern '{pattern}'"

    def test_trace_id_in_request_state(self):
        """Test that request.state.trace_id is accessible during request processing."""
        # Given: Create a test endpoint that accesses request.state.trace_id
        captured_trace_id = None
        captured_header_trace_id = None

        @self.app.get("/test_trace_id")
        async def test_endpoint(request: Request):
            nonlocal captured_trace_id
            # Capture the trace_id from request.state
            captured_trace_id = getattr(request.state, 'trace_id', None)
            return {"message": "test"}

        # When: Send a request to the test endpoint
        response = self.client.get("/test_trace_id")
        captured_header_trace_id = response.headers.get("X-Trace-ID")

        # Then: request.state.trace_id should be accessible
        assert captured_trace_id is not None, "request.state.trace_id was not set"

        # And: It should match the trace_id in the response header
        assert captured_trace_id == captured_header_trace_id, \
            f"request.state.trace_id ('{captured_trace_id}') does not match " \
            f"X-Trace-ID header ('{captured_header_trace_id}')"

        # And: It should follow the correct format
        pattern = r'^req_[0-9a-f]{8}$'
        assert re.match(pattern, captured_trace_id), \
            f"trace_id '{captured_trace_id}' does not match pattern '{pattern}'"
