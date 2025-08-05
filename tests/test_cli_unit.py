"""Unit tests for CLI main function."""

import sys
import os
from unittest.mock import patch
from io import StringIO

# Add the src directory to the path so we can import innsight.cli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from innsight.cli import main


class TestCLIMainFunction:
    """Test CLI main function directly."""
    
    def test_help_option_returns_zero(self):
        """Test that --help option returns 0."""
        with patch('sys.stdout', new_callable=StringIO):
            result = main(['--help'])
            assert result == 0
    
    def test_missing_query_returns_error(self):
        """Test that missing query returns non-zero."""
        with patch('sys.stderr', new_callable=StringIO):
            result = main([])
            assert result != 0
    
    def test_environment_variable_missing_returns_error(self):
        """Test that missing environment variables return proper error."""
        query = "我想去沖繩的美ら海水族館"
        
        # Test without API_ENDPOINT
        with patch.dict(os.environ, {}, clear=True), \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            
            result = main([query])
            error_output = mock_stderr.getvalue()
            
            assert result != 0
            assert "API_ENDPOINT" in error_output
    
    def test_missing_location_returns_error(self):
        """Test that missing location/POI returns proper error."""
        query = "想住兩天"  # No location or POI
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = main([query])
            error_output = mock_stderr.getvalue()
            
            assert result != 0
            assert "無法判斷地名或主行程" in error_output
    
    def test_markdown_output_flag(self):
        """Test that --markdown flag produces markdown output."""
        query = "我想去東京住一天"
        
        with patch('innsight.cli._create_recommender') as mock_create_recommender, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Setup mocks
            mock_recommender = mock_create_recommender.return_value
            mock_search_service = mock_recommender.search_service
            
            # Mock search results with some sample data
            import geopandas as gpd
            mock_gdf = gpd.GeoDataFrame({
                'name': ['東京酒店'],
                'tier': [2],
                'score': [85.0],
                'rating': [4.2],
                'tags': [{'parking': 'yes', 'wheelchair': 'no'}]
            })
            mock_recommender.recommend.return_value = mock_gdf
            mock_search_service.format_accommodations_as_markdown.return_value = "# 住宿推薦結果\n\n## 1. 東京酒店"
            
            result = main([query, '--markdown'])
            
            assert result == 0
            output = mock_stdout.getvalue()
            assert "# 住宿推薦結果" in output
            assert "## 1. 東京酒店" in output
            mock_recommender.recommend.assert_called_once_with(query)
            mock_search_service.format_accommodations_as_markdown.assert_called_once()
    
    def test_report_generation_flag(self):
        """Test that --report flag generates markdown report file."""
        query = "我想去美ら海水族館住一天"
        
        with patch('innsight.cli._create_recommender') as mock_create_recommender, \
             patch('innsight.cli.generate_markdown_report') as mock_generate_report, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Setup mocks
            mock_recommender = mock_create_recommender.return_value
            
            # Mock search results
            import geopandas as gpd
            mock_gdf = gpd.GeoDataFrame({
                'name': ['沖繩海洋酒店'],
                'tier': [3],
                'score': [95.0],
                'rating': [4.8],
                'tags': [{'parking': 'yes', 'wheelchair': 'yes'}]
            })
            mock_recommender.recommend.return_value = mock_gdf
            
            # Mock report generation
            mock_generate_report.return_value = "report/20250729_1548_abc123.md"
            
            result = main([query, '--report'])
            
            assert result == 0
            
            # Should call report generation with correct parameters
            mock_generate_report.assert_called_once()
            call_args = mock_generate_report.call_args
            
            # Verify query_dict contains main_poi
            query_dict = call_args[0][0]
            assert 'main_poi' in query_dict
            
            # Verify DataFrame is passed
            passed_df = call_args[0][1]
            assert len(passed_df) == 1
            assert passed_df.iloc[0]['name'] == '沖繩海洋酒店'
            
            # Should output report file path
            output = mock_stdout.getvalue()
            assert "報告已生成：report/20250729_1548_abc123.md" in output
    
    def test_report_with_poi_extraction(self):
        """Test that --report flag correctly extracts POI from query."""
        query = "我想去美ら海水族館住兩天要停車場"
        
        with patch('innsight.cli._create_recommender') as mock_create_recommender, \
             patch('innsight.cli.parse_query') as mock_parse_query, \
             patch('innsight.cli.generate_markdown_report') as mock_generate_report, \
             patch('sys.stdout', new_callable=StringIO):
            
            # Setup mocks
            mock_recommender = mock_create_recommender.return_value
            
            # Mock parser to return POI
            mock_parse_query.return_value = {
                'poi': '美ら海水族館',
                'days': '2',
                'filters': ['parking']
            }
            
            # Mock search results
            import geopandas as gpd
            mock_gdf = gpd.GeoDataFrame({
                'name': ['沖繩酒店'],
                'tier': [2],
                'score': [85.0],
                'rating': [4.0],
                'tags': [{'parking': 'yes'}]
            })
            mock_recommender.recommend.return_value = mock_gdf
            
            mock_generate_report.return_value = "report/test.md"
            
            result = main([query, '--report'])
            
            assert result == 0
            
            # Should call parse_query with the original query
            mock_parse_query.assert_called_once_with(query)
            
            # Should call generate_markdown_report with correct query_dict
            mock_generate_report.assert_called_once()
            call_args = mock_generate_report.call_args
            query_dict = call_args[0][0]
            
            # Should have extracted POI correctly
            assert query_dict['main_poi'] == '美ら海水族館'
    
    def test_report_and_markdown_combination(self):
        """Test that both --report and --markdown flags work together."""
        query = "我想去東京住一天"
        
        with patch('innsight.cli._create_recommender') as mock_create_recommender, \
             patch('innsight.cli.generate_markdown_report') as mock_generate_report, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Setup mocks
            mock_recommender = mock_create_recommender.return_value
            mock_search_service = mock_recommender.search_service
            
            # Mock search results
            import geopandas as gpd
            mock_gdf = gpd.GeoDataFrame({
                'name': ['東京酒店'],
                'tier': [2],
                'score': [85.0],
                'rating': [4.2],
                'tags': [{'parking': 'yes', 'wheelchair': 'no'}]
            })
            mock_recommender.recommend.return_value = mock_gdf
            mock_search_service.format_accommodations_as_markdown.return_value = "# 住宿推薦結果\n\n## 1. 東京酒店"
            
            # Mock report generation
            mock_generate_report.return_value = "report/20250729_1548_abc123.md"
            
            result = main([query, '--report', '--markdown'])
            
            assert result == 0
            
            # Should call both report generation AND terminal output
            mock_generate_report.assert_called_once()
            mock_search_service.format_accommodations_as_markdown.assert_called_once()
            
            # Should output both report path and markdown content
            output = mock_stdout.getvalue()
            assert "報告已生成：report/20250729_1548_abc123.md" in output
            assert "# 住宿推薦結果" in output
            assert "## 1. 東京酒店" in output
    
    def test_no_flags_shows_only_top_10_results(self):
        """Test that default output (no flags) shows only top 10 results."""
        query = "我想去東京住一天"
        
        with patch('innsight.cli._create_recommender') as mock_create_recommender, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Setup mocks
            mock_recommender = mock_create_recommender.return_value
            
            # Mock 15 search results to test the top 10 limit
            import geopandas as gpd
            hotels_data = {
                'name': [f'Hotel {i+1}' for i in range(15)],
                'tier': [1, 2, 3] * 5,  # Mix of tiers
                'score': [90-i*2 for i in range(15)]  # Descending scores
            }
            mock_gdf = gpd.GeoDataFrame(hotels_data)
            mock_recommender.recommend.return_value = mock_gdf
            
            result = main([query])  # No flags
            
            assert result == 0
            
            output = mock_stdout.getvalue()
            
            # Should show total count
            assert "找到 15 筆住宿" in output
            
            # Should show only first 10 hotels
            for i in range(10):
                assert f"name: Hotel {i+1}" in output
            
            # Should NOT show hotels 11-15
            for i in range(10, 15):
                assert f"name: Hotel {i+1}" not in output
    
