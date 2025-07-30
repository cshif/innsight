"""Unit tests for rating service."""

import pytest
import pandas as pd
import time
import warnings
from src.innsight.rating_service import RatingService, score_accommodation


class TestScoreAccommodation:
    """Test cases for score_accommodation function."""

    def test_happy_path_basic_scoring(self):
        """Test 1: Happy Path - basic scoring with tier and rating differences."""
        # Given
        row_a = {
            'tier': 3,
            'rating': 4.8,
            'tags': {'parking': 'yes', 'wheelchair': 'yes'}
        }
        row_b = {
            'tier': 1, 
            'rating': 3.0,
            'tags': {'parking': 'no', 'wheelchair': 'no'}
        }
        
        # When
        score_a = score_accommodation(row_a)
        score_b = score_accommodation(row_b)
        
        # Then
        assert score_a > score_b
        assert 0 <= score_a <= 100
        assert 0 <= score_b <= 100

    def test_weight_override(self):
        """Test 2: Weight override changes ranking significantly."""
        # Given
        row_a = {
            'tier': 3,
            'rating': 4.8,
            'tags': {'parking': 'yes', 'wheelchair': 'yes'}
        }
        row_b = {
            'tier': 1,
            'rating': 3.0, 
            'tags': {'parking': 'no', 'wheelchair': 'no'}
        }
        weights = {'rating': 10, 'tier': 1}
        
        # When - calculate with default weights first
        default_score_a = score_accommodation(row_a)
        default_score_b = score_accommodation(row_b)
        
        # Then calculate with overridden weights
        override_score_a = score_accommodation(row_a, weights=weights)
        override_score_b = score_accommodation(row_b, weights=weights)
        
        # Then - ranking should change significantly due to rating weight
        default_diff = default_score_a - default_score_b
        override_diff = override_score_a - override_score_b
        
        # With rating weighted heavily, the difference should be more pronounced
        assert abs(override_diff - default_diff) > 5  # Significant change

    def test_missing_rating_uses_default_50(self):
        """Test 3: Missing rating uses smooth value 50."""
        # Given
        row = {
            'tier': 2,
            'rating': None,
            'tags': {'parking': 'yes'}
        }
        
        # When
        score = score_accommodation(row)
        
        # Then
        assert 0 <= score <= 100
        # Should not raise exception
    
    def test_nan_rating_uses_default_50(self):
        """Test NaN rating uses default score of 50, same as None."""
        import numpy as np
        
        # Test with None rating
        row_none = {
            'tier': 2,
            'rating': None,
            'tags': {'parking': 'yes', 'wheelchair': 'no'}
        }
        score_none = score_accommodation(row_none)
        
        # Test with NaN rating
        row_nan = {
            'tier': 2,
            'rating': np.nan,
            'tags': {'parking': 'yes', 'wheelchair': 'no'}
        }
        score_nan = score_accommodation(row_nan)
        
        # Both should produce the same result
        assert score_none == score_nan
        assert 0 <= score_nan <= 100

    def test_unknown_tag_value_uses_50_with_warning(self):
        """Test 4: Unknown tag values use smooth value 50 with warning."""
        # Given
        row = {
            'tier': 2,
            'rating': 4.0,
            'tags': {'parking': 'maybe'}  # Unknown value
        }
        
        # When/Then
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            score = score_accommodation(row)
            
            # Should log warning
            assert len(w) > 0
            assert "unknown tag value" in str(w[0].message).lower()
            
        # Should still return valid score
        assert 0 <= score <= 100

    def test_tier_out_of_bounds_raises_error(self):
        """Test 5: tier out of bounds raises ValueError."""
        # Given
        row = {
            'tier': 5,  # Out of bounds
            'rating': 4.0,
            'tags': {'parking': 'yes'}
        }
        
        # When/Then
        with pytest.raises(ValueError, match="tier must be 0-3"):
            score_accommodation(row)

    def test_negative_weights_raise_error(self):
        """Test 6: Negative weights raise ValueError."""
        # Given
        row = {
            'tier': 2,
            'rating': 4.0,
            'tags': {'parking': 'yes'}
        }
        weights = {'rating': -2, 'tier': 4}
        
        # When/Then
        with pytest.raises(ValueError, match="weights must be ≥0"):
            score_accommodation(row, weights=weights)

    def test_all_zero_weights_raise_error(self):
        """Test 7: All zero weights raise ZeroDivisionError."""
        # Given
        row = {
            'tier': 2,
            'rating': 4.0,
            'tags': {'parking': 'yes'}
        }
        weights = {'tier': 0, 'rating': 0, 'parking': 0, 'wheelchair': 0, 'kids': 0, 'pet': 0}
        
        # When/Then
        with pytest.raises(ZeroDivisionError):
            score_accommodation(row, weights=weights)

    def test_rating_boundary_values(self):
        """Test 8: Rating boundary values (0 vs 5)."""
        # Given
        row_0 = {
            'tier': 2,
            'rating': 0,
            'tags': {'parking': 'yes'}
        }
        row_5 = {
            'tier': 2,
            'rating': 5,
            'tags': {'parking': 'yes'}
        }
        
        # When
        score_0 = score_accommodation(row_0)
        score_5 = score_accommodation(row_5)
        
        # Then
        assert score_0 < score_5
        assert 0 <= score_0 <= 100
        assert 0 <= score_5 <= 100

    def test_type_compatibility_dict_vs_series(self):
        """Test 9: Type compatibility - dict vs pd.Series should give equal results."""
        # Given
        data_dict = {
            'tier': 2,
            'rating': 4.5,
            'tags': {'parking': 'yes', 'wheelchair': 'no'}
        }
        data_series = pd.Series(data_dict)
        
        # When
        score_dict = score_accommodation(data_dict)
        score_series = score_accommodation(data_series)
        
        # Then
        assert score_dict == score_series

    def test_large_data_performance(self):
        """Test 10: Large data performance - 10000 rows ≤ 0.3s."""
        # Given
        import random
        data = []
        for _ in range(10000):
            row = {
                'tier': random.randint(0, 3),
                'rating': random.uniform(0, 5),
                'tags': {
                    'parking': random.choice(['yes', 'no']),
                    'wheelchair': random.choice(['yes', 'no']),
                    'kids': random.choice(['yes', 'no']),
                    'pet': random.choice(['yes', 'no'])
                }
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # When
        start_time = time.time()
        scores = df.apply(score_accommodation, axis=1)
        end_time = time.time()
        
        # Then
        execution_time = end_time - start_time
        assert execution_time <= 0.3, f"Execution time {execution_time:.3f}s exceeds 0.3s limit"
        assert scores.between(0, 100).all()

    def test_missing_and_extra_weight_keys(self):
        """Test 11: Missing weight keys use defaults, extra keys ignored."""
        # Given
        row = {
            'tier': 2,
            'rating': 4.0,
            'tags': {'parking': 'yes'}
        }
        
        # Test missing keys
        weights_missing = {'tier': 4}  # Missing other keys
        score_missing = score_accommodation(row, weights=weights_missing)
        
        # Test extra keys
        weights_extra = {'tier': 4, 'rating': 2, 'spa': 2}  # Extra key
        score_extra = score_accommodation(row, weights=weights_extra)
        
        # Then - should not raise errors
        assert 0 <= score_missing <= 100
        assert 0 <= score_extra <= 100

    def test_rating_string_conversion(self):
        """Test 12: Rating as string should convert to float."""
        # Given
        row_valid = {
            'tier': 2,
            'rating': '4.5',  # String that can convert
            'tags': {'parking': 'yes'}
        }
        row_invalid = {
            'tier': 2,
            'rating': 'invalid',  # String that cannot convert
            'tags': {'parking': 'yes'}
        }
        
        # When/Then
        # Valid string should convert and work
        score = score_accommodation(row_valid)
        assert 0 <= score <= 100
        
        # Invalid string should raise TypeError
        with pytest.raises(TypeError):
            score_accommodation(row_invalid)


class TestRatingService:
    """Test cases for RatingService class."""
    
    def test_service_initialization(self):
        """Test RatingService can be initialized."""
        service = RatingService()
        assert service is not None
        
    def test_service_has_default_weights(self):
        """Test RatingService has correct default weights."""
        service = RatingService()
        expected_weights = {
            'tier': 4,
            'rating': 2,
            'parking': 1,
            'wheelchair': 1,
            'kids': 1,
            'pet': 1
        }
        assert service.default_weights == expected_weights