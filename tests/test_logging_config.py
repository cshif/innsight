"""Tests for logging configuration."""

import json
import os
from io import StringIO
import logging

import pytest
import structlog


class TestLoggingConfig:
    """Test suite for logging configuration."""

    def test_json_format_output(self, monkeypatch):
        """Test that JSON format outputs valid JSON."""
        # Set environment to JSON mode
        monkeypatch.setenv("LOG_FORMAT", "json")

        # Import after setting environment variable
        from innsight.logging_config import configure_logging, get_logger

        # Capture log output
        log_output = StringIO()
        configure_logging(stream=log_output)

        logger = get_logger("test")
        logger.info("test message", key="value")

        # Parse output as JSON
        log_output.seek(0)
        log_line = log_output.readline().strip()

        # Should be valid JSON
        log_data = json.loads(log_line)

        # Verify structure
        assert "timestamp" in log_data
        assert "level" in log_data
        assert "message" in log_data
        assert log_data["message"] == "test message"
        assert log_data["key"] == "value"

    def test_text_format_output(self, monkeypatch):
        """Test that text format outputs human-readable text."""
        # Set environment to text mode
        monkeypatch.setenv("LOG_FORMAT", "text")

        from innsight.logging_config import configure_logging, get_logger

        # Capture log output
        log_output = StringIO()
        configure_logging(stream=log_output)

        logger = get_logger("test")
        logger.info("test message")

        # Get output
        log_output.seek(0)
        log_line = log_output.readline()

        # Should NOT be JSON (will raise exception if we try to parse)
        with pytest.raises(json.JSONDecodeError):
            json.loads(log_line)

        # Should contain the message
        assert "test message" in log_line

    def test_log_level_filtering(self, monkeypatch):
        """Test that log level filtering works correctly."""
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        from innsight.logging_config import configure_logging, get_logger

        # Capture log output
        log_output = StringIO()
        configure_logging(stream=log_output)

        logger = get_logger("test")
        logger.debug("debug message")  # Should be filtered out
        logger.info("info message")     # Should appear

        # Get output
        log_output.seek(0)
        output = log_output.read()

        # DEBUG should be filtered
        assert "debug message" not in output
        # INFO should appear
        assert "info message" in output

    def test_required_fields_present(self, monkeypatch):
        """Test that JSON output contains all required fields."""
        monkeypatch.setenv("LOG_FORMAT", "json")

        from innsight.logging_config import configure_logging, get_logger

        # Capture log output
        log_output = StringIO()
        configure_logging(stream=log_output)

        logger = get_logger("test.module")
        logger.info("test message")

        # Parse output
        log_output.seek(0)
        log_line = log_output.readline().strip()
        log_data = json.loads(log_line)

        # Verify required fields
        required_fields = ["timestamp", "level", "message"]
        for field in required_fields:
            assert field in log_data, f"Missing required field: {field}"

        # Verify values
        assert log_data["level"] == "info"
        assert log_data["message"] == "test message"
        # Timestamp should be ISO 8601 format
        assert "T" in log_data["timestamp"]
        assert "Z" in log_data["timestamp"] or "+" in log_data["timestamp"]

    def test_environment_variable_switching(self, monkeypatch):
        """Test that LOG_FORMAT environment variable switches output format."""
        from innsight.logging_config import configure_logging, get_logger

        # Test JSON format
        monkeypatch.setenv("LOG_FORMAT", "json")
        log_output_json = StringIO()
        configure_logging(stream=log_output_json)
        logger = get_logger("test")
        logger.info("test")

        log_output_json.seek(0)
        json_line = log_output_json.readline().strip()

        # Should be valid JSON
        json_data = json.loads(json_line)
        assert "timestamp" in json_data

        # Test text format
        monkeypatch.setenv("LOG_FORMAT", "text")
        log_output_text = StringIO()
        configure_logging(stream=log_output_text)
        logger = get_logger("test")
        logger.info("test")

        log_output_text.seek(0)
        text_line = log_output_text.readline()

        # Should NOT be valid JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(text_line)
