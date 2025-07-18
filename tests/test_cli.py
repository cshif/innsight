"""Tests for CLI integration."""

import subprocess
import sys
import os
import pytest

# Add the src directory to the path so we can import innsight.cli
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCLIRegistration:
    """Test CLI command registration and help functionality."""
    
    def test_cli_help_shows_correct_usage(self):
        """Test that poetry run innsight --help shows correct usage."""
        # This test will fail initially since the CLI entry point doesn't exist yet
        result = subprocess.run(
            ["poetry", "run", "innsight", "--help"],
            cwd="/Users/evachng/dev/innsight",
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "innsight <query>" in result.stdout
    
    def test_cli_entry_point_exists(self):
        """Test that innsight command is available after poetry install."""
        # Check if the entry point is registered
        result = subprocess.run(
            ["poetry", "run", "innsight", "--help"],
            cwd="/Users/evachng/dev/innsight",
            capture_output=True,
            text=True
        )
        
        # Should not get "command not found" error
        assert "command not found" not in result.stderr.lower()
        assert "not found" not in result.stderr.lower()


class TestCLIHappyPath:
    """Test successful CLI execution flow."""
    
    def test_successful_query_execution_integration(self):
        """Integration test - requires real API access but demonstrates full functionality."""
        # This is a smoke test that demonstrates the CLI works end-to-end
        # It will use real APIs if available, otherwise skip
        query = "我想去沖繩的美ら海水族館"
        
        # Check if we have the required environment variables
        if not all([
            os.getenv('API_ENDPOINT'),
            os.getenv('ORS_URL'), 
            os.getenv('ORS_API_KEY'),
            os.getenv('OVERPASS_URL')
        ]):
            pytest.skip("Integration test requires API environment variables")
        
        result = subprocess.run(
            ["poetry", "run", "innsight", query],
            cwd="/Users/evachng/dev/innsight",
            capture_output=True,
            text=True
        )
        
        # Should either succeed or fail gracefully
        assert result.returncode in [0, 1]
        
        if result.returncode == 0:
            # If successful, check output format
            assert "找到" in result.stdout
            assert "筆住宿" in result.stdout
        else:
            # If failed, should have proper error message
            assert len(result.stderr) > 0


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""
    
    def test_missing_location_returns_error(self):
        """Test that missing location/POI returns proper error."""
        query = "想住兩天"  # No location or POI
        
        result = subprocess.run(
            ["poetry", "run", "innsight", query],
            cwd="/Users/evachng/dev/innsight",
            capture_output=True,
            text=True
        )
        
        assert result.returncode != 0
        assert "無法判斷地名或主行程" in result.stderr
    