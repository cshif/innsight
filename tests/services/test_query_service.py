"""Unit tests for QueryService."""

import pytest
from unittest.mock import patch

from src.innsight.services.query_service import QueryService
from src.innsight.exceptions import ParseError


class TestQueryService:
    """Test cases for QueryService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QueryService()

    def test_extract_search_term_with_location(self):
        """Test extracting search term when location is present."""
        with patch('src.innsight.services.query_service.parse_query') as mock_parse, \
             patch('src.innsight.services.query_service.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = 'Okinawa'
            
            result = self.service.extract_search_term("我想去沖繩的美ら海水族館")
            
            assert result == 'Okinawa'
            mock_parse.assert_called_once()
            mock_extract.assert_called_once()

    def test_extract_search_term_with_poi_only(self):
        """Test extracting search term when only POI is present."""
        with patch('src.innsight.services.query_service.parse_query') as mock_parse, \
             patch('src.innsight.services.query_service.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': 'aquarium'}
            mock_extract.return_value = ''
            
            result = self.service.extract_search_term("想去水族館")
            
            assert result == 'aquarium'

    def test_extract_search_term_no_location_no_poi(self):
        """Test that missing location and POI raises ParseError."""
        with patch('src.innsight.services.query_service.parse_query') as mock_parse, \
             patch('src.innsight.services.query_service.extract_location_from_query') as mock_extract:
            
            mock_parse.return_value = {'poi': ''}
            mock_extract.return_value = ''
            
            with pytest.raises(ParseError, match="無法判斷地名或主行程"):
                self.service.extract_search_term("想住兩天")