"""
Tests for the StateManager.

Tests thread-safe application state management.
"""

import pytest

from src.core.state import StateManager, AppState, init_state_manager, get_state_manager


class TestStateManager:
    """Tests for StateManager class."""
    
    def test_init_creates_idle_state(self):
        """Test that initialization creates idle state."""
        manager = StateManager()
        
        assert manager.get() == AppState.IDLE
        assert manager.is_idle() is True
    
    def test_set_state(self):
        """Test setting state."""
        manager = StateManager()
        
        manager.set(AppState.RUNNING)
        
        assert manager.get() == AppState.RUNNING
        assert manager.is_running() is True
    
    def test_set_state_with_none_raises_error(self):
        """Test that setting None state raises ValueError."""
        manager = StateManager()
        
        with pytest.raises(ValueError, match="State cannot be None"):
            manager.set(None)
    
    def test_is_running(self):
        """Test is_running check."""
        manager = StateManager()
        
        manager.set(AppState.RUNNING)
        assert manager.is_running() is True
        
        manager.set(AppState.IDLE)
        assert manager.is_running() is False
    
    def test_is_paused(self):
        """Test is_paused check."""
        manager = StateManager()
        
        manager.set(AppState.PAUSED)
        assert manager.is_paused() is True
        
        manager.set(AppState.IDLE)
        assert manager.is_paused() is False
    
    def test_is_error(self):
        """Test is_error check."""
        manager = StateManager()
        
        manager.set(AppState.ERROR)
        assert manager.is_error() is True
        
        manager.set(AppState.IDLE)
        assert manager.is_error() is False
    
    def test_current_macro(self):
        """Test setting and getting current macro."""
        manager = StateManager()
        
        manager.set_current_macro("test_macro_id")
        
        assert manager.get_current_macro() == "test_macro_id"
    
    def test_clear_current_macro(self):
        """Test clearing current macro."""
        manager = StateManager()
        
        manager.set_current_macro("test_macro_id")
        manager.set_current_macro(None)
        
        assert manager.get_current_macro() is None
    
    def test_set_error(self):
        """Test setting error state."""
        manager = StateManager()
        
        manager.set_error("Test error message")
        
        assert manager.is_error() is True
        assert manager.get_error() == "Test error message"
    
    def test_set_error_with_empty_message_raises_error(self):
        """Test that setting empty error message raises ValueError."""
        manager = StateManager()
        
        with pytest.raises(ValueError, match="Error message cannot be empty"):
            manager.set_error("")
    
    def test_clear_error(self):
        """Test clearing error state."""
        manager = StateManager()
        
        manager.set_error("Test error")
        manager.clear_error()
        
        assert manager.is_idle() is True
        assert manager.get_error() is None


class TestStateManagerSingleton:
    """Tests for singleton functions."""
    
    def test_init_state_manager(self):
        """Test initializing the singleton."""
        # Reset singleton
        import src.core.state as state_module
        state_module._state_manager = None
        
        manager = init_state_manager()
        
        assert manager is not None
        assert isinstance(manager, StateManager)
        
        # Cleanup
        state_module._state_manager = None
    
    def test_init_twice_raises_error(self):
        """Test that initializing twice raises RuntimeError."""
        # Reset singleton
        import src.core.state as state_module
        state_module._state_manager = None
        
        init_state_manager()
        
        with pytest.raises(RuntimeError, match="already initialized"):
            init_state_manager()
        
        # Cleanup
        state_module._state_manager = None
    
    def test_get_without_init_raises_error(self):
        """Test that getting without init raises RuntimeError."""
        # Reset singleton
        import src.core.state as state_module
        state_module._state_manager = None
        
        with pytest.raises(RuntimeError, match="not initialized"):
            get_state_manager()
