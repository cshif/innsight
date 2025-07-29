"""Unit tests for AccommodationSearchService."""

import pytest
from unittest.mock import Mock
import pandas as pd
import geopandas as gpd

from src.innsight.services.accommodation_search_service import AccommodationSearchService
from src.innsight.services.query_service import QueryService
from src.innsight.services.geocode_service import GeocodeService
from src.innsight.services.accommodation_service import AccommodationService
from src.innsight.services.isochrone_service import IsochroneService
from src.innsight.services.tier_service import TierService
from src.innsight.rating_service import RatingService
from src.innsight.config import AppConfig
from src.innsight.exceptions import NoAccommodationError


class TestAccommodationSearchService:
    """Test cases for AccommodationSearchService."""

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
        self.service = AccommodationSearchService(self.config)

    def test_service_initialization(self):
        """Test that all sub-services are properly initialized."""
        assert isinstance(self.service.query_service, QueryService)
        assert isinstance(self.service.geocode_service, GeocodeService)
        assert isinstance(self.service.accommodation_service, AccommodationService)
        assert isinstance(self.service.isochrone_service, IsochroneService)
        assert isinstance(self.service.tier_service, TierService)
        assert isinstance(self.service.rating_service, RatingService)

    def test_search_accommodations_success(self):
        """Test successful accommodation search."""
        query = "我想去沖繩的美ら海水族館"
        
        # Mock all the sub-services
        self.service.query_service = Mock()
        self.service.geocode_service = Mock()
        self.service.accommodation_service = Mock()
        self.service.isochrone_service = Mock()
        self.service.tier_service = Mock()
        
        # Set up return values
        self.service.query_service.extract_search_term.return_value = "Okinawa"
        self.service.geocode_service.geocode_location.return_value = (25.0, 123.0)
        
        mock_df = pd.DataFrame({
            'osmid': [1],
            'name': ['Test Hotel'],
            'lat': [25.1],
            'lon': [123.1]
        })
        self.service.accommodation_service.fetch_accommodations.return_value = mock_df
        
        mock_isochrones = [{'geometry': 'polygon'}]
        self.service.isochrone_service.get_isochrones_with_fallback.return_value = mock_isochrones
        
        mock_gdf = gpd.GeoDataFrame(mock_df)
        mock_gdf['tier'] = [1]
        self.service.tier_service.assign_tiers.return_value = mock_gdf
        
        result = self.service.search_accommodations(query)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 1
        
        # Verify all services were called
        self.service.query_service.extract_search_term.assert_called_once_with(query)
        self.service.geocode_service.geocode_location.assert_called_once_with("Okinawa")
        self.service.accommodation_service.fetch_accommodations.assert_called_once_with(25.0, 123.0)
        self.service.isochrone_service.get_isochrones_with_fallback.assert_called_once_with((123.0, 25.0), [15, 30, 60])
        self.service.tier_service.assign_tiers.assert_called_once_with(mock_df, mock_isochrones)

    def test_search_accommodations_no_accommodations_found(self):
        """Test when no accommodations are found."""
        query = "我想去沖繩的美ら海水族館"
        
        self.service.query_service = Mock()
        self.service.geocode_service = Mock()
        self.service.accommodation_service = Mock()
        
        self.service.query_service.extract_search_term.return_value = "Okinawa"
        self.service.geocode_service.geocode_location.return_value = (25.0, 123.0)
        
        empty_df = pd.DataFrame()
        self.service.accommodation_service.fetch_accommodations.return_value = empty_df
        
        result = self.service.search_accommodations(query)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 0

    def test_search_accommodations_no_isochrones(self):
        """Test when isochrones cannot be retrieved."""
        query = "我想去沖繩的美ら海水族館"
        
        # Mock all services
        self.service.query_service = Mock()
        self.service.geocode_service = Mock()
        self.service.accommodation_service = Mock()
        self.service.isochrone_service = Mock()
        
        self.service.query_service.extract_search_term.return_value = "Okinawa"
        self.service.geocode_service.geocode_location.return_value = (25.0, 123.0)
        
        mock_df = pd.DataFrame({
            'osmid': [1],
            'name': ['Test Hotel']
        })
        self.service.accommodation_service.fetch_accommodations.return_value = mock_df
        self.service.isochrone_service.get_isochrones_with_fallback.return_value = None
        
        result = self.service.search_accommodations(query)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 0


