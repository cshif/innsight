"""Integration tests for the innsight application."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import os

from src.innsight.services import AccommodationSearchService
from src.innsight.config import AppConfig
from src.innsight.cli import main
from src.innsight.exceptions import ParseError, GeocodeError, ConfigurationError


class TestEndToEndIntegration:
    """Integration tests for complete workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=AppConfig)
        self.mock_config.api_endpoint = "http://test-nominatim.example.com"
        self.mock_config.nominatim_user_agent = "test-agent"
        self.mock_config.nominatim_timeout = 10

    def test_complete_accommodation_search_flow(self):
        """Test complete flow from query to results."""
        query = "我想去沖繩的美ら海水族館住兩天"
        
        # Mock all external API calls
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract_location, \
             patch('src.innsight.services.NominatimClient') as mock_nominatim_class, \
             patch('src.innsight.services.fetch_overpass') as mock_overpass, \
             patch('src.innsight.services.get_isochrones_by_minutes') as mock_isochrones, \
             patch('src.innsight.services.assign_tier') as mock_assign_tier:
            
            # Setup mock returns
            mock_parse.return_value = {'poi': 'aquarium', 'days': '2'}
            mock_extract_location.return_value = 'Okinawa'
            
            mock_nominatim_client = Mock()
            mock_nominatim_client.geocode.return_value = [(26.2042, 127.6792)]
            mock_nominatim_class.return_value = mock_nominatim_client
            
            mock_overpass.return_value = [
                {
                    "id": 123456,
                    "type": "node",
                    "lat": 26.3,
                    "lon": 127.8,
                    "tags": {"tourism": "hotel", "name": "沖繩海洋酒店"}
                },
                {
                    "id": 789012,
                    "type": "way",
                    "center": {"lat": 26.4, "lon": 127.9},
                    "tags": {"tourism": "guest_house", "name": "美ら海民宿"}
                }
            ]
            
            mock_isochrones.return_value = [
                {'geometry': Polygon([(127.75, 26.25), (127.85, 26.25), (127.85, 26.35), (127.75, 26.35)])},
                {'geometry': Polygon([(127.7, 26.2), (127.9, 26.2), (127.9, 26.4), (127.7, 26.4)])},
                {'geometry': Polygon([(127.6, 26.1), (128.0, 26.1), (128.0, 26.5), (127.6, 26.5)])}
            ]
            
            # Mock tier assignment
            mock_gdf = gpd.GeoDataFrame({
                'osmid': [123456, 789012],
                'name': ['沖繩海洋酒店', '美ら海民宿'],
                'tier': [1, 2]
            })
            mock_assign_tier.return_value = mock_gdf
            
            # Execute the search
            service = AccommodationSearchService(self.mock_config)
            result = service.search_accommodations(query)
            
            # Verify results
            assert isinstance(result, gpd.GeoDataFrame)
            assert len(result) == 2
            assert result.iloc[0]['name'] == '沖繩海洋酒店'
            assert result.iloc[0]['tier'] == 1
            assert result.iloc[1]['name'] == '美ら海民宿'
            assert result.iloc[1]['tier'] == 2
            
            # Verify all services were called with correct parameters
            mock_parse.assert_called_once_with(query)
            mock_extract_location.assert_called_once()
            mock_nominatim_client.geocode.assert_called_once_with('Okinawa')
            mock_overpass.assert_called_once()
            mock_isochrones.assert_called_once_with((127.6792, 26.2042), [15, 30, 60])
            mock_assign_tier.assert_called_once()

    def test_cli_integration_with_mocked_services(self):
        """Test CLI integration with mocked services."""
        # Mock the entire search service
        with patch('src.innsight.cli.AppConfig') as mock_config_class, \
             patch('src.innsight.cli.AccommodationSearchService') as mock_service_class:
            
            # Setup config mock
            mock_config = Mock()
            mock_config_class.from_env.return_value = mock_config
            
            # Setup service mock
            mock_service = Mock()
            mock_gdf = gpd.GeoDataFrame({
                'name': ['Test Hotel', 'Test Guesthouse'],
                'tier': [1, 2]
            })
            mock_service.search_accommodations.return_value = mock_gdf
            mock_service_class.return_value = mock_service
            
            # Test CLI call
            result = main(['我想去東京住一天'])
            
            assert result == 0
            mock_config_class.from_env.assert_called_once()
            mock_service_class.assert_called_once_with(mock_config)
            mock_service.search_accommodations.assert_called_once_with('我想去東京住一天')

    def test_error_propagation_through_layers(self):
        """Test that errors propagate correctly through service layers."""
        # Test ParseError propagation
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': ''}
            mock_extract.return_value = ''
            
            service = AccommodationSearchService(self.mock_config)
            
            with pytest.raises(ParseError, match="無法判斷地名或主行程"):
                service.search_accommodations("想住兩天")

    def test_geocoding_error_propagation(self):
        """Test geocoding error propagation."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract, \
             patch('src.innsight.services.NominatimClient') as mock_nominatim_class:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = 'InvalidPlace'
            
            mock_nominatim_client = Mock()
            mock_nominatim_client.geocode.return_value = []  # No results
            mock_nominatim_class.return_value = mock_nominatim_client
            
            service = AccommodationSearchService(self.mock_config)
            
            with pytest.raises(GeocodeError, match="找不到地點"):
                service.search_accommodations("我想去不存在的地方")

    def test_empty_accommodation_results(self):
        """Test handling of empty accommodation results."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract, \
             patch('src.innsight.services.NominatimClient') as mock_nominatim_class, \
             patch('src.innsight.services.fetch_overpass') as mock_overpass:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = 'RemoteLocation'
            
            mock_nominatim_client = Mock()
            mock_nominatim_client.geocode.return_value = [(26.0, 127.0)]
            mock_nominatim_class.return_value = mock_nominatim_client
            
            mock_overpass.return_value = []  # No accommodations found
            
            service = AccommodationSearchService(self.mock_config)
            result = service.search_accommodations("我想去偏僻地方")
            
            assert isinstance(result, gpd.GeoDataFrame)
            assert len(result) == 0

    def test_isochrone_failure_fallback(self):
        """Test fallback when isochrones cannot be calculated."""
        with patch('src.innsight.services.parse_query') as mock_parse, \
             patch('src.innsight.services.extract_location_from_query') as mock_extract, \
             patch('src.innsight.services.NominatimClient') as mock_nominatim_class, \
             patch('src.innsight.services.fetch_overpass') as mock_overpass, \
             patch('src.innsight.services.get_isochrones_by_minutes') as mock_isochrones:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = 'TestLocation'
            
            mock_nominatim_client = Mock()
            mock_nominatim_client.geocode.return_value = [(26.0, 127.0)]
            mock_nominatim_class.return_value = mock_nominatim_client
            
            mock_overpass.return_value = [
                {
                    "id": 123,
                    "type": "node",
                    "lat": 26.1,
                    "lon": 127.1,
                    "tags": {"tourism": "hotel", "name": "Test Hotel"}
                }
            ]
            
            mock_isochrones.side_effect = Exception("Isochrone service unavailable")
            
            service = AccommodationSearchService(self.mock_config)
            result = service.search_accommodations("我想去測試地點")
            
            # Should return empty result when isochrones fail
            assert isinstance(result, gpd.GeoDataFrame)
            assert len(result) == 0


