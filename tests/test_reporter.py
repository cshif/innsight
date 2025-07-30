"""Tests for reporter module - Markdown report generation functionality."""

import os
import shutil
from unittest.mock import patch, MagicMock
import geopandas as gpd

from src.innsight.reporter import generate_markdown_report


class TestMarkdownReportGeneration:
    """Test cases for markdown report generation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clean up any existing test reports
        if os.path.exists('report'):
            shutil.rmtree('report')
    
    def teardown_method(self):
        """Clean up after tests."""
        # Clean up test reports
        if os.path.exists('report'):
            shutil.rmtree('report')
    
    def test_generate_markdown_report_creates_file(self):
        """正確產生檔案 - Given query_dict and Top 5 DataFrame, When call generate_markdown_report, Then return file path and file exists in report/ directory."""
        query_dict = {"main_poi": "美ら海水族館"}
        
        top_df = gpd.GeoDataFrame({
            'name': ['Resort A', 'Hotel B', 'Inn C', 'Lodge D', 'Villa E'],
            'score': [93.2, 87.5, 82.1, 78.9, 75.3],
            'tier': [3, 2, 2, 1, 1],
            'rating': [4.8, 4.2, 4.0, 3.8, 3.5],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'},
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ]
        })
        
        # This should fail initially as the function doesn't exist yet
        file_path = generate_markdown_report(query_dict, top_df)
        
        # Verify file path is returned
        assert isinstance(file_path, str)
        assert file_path.endswith('.md')
        
        # Verify file exists in report/ directory
        assert os.path.exists(file_path)
        assert file_path.startswith('report/')
        
        # Verify it's actually a file
        assert os.path.isfile(file_path)
    
    def test_filename_format_with_timestamp_and_hash(self):
        """檔名與路徑規則 - Given local time 2025-07-23 13:45:00, When generate report, Then filename prefix is 20250723_1345_ plus 6-char hash."""
        query_dict = {"main_poi": "美ら海水族館"} 
        top_df = gpd.GeoDataFrame({
            'name': ['Resort A'],
            'score': [93.2],
            'tier': [3],
            'rating': [4.8],
            'tags': [{'parking': 'yes', 'wheelchair': 'yes'}]
        })
        
        # Mock datetime to specific time
        with patch('src.innsight.reporter.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20250723_1345"
            mock_now.isoformat.return_value = "2025-07-23T13:45:00.000000"
            mock_datetime.now.return_value = mock_now
            
            file_path = generate_markdown_report(query_dict, top_df)
            
            filename = os.path.basename(file_path)
            
            # Should start with timestamp
            assert filename.startswith("20250723_1345_")
            
            # Should end with .md
            assert filename.endswith(".md")
            
            # Should have 6-char hash between timestamp and extension
            parts = filename.replace('.md', '').split('_')
            assert len(parts) == 3  # date, time, hash
            hash_part = parts[2]
            assert len(hash_part) == 6
            
            # Verify file exists
            assert os.path.exists(file_path)
    
    def test_report_content_structure_complete(self):
        """內容結構完整 - Given report file, Then must contain required sections and format."""
        query_dict = {"main_poi": "美ら海水族館"}
        top_df = gpd.GeoDataFrame({
            'name': ['Resort A', 'Hotel B', 'Inn C', 'Lodge D', 'Villa E'],
            'score': [93.2, 87.5, 82.1, 78.9, 75.3],
            'tier': [3, 2, 2, 1, 1],
            'rating': [4.8, 4.2, 4.0, 3.8, 3.5],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'},
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ]
        })
        
        file_path = generate_markdown_report(query_dict, top_df)
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Must contain main title with POI name
        assert "# 美ら海水族館 周邊住宿建議" in content
        
        # Must contain region distribution section
        assert "## 區域分佈" in content
        assert "| Tier | 數量 |" in content
        assert "| Tier 3 |" in content
        assert "| Tier 2 |" in content  
        assert "| Tier 1 |" in content
        
        # Must contain Top 10 section
        assert "## 推薦 Top 10" in content
        
        # Must contain table headers
        assert "| 分數 | 名稱 | Tier | Rating | 停車 | 無障礙 |" in content
        
    def test_data_accuracy_in_report(self):
        """資料正確 - Given Top 5 DataFrame first row with score=93.2, name='Resort A', Then report table shows 93.2 and Resort A correctly."""
        query_dict = {"main_poi": "美ら海水族館"}
        top_df = gpd.GeoDataFrame({
            'name': ['Resort A', 'Hotel B'],
            'score': [93.2, 87.5],
            'tier': [3, 2],
            'rating': [4.8, 4.2],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ]
        })
        
        file_path = generate_markdown_report(query_dict, top_df)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # First row should show correct data
        assert "| 93.2 | Resort A | 3 | 4.8 | ✅ | ✅ |" in content
        assert "| 87.5 | Hotel B | 2 | 4.2 | ❌ | ❌ |" in content
    
    def test_multiple_poi_coexistence(self):
        """多景點可共存 - Given consecutive calls for two different POIs, Then filenames are different and content shows respective POI."""
        top_df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [2],
            'rating': [4.0],
            'tags': [{'parking': 'yes', 'wheelchair': 'no'}]
        })
        
        # First POI
        query_dict1 = {"main_poi": "美ら海水族館"}
        file_path1 = generate_markdown_report(query_dict1, top_df)
        
        # Second POI (different)
        query_dict2 = {"main_poi": "首里城"}
        file_path2 = generate_markdown_report(query_dict2, top_df)
        
        # Filenames should be different
        assert file_path1 != file_path2
        
        # Both files should exist
        assert os.path.exists(file_path1)
        assert os.path.exists(file_path2)
        
        # Read both files and check content
        with open(file_path1, 'r', encoding='utf-8') as f:
            content1 = f.read()
        with open(file_path2, 'r', encoding='utf-8') as f:
            content2 = f.read()
        
        # Each file should have its respective POI in title
        assert "# 美ら海水族館 周邊住宿建議" in content1
        assert "# 首里城 周邊住宿建議" in content2
        
        # Content should be different
        assert content1 != content2
    
    def test_auto_create_report_directory(self):
        """不存在資料夾時自動建立 - Given manually deleted report/ directory, When call generate_markdown_report, Then automatically rebuild directory and output report."""
        # Ensure report directory doesn't exist
        if os.path.exists('report'):
            shutil.rmtree('report')
        
        assert not os.path.exists('report')
        
        query_dict = {"main_poi": "美ら海水族館"}
        top_df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0], 
            'tier': [2],
            'rating': [4.0],
            'tags': [{'parking': 'yes', 'wheelchair': 'no'}]
        })
        
        # Should not raise exception and should create directory
        file_path = generate_markdown_report(query_dict, top_df)
        
        # Directory should now exist
        assert os.path.exists('report')
        assert os.path.isdir('report')
        
        # File should exist in the directory
        assert os.path.exists(file_path)
        assert file_path.startswith('report/')


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clean up any existing test reports
        if os.path.exists('report'):
            shutil.rmtree('report')
    
    def teardown_method(self):
        """Clean up after tests."""
        # Clean up test reports
        if os.path.exists('report'):
            shutil.rmtree('report')
    
    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        query_dict = {"main_poi": "測試景點"}
        empty_df = gpd.GeoDataFrame()
        
        file_path = generate_markdown_report(query_dict, empty_df)
        
        assert os.path.exists(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should still have basic structure
        assert "# 測試景點 周邊住宿建議" in content
        assert "## 區域分佈" in content
        assert "## 推薦 Top 10" in content
        
    def test_missing_main_poi(self):
        """Test with missing main_poi in query_dict."""
        query_dict = {}  # No main_poi
        top_df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            'score': [85.0],
            'tier': [2],
            'rating': [4.0],
            'tags': [{'parking': 'yes'}]
        })
        
        file_path = generate_markdown_report(query_dict, top_df)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should use default value
        assert "# 未知景點 周邊住宿建議" in content
    
    def test_missing_columns_in_dataframe(self):
        """Test with DataFrame missing some expected columns."""
        query_dict = {"main_poi": "測試景點"}
        minimal_df = gpd.GeoDataFrame({
            'name': ['Hotel A'],
            # Missing score, tier, rating, tags
        })
        
        file_path = generate_markdown_report(query_dict, minimal_df)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should handle missing data gracefully
        assert "# 測試景點 周邊住宿建議" in content
        assert "Hotel A" in content