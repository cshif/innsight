"""Rating service for calculating accommodation scores."""

import warnings
import pandas as pd
from typing import Dict, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import AppConfig


def _get_default_weights() -> Dict[str, float]:
    """Get default rating weights from AppConfig."""
    from .config import AppConfig
    default_config = AppConfig(
        api_endpoint="",
        ors_url="",
        ors_api_key=""
    )
    return default_config.rating_weights.copy()


def _validate_weights(weights: Dict[str, float]) -> None:
    """Validate that weights are non-negative and not all zero."""
    # Validate weights are non-negative
    for key, weight in weights.items():
        if weight < 0:
            raise ValueError("weights must be ≥0")
    
    # Check if all weights sum to zero
    if sum(weights.values()) == 0:
        raise ZeroDivisionError("All weights cannot be zero")


def _merge_weights(provided_weights: Optional[Dict[str, float]], default_weights: Dict[str, float]) -> Dict[str, float]:
    """Merge provided weights with defaults for missing keys."""
    if provided_weights is None:
        return default_weights
    
    # Merge with defaults for missing keys, ignore extra keys
    final_weights = default_weights.copy()
    for key in default_weights:
        if key in provided_weights:
            final_weights[key] = provided_weights[key]
    return final_weights


def _extract_row_data(row: Union[Dict, pd.Series]) -> tuple:
    """Extract tier, rating, and tags from row data."""
    if isinstance(row, pd.Series):
        tier = row.get('tier')
        rating = row.get('rating')
        tags = row.get('tags', {})
    else:
        tier = row.get('tier')
        rating = row.get('rating')
        tags = row.get('tags', {})
    return tier, rating, tags


def _validate_tier(tier: Optional[int]) -> None:
    """Validate tier bounds."""
    if tier is not None and (tier < 0 or tier > 3):
        raise ValueError("tier must be 0-3")


def _convert_rating(rating: Optional[Union[str, float]]) -> Optional[float]:
    """Convert and validate rating value."""
    if rating is not None and isinstance(rating, str):
        try:
            rating = float(rating)
        except ValueError:
            raise TypeError(f"Cannot convert rating '{rating}' to float")
    return rating


def _calculate_component_scores(tier: Optional[int], rating: Optional[float], tags: dict) -> Dict[str, float]:
    """Calculate scores for all components."""
    import pandas as pd
    scores = {}
    
    # Tier score: 0->0, 1->33.33, 2->66.67, 3->100
    if tier is not None and not pd.isna(tier):
        scores['tier'] = (tier / 3.0) * 100
    else:
        scores['tier'] = 50  # Default for missing tier
    
    # Rating score: 0-5 scale -> 0-100 scale
    if rating is not None and not pd.isna(rating):
        scores['rating'] = (rating / 5.0) * 100
    else:
        scores['rating'] = 50  # Default for missing rating
    
    # Tag scores: yes->100, no->0, unknown->50 with warning
    tag_keys = ['parking', 'wheelchair', 'kids', 'pet']
    for tag_key in tag_keys:
        tag_value = tags.get(tag_key)
        if tag_value == 'yes':
            scores[tag_key] = 100
        elif tag_value == 'no':
            scores[tag_key] = 0
        elif tag_value is None:
            scores[tag_key] = 50  # Default for missing tag
        else:
            # Unknown value - use 50 and warn
            scores[tag_key] = 50
            warnings.warn(f"Unknown tag value '{tag_value}' for {tag_key}, using default 50")
    
    return scores


def _calculate_weighted_score(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """Calculate final weighted average score."""
    total_weighted_score = 0
    total_weight = 0
    
    for component, score in scores.items():
        weight = weights.get(component, 0)
        total_weighted_score += score * weight
        total_weight += weight
    
    # Final score (0-100)
    return total_weighted_score / total_weight if total_weight > 0 else 0


class RatingService:
    """Service for calculating accommodation ratings."""
    
    def __init__(self, config: Optional['AppConfig'] = None):
        """Initialize the rating service with weights from config."""
        if config is not None:
            self.default_weights = config.rating_weights.copy()
        else:
            self.default_weights = _get_default_weights()
    
    def score(self, row: Union[Dict, pd.Series], weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate accommodation score using this service's configured weights.
        
        Args:
            row: Accommodation data containing tier, rating, and tags
            weights: Optional weight overrides for scoring components
            
        Returns:
            float: Score between 0-100
        """
        return score_accommodation(row, weights=weights, default_weights=self.default_weights)


def score_accommodation(row: Union[Dict, pd.Series], weights: Optional[Dict[str, float]] = None, default_weights: Optional[Dict[str, float]] = None) -> float:
    """
    Calculate accommodation score based on tier, rating, and amenity tags.
    
    Args:
        row: Accommodation data containing tier, rating, and tags
        weights: Optional weight overrides for scoring components
        default_weights: Optional default weights to use (falls back to hard-coded defaults)
        
    Returns:
        float: Score between 0-100
        
    Raises:
        ValueError: If tier is out of bounds (0-3) or weights are negative
        ZeroDivisionError: If all weights sum to zero
        TypeError: If rating string cannot be converted to float
    """
    # Use provided default weights or fallback to AppConfig defaults
    if default_weights is None:
        default_weights = _get_default_weights()
    
    # Merge weights and validate
    weights = _merge_weights(weights, default_weights)
    _validate_weights(weights)
    
    # Extract and validate data
    tier, rating, tags = _extract_row_data(row)
    _validate_tier(tier)
    rating = _convert_rating(rating)
    
    # Calculate component scores
    scores = _calculate_component_scores(tier, rating, tags)
    
    # Calculate final weighted score
    return _calculate_weighted_score(scores, weights)