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
from src.innsight.rating_service import RatingService
from src.innsight.config import AppConfig
from src.innsight.exceptions import ParseError, GeocodeError, NoAccommodationError


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
        
        # Check new columns exist
        assert 'rating' in result.columns
        assert 'tags' in result.columns


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


class TestRankAccommodationsService:
    """Test cases for rank_accommodations functionality - comprehensive acceptance criteria tests."""
    
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

    def test_correct_filter_application_parking_only(self):
        """正確套用過濾條件 - Given DataFrame 內同時存在 parking=yes 與 parking=no 的住宿；
        When 呼叫 rank_accommodations(df, filters=["parking"])；
        Then 回傳結果所有列的 tags.parking 必為 "yes"。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'}, 
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ],
            'tier': [1, 2, 1, 0],
            'rating': [4.0, 3.5, 4.5, 3.0],
            'score': [75.0, 65.0, 85.0, 45.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df, filters=["parking"])
        
        # All returned results must have parking='yes'
        for _, row in result.iterrows():
            assert row['tags']['parking'] == 'yes'
        
        # Should return 2 accommodations (osmid 1 and 3)
        assert len(result) == 2
        assert set(result['osmid'].tolist()) == {1, 3}

    def test_score_descending_order_with_specific_range(self):
        """依分數遞減排序 - Given 已算好 score 欄，其中最高分 92、最低分 55；
        When 不帶任何 filters 呼叫函式；
        Then 回傳列表第一筆 score ≥ 第二筆 ≥ … ≥ 最後一筆，且第一筆為 92，最後一筆為 55。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4, 5],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D', 'Hotel E'],
            'tags': [
                {'parking': 'yes'},
                {'parking': 'no'}, 
                {'parking': 'yes'},
                {'parking': 'no'},
                {'parking': 'yes'}
            ],
            'tier': [3, 1, 2, 0, 2],
            'rating': [5.0, 3.0, 4.0, 2.5, 4.5],
            'score': [92.0, 65.0, 78.0, 55.0, 85.0]  # Highest: 92, Lowest: 55
        })
        
        result = self.service.rank_accommodations(accommodations_df)
        
        # Check descending order
        scores = result['score'].tolist()
        assert scores == sorted(scores, reverse=True)
        
        # Check first and last scores
        assert result.iloc[0]['score'] == 92.0
        assert result.iloc[-1]['score'] == 55.0
        
        # Verify all scores are present
        assert len(result) == 5

    def test_top_n_limit(self):
        """筆數限制可調 - Given top_n=5 參數；
        When 資料表有 100 筆合格住宿；
        Then 函式只回傳 5 筆，且皆為分數前 5 名。"""
        
        # Create 100 accommodations with random scores
        import random
        random.seed(42)  # For reproducible results
        
        accommodations_data = []
        for i in range(100):
            accommodations_data.append({
                'osmid': i + 1,
                'name': f'Hotel {i+1}',
                'tags': {'parking': 'yes'},  # All have parking to ensure they're all eligible
                'tier': random.randint(0, 3),
                'rating': random.uniform(1.0, 5.0),
                'score': random.uniform(10.0, 100.0)
            })
        
        accommodations_df = gpd.GeoDataFrame(accommodations_data)
        
        result = self.service.rank_accommodations(accommodations_df, top_n=5)
        
        # Should return exactly 5 results
        assert len(result) == 5
        
        # Should be the top 5 by score
        all_scores = sorted(accommodations_df['score'].tolist(), reverse=True)
        top_5_scores = all_scores[:5]
        result_scores = result['score'].tolist()
        
        assert result_scores == top_5_scores

    def test_no_results_friendly_response_empty_dataframe(self):
        """無結果時友善回應 - Given filters 但資料皆不符合；
        When 呼叫函式；
        Then 拋 NoAccommodationError；絕不能崩潰。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2],
            'name': ['Hotel A', 'Hotel B'],
            'tags': [
                {'parking': 'no', 'wheelchair': 'no'},  # Neither has required amenities
                {'parking': 'no', 'wheelchair': 'no'}
            ],
            'tier': [1, 2],
            'rating': [4.0, 3.5],
            'score': [75.0, 65.0]
        })
        
        # Should raise NoAccommodationError, not crash
        with pytest.raises(NoAccommodationError) as exc_info:
            self.service.rank_accommodations(accommodations_df, filters=["wheelchair", "parking"])
        
        assert "No accommodations match the specified filters" in str(exc_info.value)

    def test_no_results_empty_input(self):
        """無結果時友善回應 - Given 空的 DataFrame；
        When 呼叫函式；
        Then 拋 NoAccommodationError。"""
        
        empty_df = gpd.GeoDataFrame()
        
        with pytest.raises(NoAccommodationError) as exc_info:
            self.service.rank_accommodations(empty_df)
        
        assert "No accommodations available to rank" in str(exc_info.value)

    def test_null_value_tolerance(self):
        """缺值容忍 - Given 某筆資料缺少 tags.parking；
        When 過濾條件不含 parking；
        Then 函式應照常運行並包含該筆資料（不可因 None 觸發例外）。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3],
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'tags': [
                {'wheelchair': 'yes'},  # Missing parking key
                {'parking': 'yes', 'wheelchair': 'yes'}, 
                {}  # Missing both keys
            ],
            'tier': [1, 2, 0],
            'rating': [4.0, 3.5, 3.0],
            'score': [75.0, 85.0, 55.0]
        })
        
        # Filter by wheelchair only (not parking), should work fine
        result = self.service.rank_accommodations(accommodations_df, filters=["wheelchair"])
        
        # Should return 2 accommodations (those with wheelchair='yes')
        assert len(result) == 2
        assert set(result['osmid'].tolist()) == {1, 2}
        
        # Should not crash due to missing parking values
        assert result.iloc[0]['score'] >= result.iloc[1]['score']  # Properly sorted

    def test_type_consistency_validation(self):
        """型別一致 - Given 成功回傳的結果；
        Then 每筆資料必含 name:str, score:float, tier:int；score 介於 0–100；tier 介於 0–3。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3],
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'tags': [
                {'parking': 'yes'},
                {'parking': 'yes'}, 
                {'parking': 'yes'}
            ],
            'tier': [1, 2, 3],
            'rating': [4.0, 3.5, 5.0],
            'score': [75.0, 85.0, 95.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df)
        
        for _, row in result.iterrows():
            # Check name is string or None
            assert isinstance(row['name'], (str, type(None)))
            
            # Check score is numeric and in range 0-100
            assert isinstance(row['score'], (int, float))
            assert 0 <= row['score'] <= 100
            
            # Check tier is int and in range 0-3
            assert isinstance(row['tier'], (int, float))
            assert 0 <= int(row['tier']) <= 3

    def test_type_validation_invalid_score_range(self):
        """Test validation catches invalid score ranges."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel A'],
            'tags': [{'parking': 'yes'}],
            'tier': [1],
            'rating': [4.0],
            'score': [150.0]  # Invalid: > 100
        })
        
        with pytest.raises(ValueError) as exc_info:
            self.service.rank_accommodations(accommodations_df)
        
        assert "score must be between 0-100" in str(exc_info.value)

    def test_type_validation_invalid_tier_range(self):
        """Test validation catches invalid tier ranges."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel A'],
            'tags': [{'parking': 'yes'}],
            'tier': [5],  # Invalid: > 3
            'rating': [4.0],
            'score': [75.0]
        })
        
        with pytest.raises(ValueError) as exc_info:
            self.service.rank_accommodations(accommodations_df)
        
        assert "tier must be between 0-3" in str(exc_info.value)

    def test_multiple_filters_integration(self):
        """Test multiple filters work correctly together."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'yes'},  # Matches all
                {'parking': 'yes', 'wheelchair': 'no', 'kids': 'yes'},   # Missing wheelchair
                {'parking': 'no', 'wheelchair': 'yes', 'kids': 'yes'},   # Missing parking
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'no'}    # Missing kids
            ],
            'tier': [3, 2, 1, 2],
            'rating': [5.0, 4.0, 4.5, 4.2],
            'score': [95.0, 80.0, 85.0, 82.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df, filters=["parking", "wheelchair", "kids"])
        
        # Only Hotel A should match all three filters
        assert len(result) == 1
        assert result.iloc[0]['osmid'] == 1
        assert result.iloc[0]['score'] == 95.0

    def test_performance_10000_records(self):
        """效能 - Given 10 000 筆住宿資料、随機 0–4 個條件；
        When 單執行緒批次呼叫 rank_accommodations；
        Then 整體運行時間 ≤ 0.2 秒（開發機）。"""
        
        import time
        import random
        random.seed(42)  # For reproducible results
        
        # Create 10,000 accommodations
        accommodations_data = []
        for i in range(10000):
            # Randomly assign amenities to create realistic filtering scenarios
            tags = {}
            if random.random() > 0.5:
                tags['parking'] = 'yes' if random.random() > 0.3 else 'no'
            if random.random() > 0.5:
                tags['wheelchair'] = 'yes' if random.random() > 0.2 else 'no'
            if random.random() > 0.5:  
                tags['kids'] = 'yes' if random.random() > 0.4 else 'no'
            if random.random() > 0.5:
                tags['pet'] = 'yes' if random.random() > 0.6 else 'no'
                
            accommodations_data.append({
                'osmid': i + 1,
                'name': f'Hotel {i+1}',
                'tags': tags,
                'tier': random.randint(0, 3),
                'rating': random.uniform(1.0, 5.0),
                'score': random.uniform(10.0, 100.0)
            })
        
        accommodations_df = gpd.GeoDataFrame(accommodations_data)
        
        # Test multiple scenarios with different filter combinations
        test_scenarios = [
            [],  # No filters
            ['parking'],
            ['wheelchair', 'parking'],
            ['kids', 'pet'],
            ['parking', 'wheelchair', 'kids', 'pet']  # All filters
        ]
        
        start_time = time.time()
        
        # Run multiple calls to simulate batch processing
        for scenario in test_scenarios:
            try:
                result = self.service.rank_accommodations(accommodations_df, filters=scenario, top_n=50)
                # Basic validation that the function works
                assert isinstance(result, gpd.GeoDataFrame)
                assert len(result) <= 50
            except NoAccommodationError:
                # This is acceptable for some filter combinations
                pass
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within 0.2 seconds
        assert total_time <= 0.2, f"Performance test failed: took {total_time:.3f} seconds, expected ≤ 0.2s"