"""Tests for rating configuration functionality."""

import os
import pytest
from unittest.mock import patch
from src.innsight.config import AppConfig
from src.innsight.rating_service import RatingService, score_accommodation
from src.innsight.exceptions import ConfigurationError


class TestRatingConfiguration:
    """Test rating weights configuration in AppConfig."""
    
    def test_default_rating_weights(self):
        """Test that AppConfig has correct default rating weights."""
        config = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key"
        )
        
        expected_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        
        assert config.rating_weights == expected_weights
    
    def test_config_validation_rating_weights(self):
        """Test config validation for rating weights."""
        # Test with valid weights
        config = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com", 
            ors_api_key="test_key",
            rating_weights={'tier': 5.0, 'rating': 3.0, 'parking': 1.0, 'wheelchair': 1.0, 'kids': 1.0, 'pet': 1.0}
        )
        config.validate()  # Should not raise
        
        # Test with missing required weights
        config_missing = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key", 
            rating_weights={'tier': 5.0}  # Missing other weights
        )
        
        with pytest.raises(ConfigurationError, match="Missing required rating weights"):
            config_missing.validate()
        
        # Test with negative weights
        config_negative = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key",
            rating_weights={'tier': -1.0, 'rating': 2.0, 'parking': 1.0, 'wheelchair': 1.0, 'kids': 1.0, 'pet': 1.0}
        )
        
        with pytest.raises(ConfigurationError, match="Rating weight tier must be non-negative"):
            config_negative.validate()
        
        # Test with non-numeric weights
        config_invalid = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key",
            rating_weights={'tier': 'invalid', 'rating': 2.0, 'parking': 1.0, 'wheelchair': 1.0, 'kids': 1.0, 'pet': 1.0}
        )
        
        with pytest.raises(ConfigurationError, match="Rating weight tier must be a number"):
            config_invalid.validate()

    @patch.dict(os.environ, {
        'API_ENDPOINT': 'http://test.example.com',
        'ORS_URL': 'http://ors.example.com',
        'ORS_API_KEY': 'test_key'
    })
    def test_config_from_env_uses_default_weights(self):
        """Test loading config from environment uses default weights."""
        config = AppConfig.from_env()
        
        # Check that default weights are used
        expected_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        assert config.rating_weights == expected_weights


class TestRatingServiceWithConfig:
    """Test RatingService using configuration."""
    
    def test_rating_service_uses_config_weights(self):
        """Test that RatingService uses weights from config."""
        custom_weights = {
            'tier': 10.0,
            'rating': 5.0,
            'parking': 2.0,
            'wheelchair': 2.0,
            'kids': 2.0,
            'pet': 2.0
        }
        
        config = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key",
            rating_weights=custom_weights
        )
        
        service = RatingService(config)
        assert service.default_weights == custom_weights
    
    def test_rating_service_fallback_without_config(self):
        """Test that RatingService falls back to defaults without config."""
        service = RatingService(None)
        
        expected_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        
        assert service.default_weights == expected_weights
    
    def test_rating_service_score_method_uses_config(self):
        """Test that RatingService.score() method uses configured weights."""
        custom_weights = {
            'tier': 10.0,  # Much higher tier weight
            'rating': 1.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        
        config = AppConfig(
            api_endpoint="http://test.example.com",
            ors_url="http://ors.example.com",
            ors_api_key="test_key",
            rating_weights=custom_weights
        )
        
        service = RatingService(config)
        
        # Test two accommodations with different tiers but same rating
        row_high_tier = {
            'tier': 3,
            'rating': 3.0,
            'tags': {'parking': 'no', 'wheelchair': 'no', 'kids': 'no', 'pet': 'no'}
        }
        
        row_low_tier = {
            'tier': 1,
            'rating': 3.0,
            'tags': {'parking': 'no', 'wheelchair': 'no', 'kids': 'no', 'pet': 'no'}
        }
        
        score_high = service.score(row_high_tier)
        score_low = service.score(row_low_tier)
        
        # With high tier weight, the difference should be significant
        assert score_high > score_low
        
        # Compare with default weights
        default_service = RatingService(None)
        default_score_high = default_service.score(row_high_tier)
        default_score_low = default_service.score(row_low_tier)
        
        # The difference should be more pronounced with custom weights
        custom_diff = score_high - score_low
        default_diff = default_score_high - default_score_low
        assert custom_diff > default_diff


class TestScoreAccommodationWithDefaultWeights:
    """Test score_accommodation function with default_weights parameter."""
    
    def test_score_accommodation_uses_custom_default_weights(self):
        """Test that score_accommodation uses provided default_weights."""
        custom_defaults = {
            'tier': 10.0,
            'rating': 1.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        
        row = {
            'tier': 3,
            'rating': 2.0,
            'tags': {'parking': 'no', 'wheelchair': 'no', 'kids': 'no', 'pet': 'no'}
        }
        
        # Score with custom defaults (high tier weight)
        score_custom = score_accommodation(row, default_weights=custom_defaults)
        
        # Score with built-in defaults
        score_builtin = score_accommodation(row)
        
        # Due to higher tier weight, custom should give higher score
        assert score_custom != score_builtin
    
    def test_score_accommodation_weights_override_default_weights(self):
        """Test that weights parameter overrides default_weights."""
        custom_defaults = {
            'tier': 10.0,
            'rating': 1.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        
        # Only override specific weights to test partial override
        override_weights = {
            'tier': 1.0,  # Much lower than default
            'rating': 10.0  # Much higher than default
        }
        
        row = {
            'tier': 2,      # Mid-tier (not max)
            'rating': 3.0,  # Mid-rating (not max)
            'tags': {'parking': 'no', 'wheelchair': 'no', 'kids': 'no', 'pet': 'no'}
        }
        
        # Score with custom defaults (should prioritize tier due to weight 10)
        score_defaults = score_accommodation(row, default_weights=custom_defaults)
        
        # Score with partial override weights (should prioritize rating due to weight 10)
        score_override = score_accommodation(row, weights=override_weights, default_weights=custom_defaults)
        
        # Both should work but give different results
        assert score_defaults != score_override
        assert 0 <= score_defaults <= 100
        assert 0 <= score_override <= 100