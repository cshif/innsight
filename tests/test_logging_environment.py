"""Tests for environment-based logging configuration."""

import json
import os
from io import StringIO
import pytest
from innsight.logging_config import configure_logging, get_logger


class TestEnvironmentBasedLogging:
    """Test that logging configuration adapts to ENV environment variable."""

    def test_production_environment_defaults_to_json_format(self, monkeypatch):
        """In production, LOG_FORMAT should default to 'json'."""
        monkeypatch.setenv("ENV", "prod")
        # Don't set LOG_FORMAT explicitly
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_line = output.getvalue().strip()
        # Should be valid JSON
        log_data = json.loads(log_line)
        assert log_data["message"] == "test message"

    def test_development_environment_defaults_to_text_format(self, monkeypatch):
        """In development, LOG_FORMAT should default to 'text'."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_line = output.getvalue().strip()
        # Should be text format (not valid JSON)
        assert "test message" in log_line
        with pytest.raises(json.JSONDecodeError):
            json.loads(log_line)

    def test_production_environment_defaults_to_info_level(self, monkeypatch):
        """In production, LOG_LEVEL should default to 'INFO'."""
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("LOG_FORMAT", "json")  # Force JSON for easy parsing
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.debug("debug message")
        logger.info("info message")

        lines = output.getvalue().strip().split('\n')
        # DEBUG should be filtered out, only INFO should appear
        assert len(lines) == 1
        log_data = json.loads(lines[0])
        assert log_data["message"] == "info message"
        assert log_data["level"] == "info"

    def test_development_environment_defaults_to_debug_level(self, monkeypatch):
        """In development, LOG_LEVEL should default to 'DEBUG'."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("LOG_FORMAT", "json")  # Force JSON for easy parsing
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.debug("debug message")
        logger.info("info message")

        lines = output.getvalue().strip().split('\n')
        # Both DEBUG and INFO should appear
        assert len(lines) == 2
        debug_log = json.loads(lines[0])
        info_log = json.loads(lines[1])
        assert debug_log["level"] == "debug"
        assert info_log["level"] == "info"

    def test_explicit_log_format_overrides_environment(self, monkeypatch):
        """Explicit LOG_FORMAT should override ENV-based defaults."""
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("LOG_FORMAT", "text")  # Override default

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_line = output.getvalue().strip()
        # Should be text format despite ENV=prod
        assert "test message" in log_line
        with pytest.raises(json.JSONDecodeError):
            json.loads(log_line)

    def test_explicit_log_level_overrides_environment(self, monkeypatch):
        """Explicit LOG_LEVEL should override ENV-based defaults."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")  # Override default
        monkeypatch.setenv("LOG_FORMAT", "json")

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")

        lines = output.getvalue().strip().split('\n')
        # Only WARNING should appear
        assert len(lines) == 1
        log_data = json.loads(lines[0])
        assert log_data["level"] == "warning"


class TestLoggingContextEnrichment:
    """Test that logs are enriched with environment and version information."""

    def test_logs_include_environment_field(self, monkeypatch):
        """All logs should include the 'environment' field."""
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("LOG_FORMAT", "json")

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_data = json.loads(output.getvalue().strip())
        assert "environment" in log_data
        assert log_data["environment"] == "prod"

    def test_logs_include_app_version_field(self, monkeypatch):
        """All logs should include the 'app_version' field."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("LOG_FORMAT", "json")

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_data = json.loads(output.getvalue().strip())
        assert "app_version" in log_data
        # Version could be actual version or "unknown"
        assert isinstance(log_data["app_version"], str)

    def test_environment_field_reflects_current_env(self, monkeypatch):
        """Environment field should reflect the current ENV setting."""
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("LOG_FORMAT", "json")

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_data = json.loads(output.getvalue().strip())
        assert log_data["environment"] == "dev"

    def test_default_environment_is_local(self, monkeypatch):
        """If ENV is not set, default should be 'local'."""
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setenv("LOG_FORMAT", "json")

        output = StringIO()
        configure_logging(stream=output)

        logger = get_logger(__name__)
        logger.info("test message")

        log_data = json.loads(output.getvalue().strip())
        assert log_data["environment"] == "local"
