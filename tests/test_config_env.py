"""Tests for environment-based configuration."""

import pytest
from innsight.config import AppConfig


class TestEnvironmentConfiguration:
    """Test environment-based configuration behavior."""

    def test_production_environment(self, monkeypatch):
        """Test configuration in production environment."""
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("FRONTEND_URL", "https://example.com")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.is_production is True
        assert config.is_development is False
        assert config.cors_origins == ["https://example.com"]
        assert config.log_format == "json"
        assert config.log_level == "INFO"

    def test_development_environment(self, monkeypatch):
        """Test configuration in development environment."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.is_production is False
        assert config.is_development is True
        assert config.cors_origins == ["*"]
        assert config.log_format == "text"
        assert config.log_level == "DEBUG"

    def test_dev_environment(self, monkeypatch):
        """Test configuration in dev environment."""
        monkeypatch.setenv("ENV", "dev")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.is_production is False
        assert config.is_development is True
        assert config.env == "dev"

    def test_custom_log_level_production(self, monkeypatch):
        """Test custom log level in production."""
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.log_level == "WARNING"

    def test_custom_log_level_development(self, monkeypatch):
        """Test custom log level in development."""
        monkeypatch.setenv("ENV", "local")
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.log_level == "INFO"

    def test_default_environment(self, monkeypatch):
        """Test default environment when ENV not set."""
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.env == "local"
        assert config.is_development is True

    def test_default_frontend_url(self, monkeypatch):
        """Test default frontend URL when not set."""
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        monkeypatch.setenv("API_ENDPOINT", "http://api")
        monkeypatch.setenv("ORS_URL", "http://ors")
        monkeypatch.setenv("ORS_API_KEY", "test")

        config = AppConfig.from_env()

        assert config.frontend_url == "http://localhost:5173"
