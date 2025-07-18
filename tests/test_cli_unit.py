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
    