class TestAccommodationFilteringService:
    """Test cases for accommodation filtering functionality."""
    
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
        self.service = AccommodationSearchService(self.config)
    
    def test_filter_accommodations_by_parking_required(self):
        """Test filtering accommodations that have parking when parking is required."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3],
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'}, 
                {'parking': 'yes', 'wheelchair': 'yes'}
            ],
            'tier': [1, 2, 1],
            'rating': [4.0, 3.5, 4.5],
            'score': [75.0, 65.0, 85.0]
        })
        
        user_conditions = {'parking': True}
        
        result = self.service.filter_accommodations(accommodations_df, user_conditions)
        
        assert len(result) == 2
        assert set(result['osmid'].tolist()) == {1, 3}
        
    def test_filter_accommodations_by_multiple_conditions(self):
        """Test filtering by multiple user conditions."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'no'},
                {'parking': 'no', 'wheelchair': 'yes', 'kids': 'yes'}, 
                {'parking': 'yes', 'wheelchair': 'no', 'kids': 'yes'},
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'yes'}
            ],
            'tier': [1, 2, 1, 3],
            'rating': [4.0, 3.5, 4.5, 5.0],
            'score': [80.0, 70.0, 75.0, 95.0]
        })
        
        user_conditions = {'parking': True, 'wheelchair': True, 'kids': True}
        
        result = self.service.filter_accommodations(accommodations_df, user_conditions)
        
        assert len(result) == 1  
        assert result.iloc[0]['osmid'] == 4
        
    def test_filter_accommodations_no_conditions(self):
        """Test that no filtering occurs when no conditions are specified."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2],
            'name': ['Hotel A', 'Hotel B'],
            'tags': [{'parking': 'yes'}, {'parking': 'no'}],
            'score': [80.0, 70.0]
        })
        
        user_conditions = {}
        
        result = self.service.filter_accommodations(accommodations_df, user_conditions)
        
        assert len(result) == 2
        assert result.equals(accommodations_df)


class TestAccommodationSortingService:
    """Test cases for accommodation sorting functionality."""
    
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
        self.service = AccommodationSearchService(self.config)
    
    def test_sort_accommodations_by_score_descending(self):
        """Test sorting accommodations by score in descending order."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'score': [75.0, 95.0, 65.0, 85.0],
            'tier': [1, 3, 0, 2],
            'rating': [4.0, 5.0, 3.0, 4.5]
        })
        
        result = self.service.sort_accommodations(accommodations_df)
        
        expected_order = [2, 4, 1, 3]  # osmids in descending score order: 95, 85, 75, 65
        assert result['osmid'].tolist() == expected_order
        
        # Verify scores are in descending order
        scores = result['score'].tolist()
        assert scores == sorted(scores, reverse=True)
        
    def test_sort_accommodations_empty_dataframe(self):
        """Test sorting empty dataframe returns empty result."""
        empty_df = gpd.GeoDataFrame()
        
        result = self.service.sort_accommodations(empty_df)
        
        assert len(result) == 0
        assert isinstance(result, gpd.GeoDataFrame)
        
    def test_sort_accommodations_single_item(self):
        """Test sorting single accommodation returns same item."""
        single_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel A'],
            'score': [75.0]
        })
        
        result = self.service.sort_accommodations(single_df)
        
        assert len(result) == 1
        assert result.iloc[0]['osmid'] == 1