"""Integration tests for rating functionality with AccommodationSearchService."""

import pytest
import pandas as pd
import geopandas as gpd
from unittest.mock import Mock, patch
from src.innsight.services import AccommodationSearchService
from src.innsight.config import AppConfig


class TestRatingIntegration:
    """Test rating integration with accommodation search."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.config.rating_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        # Add new configuration properties
        self.config.default_isochrone_intervals = [15, 30, 60]
        self.config.max_score = 100
        self.config.validation_sample_size = 10
        self.config.validation_large_dataset_threshold = 100
        self.config.default_top_n = 10
        self.config.default_missing_score = 50
        self.config.max_tier_value = 3
        self.config.max_rating_value = 5
        self.service = AccommodationSearchService(self.config)
    
    def test_search_accommodations_includes_score(self):
        """Test that search results include score column."""
        # Mock all the sub-services
        self.service.query_service = Mock()
        self.service.geocode_service = Mock()
        self.service.accommodation_service = Mock()
        self.service.isochrone_service = Mock()
        self.service.tier_service = Mock()
        
        # Set up return values
        self.service.query_service.extract_search_term.return_value = "Okinawa"
        self.service.geocode_service.geocode_location.return_value = (25.0, 123.0)
        
        # Mock accommodation data with rating and tags
        mock_df = pd.DataFrame({
            'osmid': [1, 2],
            'name': ['Hotel A', 'Hotel B'],
            'lat': [25.1, 25.2],
            'lon': [123.1, 123.2],
            'rating': [4.5, 3.0],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ]
        })
        self.service.accommodation_service.fetch_accommodations.return_value = mock_df
        
        mock_isochrones = [{'geometry': 'polygon'}]
        self.service.isochrone_service.get_isochrones_with_fallback.return_value = mock_isochrones
        
        # Mock tier assignment
        mock_gdf = gpd.GeoDataFrame(mock_df.copy())
        mock_gdf['tier'] = [3, 1]  # Hotel A gets higher tier
        self.service.tier_service.assign_tiers.return_value = mock_gdf
        
        # When
        result = self.service.search_accommodations("我想去沖繩住宿")
        
        # Then
        assert 'score' in result.columns
        assert len(result) == 2
        assert all(0 <= score <= 100 for score in result['score'])
        
        # Hotel A should have higher score (higher tier and rating)
        hotel_a_score = result[result['name'] == 'Hotel A']['score'].iloc[0]
        hotel_b_score = result[result['name'] == 'Hotel B']['score'].iloc[0]
        assert hotel_a_score > hotel_b_score
    
    def test_accommodation_service_extracts_rating_and_tags(self):
        """Test that AccommodationService extracts rating and amenity tags."""
        service = self.service.accommodation_service
        
        # Mock OSM elements with various tag formats
        elements = [
            {
                "id": 1,
                "type": "node",
                "lat": 25.1,
                "lon": 123.1,
                "tags": {
                    "tourism": "hotel",
                    "name": "Test Hotel",
                    "rating": "4.5",
                    "parking": "yes",
                    "wheelchair": "yes",
                    "family_friendly": "yes",
                    "pets": "yes"
                }
            },
            {
                "id": 2,
                "type": "way",
                "center": {"lat": 25.2, "lon": 123.2},
                "tags": {
                    "tourism": "guest_house",
                    "name": "Test Guesthouse",
                    "stars": "3",
                    "parking": "no",
                    "wheelchair": "no"
                }
            }
        ]
        
        result = service.process_accommodation_elements(elements)
        
        # Check data structure
        assert 'rating' in result.columns
        assert 'tags' in result.columns
        
        # Check first hotel
        hotel_row = result.iloc[0]
        assert hotel_row['rating'] == 4.5
        assert hotel_row['tags']['parking'] == 'yes'
        assert hotel_row['tags']['wheelchair'] == 'yes'
        assert hotel_row['tags']['kids'] == 'yes'
        assert hotel_row['tags']['pet'] == 'yes'
        
        # Check second guesthouse
        guesthouse_row = result.iloc[1]
        assert guesthouse_row['rating'] == 3.0
        assert guesthouse_row['tags']['parking'] == 'no'
        assert guesthouse_row['tags']['wheelchair'] == 'no'
        assert guesthouse_row['tags']['kids'] is None
        assert guesthouse_row['tags']['pet'] is None
    
    def test_extract_rating_various_formats(self):
        """Test rating extraction from various OSM tag formats."""
        service = self.service.accommodation_service
        
        # Test different rating fields
        test_cases = [
            ({'rating': '4.5'}, 4.5),
            ({'stars': '5'}, 5.0),
            ({'quality': '3.2'}, 3.2),
            ({'rating': 'invalid'}, None),
            ({}, None),
            ({'other_field': '4.0'}, None)
        ]
        
        for tags, expected in test_cases:
            result = service._extract_rating(tags)
            assert result == expected
    
    def test_extract_amenity_tags_various_formats(self):
        """Test amenity tag extraction from various OSM formats."""
        service = self.service.accommodation_service
        
        # Test parking detection
        parking_tests = [
            ({'parking': 'yes'}, 'yes'),
            ({'parking': 'no'}, 'no'),
            ({'parking:fee': 'no'}, 'yes'),  # Free parking
            ({}, None)
        ]
        
        for tags, expected in parking_tests:
            result = service._extract_amenity_tags(tags)
            assert result['parking'] == expected
        
        # Test kids friendly detection
        kids_tests = [
            ({'family_friendly': 'yes'}, 'yes'),
            ({'kids': 'true'}, 'yes'),
            ({'children': 'yes'}, 'yes'),
            ({}, None)
        ]
        
        for tags, expected in kids_tests:
            result = service._extract_amenity_tags(tags)
            assert result['kids'] == expected
        
        # Test pet friendly detection
        pet_tests = [
            ({'pets': 'yes'}, 'yes'),
            ({'pets_allowed': 'true'}, 'yes'),
            ({'dogs': 'yes'}, 'yes'),
            ({}, None)
        ]
        
        for tags, expected in pet_tests:
            result = service._extract_amenity_tags(tags)
            assert result['pet'] == expected