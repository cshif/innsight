"""Unit tests for TierService."""

import pandas as pd
import geopandas as gpd
from unittest.mock import patch

from src.innsight.services.tier_service import TierService


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
        
        with patch('src.innsight.services.tier_service.assign_tier') as mock_assign:
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