"""
Utility functions for EasyMacro.

Common helper functions used across the application.
"""

from pathlib import Path
from typing import TypeVar, Callable
from functools import wraps
import time

T = TypeVar('T')


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure.
    
    Returns:
        The path (for chaining).
    
    Raises:
        ValueError: If path is None.
    """
    if path is None:
        raise ValueError("Path cannot be None")
    
    path.mkdir(parents=True, exist_ok=True)
    return path


def debounce(delay_ms: int) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to debounce a function.
    
    Prevents rapid successive calls by waiting for a delay after the last call.
    
    Args:
        delay_ms: Delay in milliseconds.
    
    Returns:
        Decorated function.
    
    Raises:
        ValueError: If delay_ms is negative.
    
    Example:
        @debounce(100)
        def on_text_changed(text: str):
            # Only called 100ms after last change
            print(text)
    """
    if delay_ms < 0:
        raise ValueError("Delay cannot be negative")
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        last_call: float = 0.0
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            nonlocal last_call
            current_time = time.time() * 1000
            
            if current_time - last_call >= delay_ms:
                last_call = current_time
                return func(*args, **kwargs)
            
            return None  # type: ignore
        
        return wrapper
    
    return decorator


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a value between min and max.
    
    Args:
        value: Value to clamp.
        min_value: Minimum value.
        max_value: Maximum value.
    
    Returns:
        Clamped value.
    
    Raises:
        ValueError: If min_value > max_value.
    
    Example:
        clamp(150, 0, 100)  # Returns 100
    """
    if min_value > max_value:
        raise ValueError(f"min_value ({min_value}) cannot be greater than max_value ({max_value})")
    
    return max(min_value, min(value, max_value))
