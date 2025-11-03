"""Structured logging configuration using structlog.

This module provides a configurable logging system that supports:
- JSON format for production (machine-readable)
- Console format for development (human-readable)
- Environment variable control via LOG_FORMAT and LOG_LEVEL

Example:
    # JSON format (production)
    LOG_FORMAT=json python app.py

    # Text format (development)
    LOG_FORMAT=text python app.py
"""

import os
import sys
import logging
from typing import TextIO, Optional

import structlog


def _rename_event_to_message(logger, method_name, event_dict):
    """Rename 'event' key to 'message' for consistency with standard logging."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def configure_logging(stream: Optional[TextIO] = None) -> None:
    """Configure structured logging based on environment variables.

    Args:
        stream: Optional output stream for testing. If None, uses sys.stdout.

    Environment Variables:
        LOG_FORMAT: Output format - "json" or "text" (default: "json")
        LOG_LEVEL: Logging level - "DEBUG", "INFO", "WARNING", "ERROR" (default: "INFO")
    """
    # Read environment variables
    log_format = os.getenv("LOG_FORMAT", "json").lower()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Configure standard library logging (used by structlog)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Build processor chain based on format
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _rename_event_to_message,  # Rename 'event' to 'message'
    ]

    if log_format == "json":
        # JSON format for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console format for development
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Add the final processor that formats to string
    processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Disable cache for testing
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured structlog logger

    Example:
        logger = get_logger(__name__)
        logger.info("Application started", version="1.0.0")
    """
    return structlog.get_logger(name)


def bind_trace_id(trace_id: str) -> None:
    """Bind trace_id to the current logging context.

    All logs within this context will automatically include the trace_id.
    This is typically called in middleware to attach the request's trace_id
    to all logs generated during request processing.

    Args:
        trace_id: The trace ID to bind (e.g., 'req_7f3a9b2c')

    Example:
        bind_trace_id("req_7f3a9b2c")
        logger.info("Processing request")  # Will include trace_id automatically
    """
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def clear_trace_id() -> None:
    """Clear trace_id from the current logging context.

    This should be called at the end of each request to prevent
    context leakage between requests. Typically called in middleware's
    finally block.

    Example:
        try:
            bind_trace_id("req_7f3a9b2c")
            # ... process request ...
        finally:
            clear_trace_id()  # Ensure cleanup even if exceptions occur
    """
    structlog.contextvars.clear_contextvars()
