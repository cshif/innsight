"""Unit tests for services module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from src.innsight.services import (
    QueryService,
    GeocodeService, 
    AccommodationService,
    IsochroneService,
    TierService,
    AccommodationSearchService
)
from src.innsight.config import AppConfig
from src.innsight.exceptions import ParseError, GeocodeError


class TestQueryService:
    """Test cases for QueryService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QueryService()

    def test_extract_search_term_with_location(self):
        """Test extracting search term when location is present."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = 'Okinawa'
            
            result = self.service.extract_search_term("我想去沖繩的美ら海水族館")
            
            assert result == 'Okinawa'
            mock_parse.assert_called_once()
            mock_extract.assert_called_once()

    def test_extract_search_term_with_poi_only(self):
        """Test extracting search term when only POI is present."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = ''
            
            result = self.service.extract_search_term("想去水族館")
            
            assert result == 'aquarium'

    def test_extract_search_term_no_location_no_poi(self):
        """Test that missing location and POI raises ParseError."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': ''}
            mock_extract.return_value = ''
            
            with pytest.raises(ParseError, match="無法判斷地名或主行程"):
                self.service.extract_search_term("想住兩天")


class TestGeocodeService:
    """Test cases for GeocodeService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.config.api_endpoint = "http://example.com"
        self.config.nominatim_user_agent = "test"
        self.config.nominatim_timeout = 10
        self.service = GeocodeService(self.config)

    def test_client_lazy_initialization(self):
        """Test that client is lazily initialized."""
        assert self.service._client is None
        
        with patch('src.innsight.services.NominatimClient') as mock_client_class:
            client = self.service.client
            
            mock_client_class.assert_called_once_with(
                api_endpoint="http://example.com",
                user_agent="test", 
                timeout=10
            )
            assert self.service._client is not None

    def test_geocode_location_success(self):
        """Test successful geocoding."""
        mock_client = Mock()
        mock_client.geocode.return_value = [(25.0, 123.0)]
        self.service._client = mock_client
        
        result = self.service.geocode_location("Okinawa")
        
        assert result == (25.0, 123.0)
        mock_client.geocode.assert_called_once_with("Okinawa")

    def test_geocode_location_no_results(self):
        """Test geocoding with no results raises GeocodeError."""
        mock_client = Mock()
        mock_client.geocode.return_value = []
        self.service._client = mock_client
        
        with pytest.raises(GeocodeError, match="找不到地點"):
            self.service.geocode_location("NonexistentPlace")


