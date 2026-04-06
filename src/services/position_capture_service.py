"""
Position Capture Service for EasyMacro.

Manages capturing mouse position via global hotkey with timeout.
Uses pynput for keyboard listening and Qt signals for thread-safe UI updates.

Architecture:
    - pynput runs in background thread
    - Qt signals marshal updates to main thread via queued connections
    - State machine: idle → capturing → captured/cancelled → idle
"""

from typing import Optional
from enum import Enum
from threading import Lock

from PySide6.QtCore import QObject, Signal, QTimer
from pynput import keyboard

from src.core.logger import get_logger
from src.core.event_bus import get_event_bus, EventBus
from src.core.exceptions import HotkeyError


class CaptureState(Enum):
    """Position capture state enumeration.
    
    State machine:
        idle → capturing (start_capture called)
        capturing → captured (hotkey pressed, position obtained)
        capturing → cancelled (Esc pressed or timeout)
        captured/cancelled → idle (stop_capture called)
    """
    IDLE = "idle"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    CANCELLED = "cancelled"


class PositionCaptureService(QObject):
    """Service for capturing mouse position via global hotkey.
    
    This service manages the position capture workflow:
    1. Starts listening for a global hotkey (default: F2)
    2. When hotkey pressed, gets mouse position from AHKService
    3. Emits events via EventBus for UI updates
    4. Times out after specified duration if no hotkey pressed
    
    Thread Safety:
        - pynput keyboard listener runs in a background thread
        - Internal signals marshal updates to main thread
        - State is protected by a mutex
        - EventBus emits from main thread only
    
    Usage:
        service = PositionCaptureService()
        service.start_capture(capture_key="f2", timeout_ms=30000)
        # ... wait for position_captured signal or timeout
        service.stop_capture()
    """
    
    # Internal signals for thread-safe updates (from background thread)
    _position_captured_signal = Signal(int, int)  # x, y
    _capture_timeout_signal = Signal()
    _capture_cancelled_signal = Signal()
    
    def __init__(self):
        """Initialize the position capture service."""
        super().__init__()
        
        self._logger = get_logger("position_capture")
        self._state = CaptureState.IDLE
        self._state_lock = Lock()
        
        self._capture_key: str = "f2"
        self._timeout_ms: int = 30000
        
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._timeout_timer: Optional[QTimer] = None
        
        # Get service references (may be None if not initialized)
        self._event_bus: Optional[EventBus] = None
        self._ahk_service = None
        
        try:
            self._event_bus = get_event_bus()
        except RuntimeError as e:
            self._logger.warning(f"EventBus not available: {e}")
        
        try:
            from src.services.ahk_service import get_ahk_service
            self._ahk_service = get_ahk_service()
        except RuntimeError as e:
            self._logger.warning(f"AHKService not available: {e}")
        
        # Connect internal signals to slots
        self._position_captured_signal.connect(self._on_position_captured)
        self._capture_timeout_signal.connect(self._on_capture_timeout)
        self._capture_cancelled_signal.connect(self._on_capture_cancelled)
        
        self._logger.info("PositionCaptureService initialized")
    
    def start_capture(self, capture_key: str = "f2", timeout_ms: int = 30000) -> bool:
        """Start listening for position capture hotkey immediately.
        
        Note: Use start_capture_delayed() when window needs to be minimized first.
        
        Args:
            capture_key: Key to listen for (default: "f2").
            timeout_ms: Timeout in milliseconds (default: 30000 = 30 seconds).
        
        Returns:
            True if capture started, False if already capturing.
        
        Raises:
            ValueError: If capture_key is empty or timeout_ms is invalid.
            RuntimeError: If required services are not available.
        """
        # Early exit: validate inputs
        if not capture_key:
            raise ValueError("Capture key cannot be empty")
        
        if timeout_ms <= 0:
            raise ValueError(f"Timeout must be positive: {timeout_ms}")
        
        # Early exit: check if already capturing
        if self._is_capturing():
            self._logger.warning("Capture already in progress, ignoring start request")
            return False
        
        # Early exit: check required services
        if self._ahk_service is None:
            raise RuntimeError("AHKService not initialized. Cannot capture position.")
        
        if self._event_bus is None:
            raise RuntimeError("EventBus not initialized. Cannot emit capture events.")
        
        # Parse and store capture parameters
        self._capture_key = capture_key.lower()
        self._timeout_ms = timeout_ms
        
        # Transition to capturing state
        self._set_state(CaptureState.CAPTURING)
        
        # Setup timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout_triggered)
        self._timeout_timer.start(timeout_ms)
        
        # Start keyboard listener immediately
        try:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._keyboard_listener.start()
        except Exception as e:
            self._logger.error(f"Failed to start keyboard listener: {e}")
            self._cleanup()
            self._set_state(CaptureState.CANCELLED)
            raise HotkeyError(f"Failed to start keyboard listener: {e}") from e
        
        self._logger.info(f"Started position capture with key '{capture_key}', timeout {timeout_ms}ms")
        return True
    
    def start_capture_delayed(self, capture_key: str = "f2", timeout_ms: int = 30000, delay_ms: int = 200) -> None:
        """Start capture after delay to allow window state changes.
        
        Args:
            capture_key: Key to listen for (default: "f2").
            timeout_ms: Timeout in milliseconds (default: 30000 = 30 seconds).
            delay_ms: Delay before starting listener (default: 200ms).
        """
        # Store parameters
        self._capture_key = capture_key.lower()
        self._timeout_ms = timeout_ms
        
        # Early exit: check if already capturing
        if self._is_capturing():
            self._logger.warning("Capture already in progress, ignoring start request")
            return
        
        # Transition to capturing state immediately
        self._set_state(CaptureState.CAPTURING)
        
        # Start timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_timeout_triggered)
        self._timeout_timer.start(timeout_ms)
        
        # Delay keyboard listener start
        QTimer.singleShot(delay_ms, self._start_keyboard_listener)
        
        self._logger.info(f"Delayed capture scheduled with key '{capture_key}', timeout {timeout_ms}ms, delay {delay_ms}ms")
    
    def _start_keyboard_listener(self) -> None:
        """Start the keyboard listener (called after delay)."""
        if not self._is_capturing():
            self._logger.debug("Capture cancelled before listener started")
            return
        
        try:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._keyboard_listener.start()
            self._logger.debug("Keyboard listener started")
        except Exception as e:
            self._logger.error(f"Failed to start keyboard listener: {e}")
            self._cleanup()
            self._set_state(CaptureState.CANCELLED)
            if self._event_bus is not None:
                self._event_bus.position_capture_cancelled.emit()
    
    def stop_capture(self) -> None:
        """Stop capturing and cleanup resources.
        
        Returns the service to idle state regardless of current state.
        """
        self._cleanup()
        self._set_state(CaptureState.IDLE)
        self._logger.debug("Position capture stopped")
    
    def get_state(self) -> str:
        """Get current state as string.
        
        Returns:
            One of: 'idle', 'capturing', 'captured', 'cancelled'
        """
        with self._state_lock:
            return self._state.value
    
    def is_capturing(self) -> bool:
        """Check if currently capturing.
        
        Returns:
            True if in capturing state, False otherwise.
        """
        return self._is_capturing()
    
    def _is_capturing(self) -> bool:
        """Internal check for capturing state (thread-safe)."""
        with self._state_lock:
            return self._state == CaptureState.CAPTURING
    
    def _set_state(self, new_state: CaptureState) -> None:
        """Set state atomically (thread-safe).
        
        Args:
            new_state: The new state to transition to.
        """
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            self._logger.debug(f"State transition: {old_state.value} → {new_state.value}")
    
    def _get_key_name(self, key) -> Optional[str]:
        """Get string name for a key.
        
        Args:
            key: pynput key object.
        
        Returns:
            Key name string or None.
        """
        from pynput.keyboard import Key
        
        if isinstance(key, Key):
            return key.name.lower()
        
        try:
            if hasattr(key, 'char') and key.char:
                return key.char.lower()
        except AttributeError:
            pass
        
        return None
    
    def _on_key_press(self, key) -> None:
        """Handle key press from pynput listener (background thread).
        
        Args:
            key: The key that was pressed.
        """
        # Early exit: ignore if not capturing
        if not self._is_capturing():
            return
        
        try:
            # Log key press for debugging
            key_name = self._get_key_name(key)
            if key_name:
                self._logger.debug(f"Key pressed: {key_name}")
            
            # Check for capture key
            if self._is_capture_key(key):
                self._logger.info(f"Capture key '{self._capture_key}' pressed")
                self._handle_capture_key()
            # Check for escape key (cancel)
            elif key == keyboard.Key.esc:
                self._logger.info("Escape key pressed, cancelling capture")
                self._capture_cancelled_signal.emit()
        except Exception as e:
            self._logger.error(f"Error handling key press: {e}")
    
    def _on_key_release(self, key) -> None:
        """Handle key release from pynput listener (background thread).
        
        Args:
            key: The key that was released.
        """
        # No action needed on key release
        pass
    
    def _is_capture_key(self, key) -> bool:
        """Check if the pressed key matches the capture key.
        
        Args:
            key: The key from pynput.
        
        Returns:
            True if the key matches the capture key.
        """
        try:
            # Handle special keys (F1-F24)
            if hasattr(keyboard.Key, self._capture_key):
                return key == getattr(keyboard.Key, self._capture_key)
            
            # Handle character keys
            if hasattr(key, 'char') and key.char:
                return key.char.lower() == self._capture_key
            
            # Handle named keys
            return str(key).lower().replace("key.", "") == self._capture_key
        except Exception as e:
            self._logger.error(f"Error checking capture key: {e}")
            return False
    
    def _handle_capture_key(self) -> None:
        """Handle capture key press (called from background thread).
        
        Gets mouse position and emits signal for main thread processing.
        """
        try:
            if self._ahk_service is None:
                raise RuntimeError("AHKService not available")
            
            x, y = self._ahk_service.get_mouse_position()
            self._position_captured_signal.emit(x, y)
            
        except Exception as e:
            self._logger.error(f"Failed to get mouse position: {e}")
            self._capture_cancelled_signal.emit()
    
    def _on_timeout_triggered(self) -> None:
        """Handle timeout timer expiration (main thread)."""
        self._logger.info("Position capture timed out")
        self._capture_timeout_signal.emit()
    
    def _on_position_captured(self, x: int, y: int) -> None:
        """Slot for position captured signal (main thread).
        
        Args:
            x: X coordinate of mouse position.
            y: Y coordinate of mouse position.
        """
        # Early exit: ignore if not capturing
        if not self._is_capturing():
            return
        
        self._logger.info(f"Position captured at ({x}, {y})")
        self._cleanup()
        self._set_state(CaptureState.CAPTURED)
        
        # Emit event via EventBus
        if self._event_bus is not None:
            self._event_bus.position_captured.emit(x, y)
    
    def _on_capture_timeout(self) -> None:
        """Slot for capture timeout signal (main thread)."""
        # Early exit: ignore if not capturing
        if not self._is_capturing():
            return
        
        self._logger.info("Capture timed out")
        self._cleanup()
        self._set_state(CaptureState.CANCELLED)
        
        # Emit event via EventBus
        if self._event_bus is not None:
            self._event_bus.position_capture_cancelled.emit()
    
    def _on_capture_cancelled(self) -> None:
        """Slot for capture cancelled signal (main thread)."""
        # Early exit: ignore if not capturing
        if not self._is_capturing():
            return
        
        self._logger.info("Capture cancelled")
        self._cleanup()
        self._set_state(CaptureState.CANCELLED)
        
        # Emit event via EventBus
        if self._event_bus is not None:
            self._event_bus.position_capture_cancelled.emit()
    
    def __del__(self):
        """Destructor - ensure cleanup on garbage collection."""
        try:
            self._cleanup()
        except Exception:
            pass  # Ignore errors during destruction

    def _cleanup(self) -> None:
        """Cleanup resources (timer and keyboard listener)."""
        # Stop and cleanup timer
        if self._timeout_timer is not None:
            try:
                if self._timeout_timer.isActive():
                    self._timeout_timer.stop()
                # Delete the timer to prevent Qt warnings
                self._timeout_timer.deleteLater()
            except Exception as e:
                self._logger.error(f"Error stopping timer: {e}")
            finally:
                self._timeout_timer = None

        # Stop and cleanup keyboard listener
        if self._keyboard_listener is not None:
            try:
                if self._keyboard_listener.is_alive():
                    self._keyboard_listener.stop()
                    self._keyboard_listener.join(timeout=1.0)
            except Exception as e:
                self._logger.error(f"Error stopping keyboard listener: {e}")
            finally:
                self._keyboard_listener = None


# Global singleton instance
_position_capture_service: Optional[PositionCaptureService] = None


def get_position_capture_service() -> PositionCaptureService:
    """Get the global PositionCaptureService instance.
    
    Raises:
        RuntimeError: If service not initialized.
    
    Returns:
        PositionCaptureService: The global service instance.
    """
    if _position_capture_service is None:
        raise RuntimeError(
            "PositionCaptureService not initialized. "
            "Call init_position_capture_service() first."
        )
    return _position_capture_service


def init_position_capture_service() -> PositionCaptureService:
    """Initialize the global PositionCaptureService.
    
    Returns:
        PositionCaptureService: The newly created service instance.
    
    Raises:
        RuntimeError: If service already initialized.
    """
    global _position_capture_service
    
    if _position_capture_service is not None:
        raise RuntimeError("PositionCaptureService already initialized.")
    
    _position_capture_service = PositionCaptureService()
    return _position_capture_service
