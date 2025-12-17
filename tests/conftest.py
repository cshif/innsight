from unittest.mock import Mock

import pytest
from innsight.config import AppConfig


@pytest.fixture
def app_config(monkeypatch):
    """
    A pytest fixture that creates and returns a default AppConfig instance
    for testing. It sets all required environment variables.
    """
    # Set all required environment variables for AppConfig.from_env()
    monkeypatch.setenv("API_ENDPOINT", "http://test-api.com")
    monkeypatch.setenv("ORS_URL", "http://test-ors.com")
    monkeypatch.setenv("ORS_API_KEY", "test-ors-api-key")

    # Create and return the config instance
    config = AppConfig.from_env()
    return config

@pytest.fixture
def create_mock_config():
    """Factory fixture that returns a function to create mock configs."""
    def _factory(**overrides):
        mock_config = Mock(spec=AppConfig)
        mock_config.log_level = 'INFO'
        mock_config.log_format = 'json'
        mock_config.env = 'local'
        mock_config.is_production = False
        mock_config.cors_origins = ['*']
        mock_config.recommender_cache_ttl_seconds = 0
        mock_config.recommender_cache_maxsize = 20
        mock_config.recommender_cache_cleanup_interval = 60

        for key, value in overrides.items():
            setattr(mock_config, key, value)

        return mock_config

    return _factory
