"""
Tests for action models.

Tests Pydantic validation for action types.
"""

import pytest

from src.models.action import (
    ActionType,
    ClickAction,
    DelayAction,
    KeyPressAction,
    MouseMoveAction,
    parse_action,
)


class TestClickAction:
    """Tests for ClickAction model."""
    
    def test_create_click_action(self):
        """Test creating a click action."""
        action = ClickAction(x=100, y=200)
        
        assert action.x == 100
        assert action.y == 200
        assert action.button == "left"
        assert action.jitter_radius == 2
        assert action.action_type == ActionType.CLICK
    
    def test_create_click_action_with_custom_button(self):
        """Test creating a click action with custom button."""
        action = ClickAction(x=100, y=200, button="right")
        
        assert action.button == "right"
    
    def test_create_click_action_with_invalid_button_raises_error(self):
        """Test that invalid button raises ValueError."""
        with pytest.raises(ValueError, match="Button must be one of"):
            ClickAction(x=100, y=200, button="invalid")
    
    def test_create_click_action_with_negative_coordinates_raises_error(self):
        """Test that negative coordinates raise ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=-1, y=200)

        with pytest.raises(ValueError):
            ClickAction(x=100, y=-1)

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = ClickAction(x=100, y=200)

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5

    def test_delay_after_can_be_set(self):
        """Test that inline post-action delay can be configured."""
        action = ClickAction(x=100, y=200, delay_after_ms=250, delay_after_variance_percent=20)

        assert action.delay_after_ms == 250
        assert action.delay_after_variance_percent == 20

    def test_delay_after_negative_raises_error(self):
        """Test that a negative inline delay raises ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=100, y=200, delay_after_ms=-1)

    def test_delay_after_variance_out_of_range_raises_error(self):
        """Test that an out-of-range inline delay variance raises ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=100, y=200, delay_after_variance_percent=101)


class TestDelayAction:
    """Tests for DelayAction model."""
    
    def test_create_delay_action(self):
        """Test creating a delay action."""
        action = DelayAction(duration_ms=1000)
        
        assert action.duration_ms == 1000
        assert action.variance_percent == 5
        assert action.action_type == ActionType.DELAY
    
    def test_create_delay_action_with_custom_variance(self):
        """Test creating a delay action with custom variance."""
        action = DelayAction(duration_ms=1000, variance_percent=50)
        
        assert action.variance_percent == 50
    
    def test_create_delay_action_with_negative_duration_raises_error(self):
        """Test that negative duration raises ValueError."""
        with pytest.raises(ValueError):
            DelayAction(duration_ms=-1)
    
    def test_create_delay_action_with_invalid_variance_raises_error(self):
        """Test that invalid variance raises ValueError."""
        with pytest.raises(ValueError):
            DelayAction(duration_ms=1000, variance_percent=101)


class TestKeyPressAction:
    """Tests for KeyPressAction model."""
    
    def test_create_key_press_action(self):
        """Test creating a key press action."""
        action = KeyPressAction(key="a")
        
        assert action.key == "a"
        assert action.modifiers == []
        assert action.action_type == ActionType.KEY_PRESS
    
    def test_create_key_press_action_with_modifiers(self):
        """Test creating a key press action with modifiers."""
        action = KeyPressAction(key="a", modifiers=["ctrl", "shift"])
        
        assert action.modifiers == ["ctrl", "shift"]
    
    def test_create_key_press_action_with_invalid_modifier_raises_error(self):
        """Test that invalid modifier raises ValueError."""
        with pytest.raises(ValueError, match="Modifier must be one of"):
            KeyPressAction(key="a", modifiers=["invalid"])
    
    def test_create_key_press_action_with_empty_key_raises_error(self):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError):
            KeyPressAction(key="")

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = KeyPressAction(key="a")

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5


class TestMouseMoveAction:
    """Tests for MouseMoveAction model."""
    
    def test_create_mouse_move_action(self):
        """Test creating a mouse move action."""
        action = MouseMoveAction(x=100, y=200)
        
        assert action.x == 100
        assert action.y == 200
        assert action.smooth is True
        assert action.speed == 5
        assert action.action_type == ActionType.MOUSE_MOVE
    
    def test_create_mouse_move_action_with_custom_speed(self):
        """Test creating a mouse move action with custom speed."""
        action = MouseMoveAction(x=100, y=200, speed=10)
        
        assert action.speed == 10
    
    def test_create_mouse_move_action_with_invalid_speed_raises_error(self):
        """Test that invalid speed raises ValueError."""
        with pytest.raises(ValueError):
            MouseMoveAction(x=100, y=200, speed=0)

        with pytest.raises(ValueError):
            MouseMoveAction(x=100, y=200, speed=11)

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = MouseMoveAction(x=100, y=200)

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5


class TestParseAction:
    """Tests for parse_action function."""
    
    def test_parse_click_action(self):
        """Test parsing a click action."""
        data = {"action_type": "click", "x": 100, "y": 200}
        
        action = parse_action(data)
        
        assert isinstance(action, ClickAction)
        assert action.x == 100
        assert action.y == 200
    
    def test_parse_delay_action(self):
        """Test parsing a delay action."""
        data = {"action_type": "delay", "duration_ms": 1000}
        
        action = parse_action(data)
        
        assert isinstance(action, DelayAction)
        assert action.duration_ms == 1000
    
    def test_parse_key_press_action(self):
        """Test parsing a key press action."""
        data = {"action_type": "key_press", "key": "a"}
        
        action = parse_action(data)
        
        assert isinstance(action, KeyPressAction)
        assert action.key == "a"
    
    def test_parse_mouse_move_action(self):
        """Test parsing a mouse move action."""
        data = {"action_type": "mouse_move", "x": 100, "y": 200}
        
        action = parse_action(data)
        
        assert isinstance(action, MouseMoveAction)
        assert action.x == 100
    
    def test_parse_action_without_type_raises_error(self):
        """Test that parsing without action_type raises ValueError."""
        with pytest.raises(ValueError, match="must contain 'action_type'"):
            parse_action({"x": 100})
    
    def test_parse_action_with_unknown_type_raises_error(self):
        """Test that parsing with unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown action type"):
            parse_action({"action_type": "unknown"})
