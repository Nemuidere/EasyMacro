"""
Mouse Movement Service for EasyMacro.

Detects mouse movement during macro execution to implement "stop on mouse movement" 
safety feature. Uses pynput for mouse monitoring and Qt signals for thread-safe 
UI updates.

Architecture:
    - pynput mouse listener runs in background thread
    - Qt signals marshal updates to main thread via queued connections
    - State machine: idle → monitoring → movement_exceeded → idle
    - Euclidean distance calculation for movement detection
"""

from typing import Optional, Tuple
from threading import Lock
from math import sqrt

from PySide6.QtCore import QObject, Signal
from pynput import mouse

from src.core.logger import get_logger
from src.core.exceptions import MacroExecutionError


class MouseMovementService(QObject):
    """Service for detecting mouse movement during macro execution.
    
    Monitors mouse position and emits signal when movement exceeds threshold.
    Used to implement "stop on mouse movement" safety feature.
    
    Thread Safety:
        - pynput mouse listener runs in background thread
        - Internal signals marshal updates to main thread
        - State protected by threading.Lock
        - Distance calculations thread-safe via mutex
    
    Usage:
        service = MouseMovementService()
        service.start_monitoring(threshold_pixels=50)
        # ... wait for movement_exceeded signal
        service.stop_monitoring()
    
    State Machine:
        idle → monitoring (start_monitoring called)
        monitoring → movement_exceeded (distance > threshold)
        monitoring → idle (stop_monitoring called)
    """
    
    # Internal signal for thread-safe updates (from background thread)
    _movement_detected = Signal(float, float)  # distance, threshold
    
    # Public signal for main thread consumption
    movement_exceeded = Signal(float)  # distance moved when threshold exceeded
    
    def __init__(self):
        """Initialize the mouse movement service."""
        super().__init__()
        
        self._logger = get_logger("mouse_movement")
        
        # State tracking
        self._is_monitoring = False
        self._state_lock = Lock()
        
        # Position tracking
        self._initial_position: Optional[Tuple[int, int]] = None
        self._current_position: Optional[Tuple[int, int]] = None
        self._position_lock = Lock()
        
        # Threshold configuration
        self._threshold_pixels: int = 50
        
        # pynput mouse listener
        self._mouse_listener: Optional[mouse.Listener] = None
        
        # AHK service reference (lazy loaded)
        self._ahk_service = None
        
        # Connect internal signals to slots
        self._movement_detected.connect(self._on_movement_detected)
        
        self._logger.info("MouseMovementService initialized")
    
    def start_monitoring(self, threshold_pixels: int = 50) -> bool:
        """Start monitoring mouse movement.
        
        Captures initial mouse position and begins monitoring for movement
        that exceeds the specified threshold.
        
        Args:
            threshold_pixels: Movement threshold in pixels (default: 50).
        
        Returns:
            True if monitoring started, False if already monitoring.
        
        Raises:
            ValueError: If threshold is not positive.
            RuntimeError: If AHKService not initialized.
            MacroExecutionError: If mouse listener fails to start.
        """
        # Early exit: validate threshold
        if threshold_pixels <= 0:
            raise ValueError(f"Threshold must be positive: {threshold_pixels}")
        
        # Early exit: check if already monitoring
        if self._is_monitoring_state():
            self._logger.warning("Already monitoring mouse movement, ignoring start request")
            return False
        
        # Early exit: get AHK service
        ahk_service = self._get_ahk_service()
        if ahk_service is None:
            raise RuntimeError("AHKService not initialized. Cannot monitor mouse movement.")
        
        # Store threshold
        self._threshold_pixels = threshold_pixels
        
        # Capture initial position
        try:
            initial_pos = ahk_service.get_mouse_position()
        except Exception as e:
            self._logger.error(f"Failed to get initial mouse position: {e}")
            raise MacroExecutionError(f"Failed to get initial mouse position: {e}") from e
        
        with self._position_lock:
            self._initial_position = initial_pos
            self._current_position = initial_pos
        
        # Transition to monitoring state
        self._set_monitoring_state(True)
        
        # Start mouse listener
        try:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move
            )
            self._mouse_listener.start()
        except Exception as e:
            self._logger.error(f"Failed to start mouse listener: {e}")
            self._cleanup()
            self._set_monitoring_state(False)
            raise MacroExecutionError(f"Failed to start mouse listener: {e}") from e
        
        self._logger.info(
            f"Started mouse movement monitoring from {initial_pos}, "
            f"threshold: {threshold_pixels}px"
        )
        return True
    
    def stop_monitoring(self) -> None:
        """Stop monitoring and cleanup resources.
        
        Stops the mouse listener and resets state to idle.
        Safe to call multiple times.
        """
        if not self._is_monitoring_state():
            self._logger.debug("Not monitoring, nothing to stop")
            return
        
        self._cleanup()
        self._set_monitoring_state(False)
        
        with self._position_lock:
            self._initial_position = None
            self._current_position = None
        
        self._logger.info("Mouse movement monitoring stopped")
    
    def is_monitoring(self) -> bool:
        """Check if currently monitoring mouse movement.
        
        Returns:
            True if in monitoring state, False otherwise.
        """
        return self._is_monitoring_state()
    
    def get_distance_moved(self) -> float:
        """Get Euclidean distance moved from initial position.
        
        Returns:
            Distance in pixels from initial position to current position.
            Returns 0.0 if not monitoring or positions not available.
        """
        with self._position_lock:
            if self._initial_position is None or self._current_position is None:
                return 0.0
            
            return self._calculate_distance(self._initial_position, self._current_position)
    
    def get_current_position(self) -> Optional[Tuple[int, int]]:
        """Get current mouse position.
        
        Returns:
            Tuple of (x, y) coordinates, or None if not monitoring.
        """
        with self._position_lock:
            return self._current_position
    
    def get_initial_position(self) -> Optional[Tuple[int, int]]:
        """Get initial mouse position when monitoring started.
        
        Returns:
            Tuple of (x, y) coordinates, or None if not monitoring.
        """
        with self._position_lock:
            return self._initial_position
    
    def _on_mouse_move(self, x: int, y: int) -> None:
        """Handle mouse move event from pynput listener (background thread).
        
        Args:
            x: Current X coordinate.
            y: Current Y coordinate.
        """
        # Early exit: ignore if not monitoring
        if not self._is_monitoring_state():
            return
        
        try:
            # Update current position
            with self._position_lock:
                self._current_position = (x, y)
                
                # Calculate distance from initial position
                if self._initial_position is None:
                    return
                
                distance = self._calculate_distance(
                    self._initial_position, 
                    self._current_position
                )
            
            # Check if threshold exceeded
            if distance > self._threshold_pixels:
                self._movement_detected.emit(distance, float(self._threshold_pixels))
                
        except Exception as e:
            self._logger.error(f"Error handling mouse move: {e}")
    
    def _on_movement_detected(self, distance: float, threshold: float) -> None:
        """Slot for movement detected signal (main thread).
        
        Args:
            distance: Distance moved in pixels.
            threshold: Threshold that was exceeded.
        """
        # Early exit: ignore if not monitoring (could have stopped between signal emit and slot)
        if not self._is_monitoring_state():
            return
        
        self._logger.info(
            f"Mouse movement exceeded threshold: {distance:.1f}px > {threshold:.1f}px"
        )
        
        # Emit public signal
        self.movement_exceeded.emit(distance)
        
        # Stop monitoring after threshold exceeded
        self.stop_monitoring()
    
    def _calculate_distance(
        self, 
        pos1: Tuple[int, int], 
        pos2: Tuple[int, int]
    ) -> float:
        """Calculate Euclidean distance between two points.
        
        Args:
            pos1: First position tuple (x1, y1).
            pos2: Second position tuple (x2, y2).
        
        Returns:
            Euclidean distance in pixels.
        """
        x1, y1 = pos1
        x2, y2 = pos2
        return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    def _is_monitoring_state(self) -> bool:
        """Check if currently monitoring (thread-safe).
        
        Returns:
            True if in monitoring state, False otherwise.
        """
        with self._state_lock:
            return self._is_monitoring
    
    def _set_monitoring_state(self, monitoring: bool) -> None:
        """Set monitoring state atomically (thread-safe).
        
        Args:
            monitoring: New monitoring state.
        """
        with self._state_lock:
            old_state = self._is_monitoring
            self._is_monitoring = monitoring
            self._logger.debug(f"State: monitoring={old_state} → {monitoring}")
    
    def _get_ahk_service(self):
        """Get AHK service instance (lazy loading).
        
        Returns:
            AHKService instance or None if not available.
        """
        if self._ahk_service is None:
            try:
                from src.services.ahk_service import get_ahk_service
                self._ahk_service = get_ahk_service()
            except RuntimeError as e:
                self._logger.warning(f"AHKService not available: {e}")
                return None
        return self._ahk_service
    
    def _cleanup(self) -> None:
        """Cleanup mouse listener resources.
        
        Stops and joins the mouse listener safely.
        """
        if self._mouse_listener is not None:
            try:
                if self._mouse_listener.is_alive():
                    self._mouse_listener.stop()
                    self._mouse_listener.join(timeout=1.0)
            except Exception as e:
                self._logger.error(f"Error stopping mouse listener: {e}")
            finally:
                self._mouse_listener = None


# Global singleton instance
_mouse_movement_service: Optional[MouseMovementService] = None


def get_mouse_movement_service() -> MouseMovementService:
    """Get the global MouseMovementService instance.
    
    Raises:
        RuntimeError: If service not initialized.
    
    Returns:
        MouseMovementService: The global service instance.
    """
    if _mouse_movement_service is None:
        raise RuntimeError(
            "MouseMovementService not initialized. "
            "Call init_mouse_movement_service() first."
        )
    return _mouse_movement_service


def init_mouse_movement_service() -> MouseMovementService:
    """Initialize the global MouseMovementService.
    
    Returns:
        MouseMovementService: The newly created service instance.
    
    Raises:
        RuntimeError: If service already initialized.
    """
    global _mouse_movement_service
    
    if _mouse_movement_service is not None:
        raise RuntimeError("MouseMovementService already initialized.")
    
    _mouse_movement_service = MouseMovementService()
    return _mouse_movement_service
