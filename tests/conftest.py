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
