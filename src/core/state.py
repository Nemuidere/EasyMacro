"""
Application state management for EasyMacro.

Provides thread-safe state management using QMutex.
"""

from typing import Optional, Any
from enum import Enum
from PySide6.QtCore import QMutex, QMutexLocker


class AppState(Enum):
    """Application state enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class StateManager:
    """
    Thread-safe application state manager.
    
    Manages global application state with QMutex protection.
    
    Usage:
        state = StateManager()
        state.set(AppState.RUNNING)
        if state.is_running():
            # Do something
    """
    
    def __init__(self):
        """Initialize state manager."""
        self._mutex = QMutex()
        self._state: AppState = AppState.IDLE
        self._current_macro_id: Optional[str] = None
        self._error_message: Optional[str] = None
    
    def get(self) -> AppState:
        """Get current application state.
        
        Returns:
            Current AppState.
        """
        with QMutexLocker(self._mutex):
            return self._state
    
    def set(self, state: AppState) -> None:
        """Set application state.
        
        Args:
            state: New state to set.
        
        Raises:
            ValueError: If state is None.
        """
        if state is None:
            raise ValueError("State cannot be None")
        
        with QMutexLocker(self._mutex):
            self._state = state
    
    def is_idle(self) -> bool:
        """Check if application is idle.
        
        Returns:
            True if idle, False otherwise.
        """
        return self.get() == AppState.IDLE
    
    def is_running(self) -> bool:
        """Check if application is running a macro.
        
        Returns:
            True if running, False otherwise.
        """
        return self.get() == AppState.RUNNING
    
    def is_paused(self) -> bool:
        """Check if application is paused.
        
        Returns:
            True if paused, False otherwise.
        """
        return self.get() == AppState.PAUSED
    
    def is_error(self) -> bool:
        """Check if application is in error state.
        
        Returns:
            True if error, False otherwise.
        """
        return self.get() == AppState.ERROR
    
    def get_current_macro(self) -> Optional[str]:
        """Get the currently running macro ID.
        
        Returns:
            Macro ID if running, None otherwise.
        """
        with QMutexLocker(self._mutex):
            return self._current_macro_id
    
    def set_current_macro(self, macro_id: Optional[str]) -> None:
        """Set the currently running macro ID.
        
        Args:
            macro_id: Macro ID to set, or None to clear.
        """
        with QMutexLocker(self._mutex):
            self._current_macro_id = macro_id
    
    def get_error(self) -> Optional[str]:
        """Get the current error message.
        
        Returns:
            Error message if in error state, None otherwise.
        """
        with QMutexLocker(self._mutex):
            return self._error_message
    
    def set_error(self, message: str) -> None:
        """Set error state with message.
        
        Args:
            message: Error message.
        
        Raises:
            ValueError: If message is empty.
        """
        if not message:
            raise ValueError("Error message cannot be empty")
        
        with QMutexLocker(self._mutex):
            self._state = AppState.ERROR
            self._error_message = message
    
    def clear_error(self) -> None:
        """Clear error state and return to idle."""
        with QMutexLocker(self._mutex):
            self._state = AppState.IDLE
            self._error_message = None


# Global singleton instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance.
    
    Raises:
        RuntimeError: If state manager not initialized.
    
    Returns:
        StateManager: The global state manager instance.
    """
    if _state_manager is None:
        raise RuntimeError("State manager not initialized. Call init_state_manager() first.")
    
    return _state_manager


def init_state_manager() -> StateManager:
    """Initialize the global state manager.
    
    Returns:
        StateManager: The newly created state manager instance.
    
    Raises:
        RuntimeError: If state manager already initialized.
    """
    global _state_manager
    
    if _state_manager is not None:
        raise RuntimeError("State manager already initialized.")
    
    _state_manager = StateManager()
    return _state_manager
