"""
Tests for the RandomizationEngine.

Tests Gaussian distribution randomization for human-like behavior.
"""

import pytest
import numpy as np

from src.core.randomization import RandomizationEngine, init_randomization_engine, get_randomization_engine
from src.models.settings import RandomizationSettings


class TestRandomizationEngine:
    """Tests for RandomizationEngine class."""
    
    def test_init_with_valid_settings(self):
        """Test initialization with valid settings."""
        settings = RandomizationSettings()
        engine = RandomizationEngine(settings)
        
        assert engine.is_enabled() is True
        assert engine.get_jitter_radius() == 5
        assert engine.get_timing_variance() == 20
    
    def test_init_with_none_settings_raises_error(self):
        """Test initialization with None settings raises ValueError."""
        with pytest.raises(ValueError, match="Settings cannot be None"):
            RandomizationEngine(None)
    
    def test_apply_jitter_returns_tuple(self, randomization_settings):
        """Test that apply_jitter returns a tuple."""
        engine = RandomizationEngine(randomization_settings)
        result = engine.apply_jitter(100, 200)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
    
    def test_apply_jitter_never_negative(self, randomization_settings):
        """Test that jitter never produces negative coordinates."""
        engine = RandomizationEngine(randomization_settings)
        
        # Test many times to catch edge cases
        for _ in range(100):
            x, y = engine.apply_jitter(0, 0)
            assert x >= 0
            assert y >= 0
    
    def test_apply_jitter_with_disabled_randomization(self):
        """Test that disabled randomization returns original coordinates."""
        settings = RandomizationSettings(enabled=False)
        engine = RandomizationEngine(settings)
        
        x, y = engine.apply_jitter(100, 200)
        
        assert x == 100
        assert y == 200
    
    def test_apply_jitter_negative_coordinates_raises_error(self, randomization_settings):
        """Test that negative coordinates raise ValueError."""
        engine = RandomizationEngine(randomization_settings)
        
        with pytest.raises(ValueError, match="X coordinate cannot be negative"):
            engine.apply_jitter(-1, 100)
        
        with pytest.raises(ValueError, match="Y coordinate cannot be negative"):
            engine.apply_jitter(100, -1)
    
    def test_randomize_delay_returns_float(self, randomization_settings):
        """Test that randomize_delay returns a float."""
        engine = RandomizationEngine(randomization_settings)
        result = engine.randomize_delay(1000)
        
        assert isinstance(result, float)
    
    def test_randomize_delay_never_negative(self, randomization_settings):
        """Test that randomized delay is never negative."""
        engine = RandomizationEngine(randomization_settings)
        
        for _ in range(100):
            delay = engine.randomize_delay(100)
            assert delay >= 0
    
    def test_randomize_delay_with_disabled_randomization(self):
        """Test that disabled randomization returns original delay."""
        settings = RandomizationSettings(enabled=False)
        engine = RandomizationEngine(settings)
        
        delay = engine.randomize_delay(1000)
        
        assert delay == 1000.0
    
    def test_randomize_delay_negative_raises_error(self, randomization_settings):
        """Test that negative delay raises ValueError."""
        engine = RandomizationEngine(randomization_settings)
        
        with pytest.raises(ValueError, match="Delay cannot be negative"):
            engine.randomize_delay(-1)
    
    def test_randomize_speed_in_range(self, randomization_settings):
        """Test that randomized speed is always in valid range."""
        engine = RandomizationEngine(randomization_settings)
        
        for _ in range(100):
            speed = engine.randomize_speed(5)
            assert 1 <= speed <= 10
    
    def test_randomize_speed_out_of_range_raises_error(self, randomization_settings):
        """Test that out of range speed raises ValueError."""
        engine = RandomizationEngine(randomization_settings)
        
        with pytest.raises(ValueError, match="Speed must be between 1 and 10"):
            engine.randomize_speed(0)
        
        with pytest.raises(ValueError, match="Speed must be between 1 and 10"):
            engine.randomize_speed(11)
    
    def test_randomize_speed_with_disabled_randomization(self):
        """Test that disabled randomization returns original speed."""
        settings = RandomizationSettings(enabled=False)
        engine = RandomizationEngine(settings)
        
        speed = engine.randomize_speed(5)
        
        assert speed == 5
    
    def test_update_settings(self, randomization_settings):
        """Test updating settings."""
        engine = RandomizationEngine(randomization_settings)
        
        new_settings = RandomizationSettings(enabled=False, jitter_radius=10)
        engine.update_settings(new_settings)
        
        assert engine.is_enabled() is False
        assert engine.get_jitter_radius() == 10
    
    def test_update_settings_with_none_raises_error(self, randomization_settings):
        """Test that updating with None raises ValueError."""
        engine = RandomizationEngine(randomization_settings)
        
        with pytest.raises(ValueError, match="Settings cannot be None"):
            engine.update_settings(None)


class TestRandomizationEngineSingleton:
    """Tests for singleton functions."""
    
    def test_init_randomization_engine(self, randomization_settings):
        """Test initializing the singleton."""
        # Reset singleton
        import src.core.randomization as rand_module
        rand_module._randomization_engine = None
        
        engine = init_randomization_engine(randomization_settings)
        
        assert engine is not None
        assert isinstance(engine, RandomizationEngine)
        
        # Cleanup
        rand_module._randomization_engine = None
    
    def test_init_twice_raises_error(self, randomization_settings):
        """Test that initializing twice raises RuntimeError."""
        # Reset singleton
        import src.core.randomization as rand_module
        rand_module._randomization_engine = None
        
        init_randomization_engine(randomization_settings)
        
        with pytest.raises(RuntimeError, match="already initialized"):
            init_randomization_engine(randomization_settings)
        
        # Cleanup
        rand_module._randomization_engine = None
    
    def test_get_without_init_raises_error(self):
        """Test that getting without init raises RuntimeError."""
        # Reset singleton
        import src.core.randomization as rand_module
        rand_module._randomization_engine = None
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_randomization_engine()
