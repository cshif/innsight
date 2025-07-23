"""Configuration management for innsight application."""

import os
from dataclasses import dataclass, field
from typing import Tuple, Dict
from dotenv import load_dotenv

from .exceptions import ConfigurationError

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
    ors_timeout: Tuple[int, int] = (5, 30)
    
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
    
    # Rating Weights
    rating_weights: Dict[str, float] = field(default_factory=lambda: {
        'tier': 4.0,
        'rating': 2.0,
        'parking': 1.0,
        'wheelchair': 1.0,
        'kids': 1.0,
        'pet': 1.0
    })
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create configuration from environment variables."""
        api_endpoint = os.getenv("API_ENDPOINT")
        ors_url = os.getenv("ORS_URL")
        ors_api_key = os.getenv("ORS_API_KEY")
        
        if not api_endpoint:
            raise ConfigurationError("API_ENDPOINT environment variable not set")
        if not ors_url:
            raise ConfigurationError("ORS_URL environment variable not set")
        if not ors_api_key:
            raise ConfigurationError("ORS_API_KEY environment variable not set")
            
        return cls(
            api_endpoint=api_endpoint,
            ors_url=ors_url,
            ors_api_key=ors_api_key
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.api_endpoint:
            raise ConfigurationError("API endpoint must not be empty")
        if not self.ors_url:
            raise ConfigurationError("ORS URL must not be empty")
        if not self.ors_api_key:
            raise ConfigurationError("ORS API key must not be empty")
        if self.nominatim_timeout <= 0:
            raise ConfigurationError("Nominatim timeout must be positive")
        if any(t <= 0 for t in self.ors_timeout):
            raise ConfigurationError("ORS timeout values must be positive")
        
        # Validate rating weights
        if not isinstance(self.rating_weights, dict):
            raise ConfigurationError("Rating weights must be a dictionary")
        
        required_weights = {'tier', 'rating', 'parking', 'wheelchair', 'kids', 'pet'}
        if not required_weights.issubset(self.rating_weights.keys()):
            missing = required_weights - set(self.rating_weights.keys())
            raise ConfigurationError(f"Missing required rating weights: {missing}")
        
        for weight_name, weight_value in self.rating_weights.items():
            if not isinstance(weight_value, (int, float)):
                raise ConfigurationError(f"Rating weight {weight_name} must be a number, got {type(weight_value)}")
            if weight_value < 0:
                raise ConfigurationError(f"Rating weight {weight_name} must be non-negative, got {weight_value}")