"""
Tests for input validators.

Tests validation functions at boundaries.
"""

import pytest
from pathlib import Path

from src.core.validators import (
    validate_not_empty,
    validate_path_exists,
    validate_positive_int,
    validate_in_range,
    validate_type,
)


class TestValidateNotEmpty:
    """Tests for validate_not_empty function."""
    
    def test_valid_string(self):
        """Test validation with valid string."""
        result = validate_not_empty("  test  ", "field")
        
        assert result == "test"
    
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="field cannot be empty"):
            validate_not_empty("", "field")
    
    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="field cannot be empty"):
            validate_not_empty("   ", "field")
    
    def test_none_raises_error(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="field cannot be empty"):
            validate_not_empty(None, "field")


class TestValidatePathExists:
    """Tests for validate_path_exists function."""
    
    def test_existing_path(self, temp_dir):
        """Test validation with existing path."""
        result = validate_path_exists(temp_dir, "path")
        
        assert result == temp_dir
    
    def test_nonexistent_path_raises_error(self, temp_dir):
        """Test that nonexistent path raises ValueError."""
        nonexistent = temp_dir / "nonexistent"
        
        with pytest.raises(ValueError, match="path does not exist"):
            validate_path_exists(nonexistent, "path")
    
    def test_none_raises_error(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="path cannot be None"):
            validate_path_exists(None, "path")


class TestValidatePositiveInt:
    """Tests for validate_positive_int function."""
    
    def test_positive_value(self):
        """Test validation with positive value."""
        result = validate_positive_int(10, "value")
        
        assert result == 10
    
    def test_zero_raises_error(self):
        """Test that zero raises ValueError."""
        with pytest.raises(ValueError, match="value must be positive"):
            validate_positive_int(0, "value")
    
    def test_negative_raises_error(self):
        """Test that negative value raises ValueError."""
        with pytest.raises(ValueError, match="value must be positive"):
            validate_positive_int(-1, "value")


class TestValidateInRange:
    """Tests for validate_in_range function."""
    
    def test_value_in_range(self):
        """Test validation with value in range."""
        result = validate_in_range(5, 0, 10, "value")
        
        assert result == 5
    
    def test_value_at_min(self):
        """Test validation with value at minimum."""
        result = validate_in_range(0, 0, 10, "value")
        
        assert result == 0
    
    def test_value_at_max(self):
        """Test validation with value at maximum."""
        result = validate_in_range(10, 0, 10, "value")
        
        assert result == 10
    
    def test_value_below_range_raises_error(self):
        """Test that value below range raises ValueError."""
        with pytest.raises(ValueError, match="value must be between"):
            validate_in_range(-1, 0, 10, "value")
    
    def test_value_above_range_raises_error(self):
        """Test that value above range raises ValueError."""
        with pytest.raises(ValueError, match="value must be between"):
            validate_in_range(11, 0, 10, "value")
    
    def test_invalid_range_raises_error(self):
        """Test that invalid range raises ValueError."""
        with pytest.raises(ValueError, match="min_value .* cannot be greater than max_value"):
            validate_in_range(5, 10, 0, "value")


class TestValidateType:
    """Tests for validate_type function."""
    
    def test_correct_type(self):
        """Test validation with correct type."""
        result = validate_type("test", str, "value")
        
        assert result == "test"
    
    def test_incorrect_type_raises_error(self):
        """Test that incorrect type raises TypeError."""
        with pytest.raises(TypeError, match="value must be str"):
            validate_type(123, str, "value")
    
    def test_with_custom_class(self):
        """Test validation with custom class."""
        class CustomClass:
            pass
        
        instance = CustomClass()
        result = validate_type(instance, CustomClass, "value")
        
        assert result is instance