class TestAccommodationService:
    """Test cases for AccommodationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = AccommodationService()

    def test_build_overpass_query(self):
        """Test building Overpass API query."""
        lat, lon = 25.0, 123.0
        query = self.service.build_overpass_query(lat, lon)
        
        assert "25.0,123.0" in query
        assert "tourism" in query
        assert "hotel" in query

    def test_fetch_accommodations(self):
        """Test fetching accommodations from API."""
        with patch('src.innsight.services.fetch_overpass') as mock_fetch:
            mock_elements = [
                {
                    "id": 1,
                    "type": "node",
                    "lat": 25.1,
                    "lon": 123.1,
                    "tags": {"tourism": "hotel", "name": "Test Hotel"}
                }
            ]
            mock_fetch.return_value = mock_elements
            
            result = self.service.fetch_accommodations(25.0, 123.0)
            
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
            assert result.iloc[0]['name'] == 'Test Hotel'

    def test_process_accommodation_elements(self):
        """Test processing accommodation elements into DataFrame."""
        elements = [
            {
                "id": 1,
                "type": "node", 
                "lat": 25.1,
                "lon": 123.1,
                "tags": {"tourism": "hotel", "name": "Test Hotel"}
            },
            {
                "id": 2,
                "type": "way",
                "center": {"lat": 25.2, "lon": 123.2},
                "tags": {"tourism": "guest_house", "name": "Test Guesthouse"}
            }
        ]
        
        result = self.service.process_accommodation_elements(elements)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert result.iloc[0]['osmid'] == 1
        assert result.iloc[0]['tourism'] == 'hotel'
        assert result.iloc[1]['osmid'] == 2
        assert result.iloc[1]['tourism'] == 'guest_house'


class TestIsochroneService:
    """Test cases for IsochroneService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.service = IsochroneService(self.config)

    def test_get_isochrones_with_fallback_success(self):
        """Test successful isochrone retrieval."""
        with patch('src.innsight.services.get_isochrones_by_minutes') as mock_get:
            mock_isochrones = [{'geometry': 'polygon1'}, {'geometry': 'polygon2'}]
            mock_get.return_value = mock_isochrones
            
            result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15, 30])
            
            assert result == mock_isochrones
            mock_get.assert_called_once_with((123.0, 25.0), [15, 30])

    def test_get_isochrones_with_fallback_cache_error(self):
        """Test fallback handling for cache errors."""
        with patch('src.innsight.services.get_isochrones_by_minutes') as mock_get:
            mock_get.side_effect = [Exception("cache error"), [{'geometry': 'polygon'}]]
            
            with patch('sys.stderr'):
                result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
                
            assert result == [{'geometry': 'polygon'}]

    def test_get_isochrones_with_fallback_non_cache_error(self):
        """Test handling of non-cache errors."""
        with patch('src.innsight.services.get_isochrones_by_minutes') as mock_get:
            mock_get.side_effect = Exception("network error")
            
            result = self.service.get_isochrones_with_fallback((123.0, 25.0), [15])
            
            assert result is None


class TestTierService:
    """Test cases for TierService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = TierService()

    def test_assign_tiers_with_isochrones(self):
        """Test tier assignment with valid isochrones."""
        df = pd.DataFrame({
            'osmid': [1, 2],
            'lat': [25.1, 25.2],
            'lon': [123.1, 123.2],
            'name': ['Hotel A', 'Hotel B']
        })
        
        mock_isochrones = [{'geometry': 'polygon1'}, {'geometry': 'polygon2'}]
        
        with patch('src.innsight.services.assign_tier') as mock_assign:
            mock_gdf = gpd.GeoDataFrame(df.copy())
            mock_gdf['tier'] = [1, 2]
            mock_assign.return_value = mock_gdf
            
            result = self.service.assign_tiers(df, mock_isochrones)
            
            assert isinstance(result, gpd.GeoDataFrame)
            mock_assign.assert_called_once_with(df, mock_isochrones)

    def test_assign_tiers_no_isochrones(self):
        """Test tier assignment when no isochrones available."""
        df = pd.DataFrame({
            'osmid': [1, 2],
            'lat': [25.1, 25.2],
            'lon': [123.1, 123.2],
            'name': ['Hotel A', 'Hotel B']
        })
        
        result = self.service.assign_tiers(df, None)
        
        assert isinstance(result, pd.DataFrame)
        assert all(result['tier'] == 0)

    def test_assign_tiers_empty_isochrones(self):
        """Test tier assignment with empty isochrones list."""
        df = pd.DataFrame({
            'osmid': [1, 2],
            'lat': [25.1, 25.2], 
            'lon': [123.1, 123.2],
            'name': ['Hotel A', 'Hotel B']
        })
        
        result = self.service.assign_tiers(df, [])
        
        assert isinstance(result, pd.DataFrame)
        assert all(result['tier'] == 0)


class TestAccommodationSearchService:
    """Test cases for AccommodationSearchService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.service = AccommodationSearchService(self.config)

    def test_service_initialization(self):
        """Test that all sub-services are properly initialized."""
        assert isinstance(self.service.query_service, QueryService)
        assert isinstance(self.service.geocode_service, GeocodeService)
        assert isinstance(self.service.accommodation_service, AccommodationService)
        assert isinstance(self.service.isochrone_service, IsochroneService)
        assert isinstance(self.service.tier_service, TierService)

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