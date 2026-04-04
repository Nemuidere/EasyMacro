"""
Randomization engine for EasyMacro.

Provides human-like randomization for macro actions using Gaussian distribution.
"""

from typing import Tuple
import numpy as np

from src.models.settings import RandomizationSettings


class RandomizationEngine:
    """
    Provides randomization for macro actions.
    
    Uses Gaussian (normal) distribution for natural-feeling variations
    in timing and position. This makes automation behavior more human-like
    and harder to detect.
    
    Usage:
        engine = RandomizationEngine(settings)
        jittered_pos = engine.apply_jitter(100, 100)
        randomized_delay = engine.randomize_delay(1000)
    """
    
    def __init__(self, settings: RandomizationSettings):
        """Initialize randomization engine.
        
        Args:
            settings: Randomization settings.
        
        Raises:
            ValueError: If settings is None.
        """
        if settings is None:
            raise ValueError("Settings cannot be None")
        
        self._settings = settings
        self._rng = np.random.default_rng()
    
    def apply_jitter(self, x: int, y: int) -> Tuple[int, int]:
        """Apply random jitter to a position.
        
        Uses Gaussian distribution centered on the original position
        with standard deviation equal to jitter_radius.
        
        Args:
            x: Original X coordinate.
            y: Original Y coordinate.
        
        Returns:
            Tuple of (jittered_x, jittered_y).
        
        Raises:
            ValueError: If coordinates are negative.
        """
        if x < 0:
            raise ValueError(f"X coordinate cannot be negative: {x}")
        if y < 0:
            raise ValueError(f"Y coordinate cannot be negative: {y}")
        
        if not self._settings.enabled:
            return (x, y)
        
        # Gaussian distribution centered on original position
        jitter_x = self._rng.normal(0, self._settings.jitter_radius)
        jitter_y = self._rng.normal(0, self._settings.jitter_radius)
        
        # Ensure we don't get negative coordinates
        new_x = max(0, int(x + jitter_x))
        new_y = max(0, int(y + jitter_y))
        
        return (new_x, new_y)
    
    def randomize_delay(self, base_ms: int) -> float:
        """Randomize a delay using Gaussian distribution.
        
        The variance is calculated as a percentage of the base delay.
        Result is guaranteed to be non-negative.
        
        Args:
            base_ms: Base delay in milliseconds.
        
        Returns:
            Randomized delay in milliseconds (non-negative).
        
        Raises:
            ValueError: If base_ms is negative.
        """
        if base_ms < 0:
            raise ValueError(f"Delay cannot be negative: {base_ms}")
        
        if not self._settings.enabled:
            return float(base_ms)
        
        # Calculate variance as percentage of base
        variance_ms = base_ms * (self._settings.timing_variance_percent / 100.0)
        
        # Gaussian distribution
        randomized = self._rng.normal(base_ms, variance_ms)
        
        # Ensure non-negative
        return max(0.0, randomized)
    
    def randomize_speed(self, base_speed: int) -> int:
        """Randomize movement speed.
        
        Args:
            base_speed: Base speed (1-10).
        
        Returns:
            Randomized speed (1-10).
        
        Raises:
            ValueError: If base_speed is out of range.
        """
        if not (1 <= base_speed <= 10):
            raise ValueError(f"Speed must be between 1 and 10: {base_speed}")
        
        if not self._settings.enabled:
            return base_speed
        
        # Apply variation
        variation = self._settings.mouse_speed_variation
        randomized = self._rng.normal(base_speed, variation / 5.0)
        
        # Clamp to valid range
        return max(1, min(10, int(randomized)))
    
    def update_settings(self, settings: RandomizationSettings) -> None:
        """Update randomization settings.
        
        Args:
            settings: New settings to apply.
        
        Raises:
            ValueError: If settings is None.
        """
        if settings is None:
            raise ValueError("Settings cannot be None")
        self._settings = settings
    
    def is_enabled(self) -> bool:
        """Check if randomization is enabled.
        
        Returns:
            True if enabled, False otherwise.
        """
        return self._settings.enabled
    
    def get_jitter_radius(self) -> int:
        """Get current jitter radius.
        
        Returns:
            Current jitter radius in pixels.
        """
        return self._settings.jitter_radius
    
    def get_timing_variance(self) -> int:
        """Get current timing variance percentage.
        
        Returns:
            Current timing variance percentage.
        """
        return self._settings.timing_variance_percent


# Global singleton instance
_randomization_engine: RandomizationEngine | None = None


def get_randomization_engine() -> RandomizationEngine:
    """Get the global randomization engine instance.
    
    Raises:
        RuntimeError: If engine not initialized.
    
    Returns:
        RandomizationEngine: The global engine instance.
    """
    if _randomization_engine is None:
        raise RuntimeError(
            "Randomization engine not initialized. "
            "Call init_randomization_engine() first."
        )
    return _randomization_engine


def init_randomization_engine(settings: RandomizationSettings) -> RandomizationEngine:
    """Initialize the global randomization engine.
    
    Args:
        settings: Randomization settings.
    
    Returns:
        RandomizationEngine: The newly created engine instance.
    
    Raises:
        RuntimeError: If engine already initialized.
        ValueError: If settings is None.
    """
    global _randomization_engine
    if _randomization_engine is not None:
        raise RuntimeError("Randomization engine already initialized.")
    _randomization_engine = RandomizationEngine(settings)
    return _randomization_engine
