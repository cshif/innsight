"""Unit tests for AccommodationService."""

import pandas as pd
from unittest.mock import patch

from src.innsight.services.accommodation_service import AccommodationService


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
        with patch('src.innsight.services.accommodation_service.fetch_overpass') as mock_fetch:
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