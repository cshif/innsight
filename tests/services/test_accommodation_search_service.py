"""Unit tests for AccommodationSearchService."""

from unittest.mock import Mock
import pandas as pd
import geopandas as gpd
import pytest

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


class TestMarkdownOutputService:
    """Test cases for markdown output functionality."""
    
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
    
    def test_format_accommodations_as_markdown_basic(self):
        """Test basic markdown formatting of accommodation results."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2], 
            'name': ['Hotel A', 'Hotel B'],
            'tier': [3, 1],
            'rating': [4.5, 3.0],
            'score': [95.0, 75.0],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ]
        })
        
        # This should fail initially as the method doesn't exist yet
        markdown_output = self.service.format_accommodations_as_markdown(accommodations_df)
        
        # Expected Markdown format
        expected_lines = [
            "# 住宿推薦結果",
            "",
            "## 1. Hotel A",
            "**分數:** 95.0",
            "**等級:** 3",
            "**評分:** 4.5",
            "**設施:**",
            "- 停車場: ✅",
            "- 無障礙: ✅",
            "",
            "## 2. Hotel B", 
            "**分數:** 75.0",
            "**等級:** 1",
            "**評分:** 3.0",
            "**設施:**",
            "- 停車場: ❌",
            "- 無障礙: ❌"
        ]
        
        assert markdown_output == "\n".join(expected_lines)
    
    def test_format_accommodations_as_markdown_empty(self):
        """Test markdown formatting with empty DataFrame."""
        empty_df = gpd.GeoDataFrame()
        
        markdown_output = self.service.format_accommodations_as_markdown(empty_df)
        
        expected = "# 住宿推薦結果\n\n沒有找到符合條件的住宿。"
        assert markdown_output == expected
    
    def test_format_accommodations_as_markdown_missing_tags(self):
        """Test markdown formatting with missing amenity tags."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel C'],
            'tier': [2],
            'rating': [4.0],
            'score': [80.0],
            'tags': [{}]  # Empty tags
        })
        
        markdown_output = self.service.format_accommodations_as_markdown(accommodations_df)
        
        expected_lines = [
            "# 住宿推薦結果",
            "",
            "## 1. Hotel C",
            "**分數:** 80.0",
            "**等級:** 2", 
            "**評分:** 4.0",
            "**設施:**"
        ]
        
        assert markdown_output == "\n".join(expected_lines)
    
    def test_format_accommodations_as_markdown_partial_amenities(self):
        """Test markdown formatting with partial amenity information."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel D'],
            'tier': [1],
            'rating': [3.5],
            'score': [70.0],
            'tags': [{'parking': 'yes', 'kids': 'no'}]  # Only some amenities
        })
        
        markdown_output = self.service.format_accommodations_as_markdown(accommodations_df)
        
        expected_lines = [
            "# 住宿推薦結果",
            "",
            "## 1. Hotel D",
            "**分數:** 70.0",
            "**等級:** 1",
            "**評分:** 3.5",
            "**設施:**",
            "- 停車場: ✅",
            "- 親子友善: ❌"
        ]
        
        assert markdown_output == "\n".join(expected_lines)


class TestAccommodationDataValidation:
    """Test cases for accommodation data validation."""
    
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
    
    def test_validate_empty_dataframe(self):
        """Test validation of empty dataframe."""
        empty_df = gpd.GeoDataFrame()
        
        # Should not raise any exception
        self.service._validate_accommodation_data(empty_df)
    
    def test_validate_missing_required_columns(self):
        """Test validation fails when required columns are missing."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0]
            # Missing 'tier' column
        })
        
        with pytest.raises(ValueError, match="Missing required columns: \\['tier'\\]"):
            self.service._validate_accommodation_data(df)
    
    def test_validate_score_range_valid(self):
        """Test validation passes for valid score ranges."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],
            'score': [0.0, 100.0],
            'tier': [1, 2]
        })
        
        # Should not raise any exception
        self.service._validate_accommodation_data(df)
    
    def test_validate_score_range_invalid_low(self):
        """Test validation fails for scores below 0."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [-1.0],
            'tier': [1]
        })
        
        with pytest.raises(ValueError, match="score must be between 0-100, got -1.0"):
            self.service._validate_accommodation_data(df)
    
    def test_validate_score_range_invalid_high(self):
        """Test validation fails for scores above 100."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [101.0],
            'tier': [1]
        })
        
        with pytest.raises(ValueError, match="score must be between 0-100, got 101.0"):
            self.service._validate_accommodation_data(df)
    
    def test_validate_tier_range_valid(self):
        """Test validation passes for valid tier ranges."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A', 'Hotel B'],
            'score': [85.0, 90.0],
            'tier': [0, 3]
        })
        
        # Should not raise any exception
        self.service._validate_accommodation_data(df)
    
    def test_validate_tier_range_invalid_low(self):
        """Test validation fails for tiers below 0."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [-1]
        })
        
        with pytest.raises(ValueError, match="tier must be between 0-3, got -1"):
            self.service._validate_accommodation_data(df)
    
    def test_validate_tier_range_invalid_high(self):
        """Test validation fails for tiers above 3."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [4]
        })
        
        with pytest.raises(ValueError, match="tier must be between 0-3, got 4"):
            self.service._validate_accommodation_data(df)
    
    def test_validate_name_type_valid(self):
        """Test validation passes for valid name types."""
        df = gpd.GeoDataFrame({
            'name': ['Hotel A', None],
            'score': [85.0, 90.0],
            'tier': [1, 2]
        })
        
        # Should not raise any exception
        self.service._validate_accommodation_data(df)
    
    def test_validate_name_type_invalid(self):
        """Test validation fails for invalid name types."""
        df = gpd.GeoDataFrame({
            'name': [123],  # Invalid type
            'score': [85.0],
            'tier': [1]
        })
        
        with pytest.raises(TypeError, match="name must be str or None, got <class 'numpy.float64'>"):
            self.service._validate_accommodation_data(df)