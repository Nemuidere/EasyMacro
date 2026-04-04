"""
Tests for Macro model.

Tests Pydantic validation for macro definition.
"""

import pytest

from src.models.macro import Macro, MacroStatus
from src.models.action import ClickAction, DelayAction


class TestMacro:
    """Tests for Macro model."""
    
    def test_create_macro(self):
        """Test creating a macro."""
        macro = Macro(name="Test Macro")
        
        assert macro.name == "Test Macro"
        assert macro.description == ""
        assert macro.actions == []
        assert macro.hotkey is None
        assert macro.enabled is True
        assert macro.repeat_count == 1
        assert macro.status == MacroStatus.IDLE
    
    def test_create_macro_with_actions(self, sample_click_action, sample_delay_action):
        """Test creating a macro with actions."""
        macro = Macro(
            name="Test Macro",
            actions=[sample_click_action, sample_delay_action]
        )
        
        assert len(macro.actions) == 2
    
    def test_create_macro_with_empty_name_raises_error(self):
        """Test that creating macro with empty name raises ValueError."""
        with pytest.raises(ValueError, match="Macro name cannot be empty"):
            Macro(name="")
    
    def test_create_macro_with_whitespace_name_raises_error(self):
        """Test that creating macro with whitespace name raises ValueError."""
        with pytest.raises(ValueError, match="Macro name cannot be empty"):
            Macro(name="   ")
    
    def test_create_macro_with_hotkey(self):
        """Test creating a macro with hotkey."""
        macro = Macro(name="Test Macro", hotkey="ctrl+a")
        
        assert macro.hotkey == "ctrl+a"
    
    def test_create_macro_with_invalid_repeat_count_raises_error(self):
        """Test that invalid repeat count raises ValueError."""
        with pytest.raises(ValueError):
            Macro(name="Test Macro", repeat_count=-1)
    
    def test_add_action(self, sample_macro, sample_click_action):
        """Test adding an action to a macro."""
        initial_count = len(sample_macro.actions)
        
        sample_macro.add_action(sample_click_action)
        
        assert len(sample_macro.actions) == initial_count + 1
    
    def test_remove_action(self, sample_macro):
        """Test removing an action from a macro."""
        # Add an action first
        action = ClickAction(x=50, y=50)
        sample_macro.add_action(action)
        
        # Remove it
        result = sample_macro.remove_action(action.id)
        
        assert result is True
    
    def test_remove_nonexistent_action(self, sample_macro):
        """Test removing nonexistent action returns False."""
        result = sample_macro.remove_action("nonexistent_id")
        
        assert result is False
    
    def test_clear_actions(self, sample_macro):
        """Test clearing all actions."""
        sample_macro.clear_actions()
        
        assert len(sample_macro.actions) == 0
    
    def test_is_running(self, sample_macro):
        """Test is_running check."""
        sample_macro.status = MacroStatus.RUNNING
        
        assert sample_macro.is_running() is True
        assert sample_macro.is_idle() is False
    
    def test_is_paused(self, sample_macro):
        """Test is_paused check."""
        sample_macro.status = MacroStatus.PAUSED
        
        assert sample_macro.is_paused() is True
        assert sample_macro.is_idle() is False
    
    def test_is_idle(self, sample_macro):
        """Test is_idle check."""
        assert sample_macro.is_idle() is True
    
    def test_touch_updates_timestamp(self, sample_macro):
        """Test that touch updates the updated_at timestamp."""
        import time
        
        old_timestamp = sample_macro.updated_at
        time.sleep(0.01)  # Small delay
        
        sample_macro.touch()
        
        assert sample_macro.updated_at > old_timestamp
    
    def test_to_dict(self, sample_macro):
        """Test converting macro to dictionary."""
        data = sample_macro.to_dict()
        
        assert isinstance(data, dict)
        assert "id" in data
        assert "name" in data
        assert data["name"] == sample_macro.name
    
    def test_to_json(self, sample_macro):
        """Test converting macro to JSON."""
        json_str = sample_macro.to_json()
        
        assert isinstance(json_str, str)
        assert "Test Macro" in json_str
