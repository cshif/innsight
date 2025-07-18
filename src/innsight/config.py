"""Configuration management for innsight application."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    """Central configuration for the innsight application."""
    
    # API Endpoints
    api_endpoint: str
    ors_url: str
    ors_api_key: str
    
    # Client Settings
    nominatim_user_agent: str = "innsight"
    nominatim_timeout: int = 10
    ors_timeout: tuple[int, int] = (5, 30)
    
    # Cache Settings
    cache_maxsize: int = 128
    cache_ttl_hours: int = 24
    
    # Retry Settings
    max_retry_attempts: int = 3
    retry_delay: int = 1
    retry_backoff: int = 2
    
    # Tier Settings
    default_buffer: float = 1e-5
    max_days: int = 14
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create configuration from environment variables."""
        api_endpoint = os.getenv("API_ENDPOINT")
        ors_url = os.getenv("ORS_URL")
        ors_api_key = os.getenv("ORS_API_KEY")
        
        if not api_endpoint:
            raise ValueError("API_ENDPOINT environment variable not set")
        if not ors_url:
            raise ValueError("ORS_URL environment variable not set")
        if not ors_api_key:
            raise ValueError("ORS_API_KEY environment variable not set")
            
        return cls(
            api_endpoint=api_endpoint,
            ors_url=ors_url,
            ors_api_key=ors_api_key
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.api_endpoint:
            raise ValueError("API endpoint must not be empty")
        if not self.ors_url:
            raise ValueError("ORS URL must not be empty")
        if not self.ors_api_key:
            raise ValueError("ORS API key must not be empty")
        if self.nominatim_timeout <= 0:
            raise ValueError("Nominatim timeout must be positive")
        if any(t <= 0 for t in self.ors_timeout):
            raise ValueError("ORS timeout values must be positive")