class TestConfigurationIntegration:
    """Integration tests for configuration management."""

    def test_config_from_environment_variables(self):
        """Test configuration loading from environment variables."""
        test_env = {
            'API_ENDPOINT': 'http://test-api.example.com',
            'ORS_URL': 'http://test-ors.example.com',
            'ORS_API_KEY': 'test-api-key'
        }
        
        with patch.dict(os.environ, test_env):
            config = AppConfig.from_env()
            
            assert config.api_endpoint == 'http://test-api.example.com'
            assert config.ors_url == 'http://test-ors.example.com'
            assert config.ors_api_key == 'test-api-key'
            assert config.nominatim_user_agent == 'innsight'  # default value
            assert config.nominatim_timeout == 10  # default value

    def test_missing_environment_variables(self):
        """Test error handling for missing environment variables."""
        # Test missing API_ENDPOINT
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="API_ENDPOINT environment variable not set"):
                AppConfig.from_env()
        
        # Test missing ORS_URL
        with patch.dict(os.environ, {'API_ENDPOINT': 'http://test.com'}, clear=True):
            with pytest.raises(ConfigurationError, match="ORS_URL environment variable not set"):
                AppConfig.from_env()
        
        # Test missing ORS_API_KEY
        with patch.dict(os.environ, {
            'API_ENDPOINT': 'http://test.com',
            'ORS_URL': 'http://ors.com'
        }, clear=True):
            with pytest.raises(ConfigurationError, match="ORS_API_KEY environment variable not set"):
                AppConfig.from_env()


class TestServiceLayerIntegration:
    """Integration tests for service layer interactions."""

    def test_service_dependency_injection(self):
        """Test that services are properly injected with dependencies."""
        mock_config = Mock(spec=AppConfig)
        mock_config.api_endpoint = "http://test.com"
        mock_config.nominatim_user_agent = "test"
        mock_config.nominatim_timeout = 10
        
        service = AccommodationSearchService(mock_config)
        
        # Verify all sub-services are created
        assert service.query_service is not None
        assert service.geocode_service is not None
        assert service.accommodation_service is not None
        assert service.isochrone_service is not None
        assert service.tier_service is not None
        
        # Verify configuration is passed to services that need it
        assert service.geocode_service.config == mock_config
        assert service.isochrone_service.config == mock_config

    def test_service_coordination(self):
        """Test coordination between different services."""
        mock_config = Mock(spec=AppConfig)
        
        # Create service with mocked dependencies
        service = AccommodationSearchService(mock_config)
        service.query_service = Mock()
        service.geocode_service = Mock()
        service.accommodation_service = Mock()
        service.isochrone_service = Mock()
        service.tier_service = Mock()
        
        # Setup return values to trace the data flow
        service.query_service.extract_search_term.return_value = "TestLocation"
        service.geocode_service.geocode_location.return_value = (26.0, 127.0)
        
        test_df = pd.DataFrame({
            'osmid': [1, 2],
            'name': ['Hotel A', 'Hotel B']
        })
        service.accommodation_service.fetch_accommodations.return_value = test_df
        
        mock_isochrones = [{'geometry': 'test_polygon'}]
        service.isochrone_service.get_isochrones_with_fallback.return_value = mock_isochrones
        
        result_gdf = gpd.GeoDataFrame(test_df)
        result_gdf['tier'] = [1, 2]
        service.tier_service.assign_tiers.return_value = result_gdf
        
        # Execute search
        result = service.search_accommodations("test query")
        
        # Verify the data flows correctly through all services
        service.query_service.extract_search_term.assert_called_once_with("test query")
        service.geocode_service.geocode_location.assert_called_once_with("TestLocation")
        service.accommodation_service.fetch_accommodations.assert_called_once_with(26.0, 127.0)
        service.isochrone_service.get_isochrones_with_fallback.assert_called_once_with((127.0, 26.0), [15, 30, 60])
        service.tier_service.assign_tiers.assert_called_once_with(test_df, mock_isochrones)
        
        assert result is result_gdf