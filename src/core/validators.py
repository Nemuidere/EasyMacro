"""
Input validation utilities for EasyMacro.

Provides validation functions for data at boundaries.
"""

from typing import Any, List, Tuple
from pathlib import Path


def validate_not_empty(value: str, field_name: str) -> str:
    """Validate that a string is not empty.
    
    Args:
        value: String to validate.
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated string (stripped).
    
    Raises:
        ValueError: If value is empty or whitespace.
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    
    return value.strip()


def validate_path_exists(path: Path, field_name: str) -> Path:
    """Validate that a path exists.
    
    Args:
        path: Path to validate.
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated path.
    
    Raises:
        ValueError: If path does not exist.
    """
    if path is None:
        raise ValueError(f"{field_name} cannot be None")
    
    if not path.exists():
        raise ValueError(f"{field_name} does not exist: {path}")
    
    return path


def validate_positive_int(value: int, field_name: str) -> int:
    """Validate that an integer is positive.
    
    Args:
        value: Integer to validate.
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated integer.
    
    Raises:
        ValueError: If value is not positive.
    """
    if value <= 0:
        raise ValueError(f"{field_name} must be positive, got {value}")
    
    return value


def validate_in_range(value: float, min_val: float, max_val: float, field_name: str) -> float:
    """Validate that a value is within a range.
    
    Args:
        value: Value to validate.
        min_val: Minimum value (inclusive).
        max_val: Maximum value (inclusive).
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated value.
    
    Raises:
        ValueError: If value is out of range.
    """
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"{field_name} must be between {min_val} and {max_val}, got {value}"
        )
    
    return value


def validate_type(value: Any, expected_type: type, field_name: str) -> Any:
    """Validate that a value is of the expected type.
    
    Args:
        value: Value to validate.
        expected_type: Expected type.
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated value.
    
    Raises:
        TypeError: If value is not of expected type.
    """
    if not isinstance(value, expected_type):
        raise TypeError(
            f"{field_name} must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    
    return value
