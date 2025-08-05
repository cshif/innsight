"""Tests for utility functions."""

import pytest
from src.innsight.utils import combine_tokens


class TestCombineTokens:
    """Test suite for combine_tokens function."""
    
    def test_combine_tokens_normal_case(self):
        """Test combining normal string tokens."""
        tokens = ["hello", "world", "test"]
        result = combine_tokens(tokens)
        assert result == "helloworldtest"
    
    def test_combine_tokens_with_none_values(self):
        """Test combining tokens with None values."""
        tokens = ["hello", None, "world", None, "test"]
        result = combine_tokens(tokens)
        assert result == "helloworldtest"
    
    def test_combine_tokens_empty_list(self):
        """Test combining empty token list."""
        tokens = []
        result = combine_tokens(tokens)
        assert result == ""
    
    def test_combine_tokens_all_none(self):
        """Test combining tokens that are all None."""
        tokens = [None, None, None]
        result = combine_tokens(tokens)
        assert result == ""
    
    def test_combine_tokens_mixed_types(self):
        """Test combining tokens with mixed types."""
        tokens = ["hello", 123, "world", 45.6]
        result = combine_tokens(tokens)
        assert result == "hello123world45.6"
    
    def test_combine_tokens_with_invalid_tokens_type_error(self):
        """Test combining tokens that cause TypeError in str() conversion."""
        # Create a mock object that raises TypeError when str() is called
        class BadToken:
            def __str__(self):
                raise TypeError("Cannot convert to string")
        
        tokens = ["hello", BadToken(), "world"]
        result = combine_tokens(tokens)
        assert result == ""  # Should return empty string due to exception
    
    def test_combine_tokens_with_invalid_tokens_attribute_error(self):
        """Test combining tokens that cause AttributeError."""
        # Create a mock object that raises AttributeError when accessed
        class BadToken:
            def __str__(self):
                raise AttributeError("Missing attribute")
        
        tokens = ["hello", BadToken(), "world"]
        result = combine_tokens(tokens)
        assert result == ""  # Should return empty string due to exception
    
    def test_combine_tokens_non_iterable_input(self):
        """Test with non-iterable input to trigger exception handling."""
        # This should trigger the TypeError/AttributeError exception handling
        # when trying to iterate over non-iterable
        result = combine_tokens(None)
        assert result == ""
    
    def test_combine_tokens_string_tokens(self):
        """Test with string tokens including empty strings."""
        tokens = ["hello", "", "world", ""]
        result = combine_tokens(tokens)
        assert result == "helloworld"