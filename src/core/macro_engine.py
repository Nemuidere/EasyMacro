"""
Macro execution engine for EasyMacro.

Handles the execution of macro actions with optional randomization.
"""

from typing import Optional, Callable, TYPE_CHECKING
from enum import Enum
from time import time
from PySide6.QtCore import QObject, Signal, QTimer

from src.models.macro import Macro, MacroStatus
from src.models.action import Action, ActionType, ClickAction, DelayAction, KeyPressAction, MouseMoveAction
from src.models.settings import RandomizationSettings
from src.core.randomization import RandomizationEngine
from src.core.state import StateManager, AppState
from src.core.event_bus import EventBus, get_event_bus
from src.core.exceptions import MacroError, MacroExecutionError
from src.core.logger import get_logger
from src.core.constants import MODIFIER_KEY_DOWN_ORDER, MODIFIER_KEY_UP_ORDER
from src.services.stats_service import StatsService, get_stats_service

if TYPE_CHECKING:
    from src.services.mouse_movement_service import MouseMovementService


class ExecutionState(Enum):
    """State of macro execution."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class MacroEngine(QObject):
    """
    Executes macros with optional randomization.
    
    The engine runs macros action by action, applying randomization
    if enabled. It communicates progress via Qt signals.
    
    Signals:
        action_started: Emitted when an action starts (action_id, action_type)
        action_completed: Emitted when an action completes (action_id)
        macro_started: Emitted when macro starts (macro_id)
        macro_completed: Emitted when macro completes (macro_id)
        macro_error: Emitted on error (macro_id, error_message)
    
    Usage:
        engine = MacroEngine(ahk_service, randomization_engine)
        engine.run_macro(macro)
    """
    
    # Signals
    action_started = Signal(str, str)  # action_id, action_type
    action_completed = Signal(str)  # action_id
    macro_started = Signal(str)  # macro_id
    macro_completed = Signal(str)  # macro_id
    macro_error = Signal(str, str)  # macro_id, error_message
    
    def __init__(
        self,
        randomization_engine: RandomizationEngine,
        state_manager: StateManager,
        stats_service: StatsService,
        mouse_movement_service: Optional['MouseMovementService'] = None,
        parent: Optional[QObject] = None
    ):
        """Initialize macro engine.
        
        Args:
            randomization_engine: Engine for applying randomization.
            state_manager: Application state manager.
            stats_service: Statistics tracking service.
            mouse_movement_service: Optional service for mouse movement detection.
            parent: Optional Qt parent.
        
        Raises:
            ValueError: If any argument is None.
        """
        super().__init__(parent)
        
        if randomization_engine is None:
            raise ValueError("Randomization engine cannot be None")
        if state_manager is None:
            raise ValueError("State manager cannot be None")
        if stats_service is None:
            raise ValueError("Stats service cannot be None")
        
        self._randomization = randomization_engine
        self._state = state_manager
        self._stats = stats_service
        self._mouse_movement_service = mouse_movement_service
        self._logger = get_logger("macro_engine")
        self._event_bus = get_event_bus()
        
        self._current_macro: Optional[Macro] = None
        self._current_action_index: int = 0
        self._execution_state: ExecutionState = ExecutionState.IDLE
        self._repeat_count: int = 0
        self._current_repeat: int = 0
        self._macro_start_time: float = 0.0
        
        # Stop on mouse movement settings
        self._stop_on_mouse_movement: bool = True
        self._mouse_movement_threshold: int = 50
        
        # Connect to mouse movement signal if service available
        if self._mouse_movement_service:
            self._mouse_movement_service.movement_exceeded.connect(
                self._on_mouse_movement_exceeded
            )
        
        # Timer for delays
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._on_delay_complete)
    
    def run_macro(self, macro: Macro) -> None:
        """Start executing a macro.
        
        Args:
            macro: Macro to execute.
        
        Raises:
            ValueError: If macro is None or has no actions.
            MacroExecutionError: If another macro is already running.
        """
        if macro is None:
            raise ValueError("Macro cannot be None")
        if not macro.actions:
            raise ValueError(f"Macro '{macro.name}' has no actions")
        
        if self._execution_state == ExecutionState.RUNNING:
            raise MacroExecutionError(
                f"Cannot start macro '{macro.name}': another macro is running"
            )
        
        self._logger.info(f"Starting macro: {macro.name}")
        
        self._current_macro = macro
        self._current_action_index = 0
        self._current_repeat = 0
        self._repeat_count = macro.repeat_count
        self._execution_state = ExecutionState.RUNNING
        self._macro_start_time = time()
        
        # Update state
        self._state.set(AppState.RUNNING)
        self._state.set_current_macro(macro.id)
        
        # Start mouse movement monitoring if enabled
        if self._stop_on_mouse_movement and self._mouse_movement_service:
            try:
                self._mouse_movement_service.start_monitoring(
                    threshold_pixels=self._mouse_movement_threshold
                )
            except Exception as e:
                self._logger.warning(f"Failed to start mouse movement monitoring: {e}")
        
        # Emit signals
        self.macro_started.emit(macro.id)
        self._event_bus.macro_started.emit(macro.id)
        
        # Start execution
        self._execute_next_action()
    
    def pause_macro(self) -> None:
        """Pause the currently running macro.
        
        Raises:
            MacroExecutionError: If no macro is running.
        """
        if self._execution_state != ExecutionState.RUNNING:
            raise MacroExecutionError("No macro is running")
        
        self._logger.info(f"Pausing macro: {self._current_macro.name}")
        
        self._execution_state = ExecutionState.PAUSED
        self._state.set(AppState.PAUSED)
        self._delay_timer.stop()
    
    def resume_macro(self) -> None:
        """Resume a paused macro.
        
        Raises:
            MacroExecutionError: If no macro is paused.
        """
        if self._execution_state != ExecutionState.PAUSED:
            raise MacroExecutionError("No macro is paused")
        
        self._logger.info(f"Resuming macro: {self._current_macro.name}")
        
        self._execution_state = ExecutionState.RUNNING
        self._state.set(AppState.RUNNING)
        self._execute_next_action()
    
    def stop_macro(self) -> None:
        """Stop the currently running macro.
        
        Does nothing if no macro is running.
        """
        if self._execution_state == ExecutionState.IDLE:
            return
        
        self._logger.info(f"Stopping macro: {self._current_macro.name}")
        
        # Stop mouse movement monitoring
        if self._mouse_movement_service and self._mouse_movement_service.is_monitoring():
            self._mouse_movement_service.stop_monitoring()
        
        self._delay_timer.stop()
        self._execution_state = ExecutionState.STOPPED
        self._state.set(AppState.IDLE)
        self._state.set_current_macro(None)
        
        if self._current_macro:
            self._event_bus.macro_stopped.emit(self._current_macro.id)
        
        self._current_macro = None
        self._execution_state = ExecutionState.IDLE
    
    def is_running(self) -> bool:
        """Check if a macro is running.
        
        Returns:
            True if running, False otherwise.
        """
        return self._execution_state == ExecutionState.RUNNING
    
    def is_paused(self) -> bool:
        """Check if a macro is paused.
        
        Returns:
            True if paused, False otherwise.
        """
        return self._execution_state == ExecutionState.PAUSED
    
    def get_current_macro(self) -> Optional[Macro]:
        """Get the currently running macro.
        
        Returns:
            Current macro or None.
        """
        return self._current_macro
    
    def _execute_next_action(self) -> None:
        """Execute the next action in the macro."""
        if self._execution_state != ExecutionState.RUNNING:
            return
        
        if self._current_macro is None:
            self._complete_macro()
            return
        
        # Check if we've completed all actions
        if self._current_action_index >= len(self._current_macro.actions):
            # Check if we need to repeat
            if self._repeat_count == 0 or self._current_repeat < self._repeat_count - 1:
                self._current_repeat += 1
                self._current_action_index = 0
                # Apply repeat delay if configured
                if self._current_macro.repeat_delay_ms > 0:
                    self._schedule_delay(self._current_macro.repeat_delay_ms)
                    return
            else:
                self._complete_macro()
                return
        
        action = self._current_macro.actions[self._current_action_index]
        self._execute_action(action)
    
    def _execute_action(self, action: Action) -> None:
        """Execute a single action.
        
        Args:
            action: Action to execute.
        """
        self._logger.debug(f"Executing action: {action.action_type}")
        
        self.action_started.emit(action.id, action.action_type.value)
        
        try:
            if isinstance(action, ClickAction):
                self._execute_click(action)
            elif isinstance(action, DelayAction):
                self._execute_delay(action)
            elif isinstance(action, KeyPressAction):
                self._execute_key_press(action)
            elif isinstance(action, MouseMoveAction):
                self._execute_mouse_move(action)
            else:
                raise MacroExecutionError(f"Unknown action type: {action.action_type}")
            
            self.action_completed.emit(action.id)
            self._current_action_index += 1
            self._execute_next_action()
            
        except Exception as e:
            self._handle_error(str(e))
    
    def _execute_click(self, action: ClickAction) -> None:
        """Execute a click action.

        Args:
            action: Click action to execute.
        """
        # Apply jitter if randomization is enabled
        x, y = action.x, action.y
        if self._current_macro and self._current_macro.randomization_enabled:
            x, y = self._randomization.apply_jitter(action.x, action.y)

        self._logger.debug(f"Click at ({x}, {y}) with button {action.button}, modifiers {action.modifiers}")

        # Get AHK service
        from src.services.ahk_service import get_ahk_service
        ahk = get_ahk_service()

        # Press modifiers in order
        for mod in MODIFIER_KEY_DOWN_ORDER:
            if mod in action.modifiers:
                ahk.key_down(mod)

        try:
            # Determine click count based on action type
            click_count = 1
            if action.action_type == ActionType.DOUBLE_CLICK:
                click_count = 2

            # Perform click
            ahk.click(x, y, button=action.button, click_count=click_count)
            
        finally:
            # Release modifiers in reverse order
            for mod in MODIFIER_KEY_UP_ORDER:
                if mod in action.modifiers:
                    ahk.key_up(mod)

        # Track clicks in stats
        if self._current_macro:
            self._stats.update_clicks(self._current_macro.id, click_count)
    
    def _execute_delay(self, action: DelayAction) -> None:
        """Execute a delay action.

        Args:
            action: Delay action to execute.
        """
        # Apply randomization if enabled
        delay_ms = action.duration_ms
        if self._current_macro.randomization_enabled:
            delay_ms = self._randomization.randomize_delay(action.duration_ms)

        self._logger.debug(f"Delay for {delay_ms:.0f}ms")

        # Get AHK service
        from src.services.ahk_service import get_ahk_service
        ahk = get_ahk_service()

        ahk.sleep(int(delay_ms))
    
    def _execute_key_press(self, action: KeyPressAction) -> None:
        """Execute a key press action.

        Args:
            action: Key press action to execute.
        """
        self._logger.debug(f"Key press: {action.key} with modifiers {action.modifiers}")

        # Get AHK service
        from src.services.ahk_service import get_ahk_service
        ahk = get_ahk_service()

        ahk.key_press(action.key, action.modifiers)
    
    def _execute_mouse_move(self, action: MouseMoveAction) -> None:
        """Execute a mouse move action.

        Args:
            action: Mouse move action to execute.
        """
        # Apply jitter if randomization is enabled
        x, y = action.x, action.y
        if self._current_macro.randomization_enabled:
            x, y = self._randomization.apply_jitter(action.x, action.y)

        speed = action.speed
        if self._current_macro.randomization_enabled:
            speed = self._randomization.randomize_speed(action.speed)

        self._logger.debug(f"Mouse move to ({x}, {y}) with speed {speed}")

        # Get AHK service
        from src.services.ahk_service import get_ahk_service
        ahk = get_ahk_service()

        ahk.mouse_move(x, y, speed=speed, smooth=action.smooth)
    
    def _schedule_delay(self, delay_ms: float) -> None:
        """Schedule a delay.
        
        Args:
            delay_ms: Delay in milliseconds.
        """
        self._delay_timer.start(int(delay_ms))
    
    def _on_delay_complete(self) -> None:
        """Called when a delay completes."""
        self._current_action_index += 1
        self._execute_next_action()
    
    def _complete_macro(self) -> None:
        """Complete the current macro."""
        if self._current_macro is None:
            return

        self._logger.info(f"Macro completed: {self._current_macro.name}")

        macro_id = self._current_macro.id

        # Track execution time in stats
        execution_time = time() - self._macro_start_time
        self._stats.update_time(macro_id, execution_time)

        # Stop mouse movement monitoring
        if self._mouse_movement_service and self._mouse_movement_service.is_monitoring():
            self._mouse_movement_service.stop_monitoring()

        self._execution_state = ExecutionState.IDLE
        self._state.set(AppState.IDLE)
        self._state.set_current_macro(None)

        self.macro_completed.emit(macro_id)
        self._event_bus.macro_stopped.emit(macro_id)

        self._current_macro = None
    
    def _handle_error(self, error_message: str) -> None:
        """Handle an execution error.
        
        Args:
            error_message: Error message.
        """
        if self._current_macro is None:
            return
        
        self._logger.error(f"Macro error: {error_message}")
        
        macro_id = self._current_macro.id
        
        self._execution_state = ExecutionState.IDLE
        self._state.set_error(error_message)
        self._state.set_current_macro(None)
        
        self.macro_error.emit(macro_id, error_message)
        self._event_bus.macro_error.emit(macro_id, error_message)

        self._current_macro = None

    def _on_mouse_movement_exceeded(self, distance: float) -> None:
        """Handle mouse movement exceeded signal.

        Stops the current macro when mouse movement exceeds threshold.

        Args:
            distance: Distance moved in pixels.
        """
        if self._current_macro is None:
            return

        self._logger.info(
            f"Mouse movement exceeded threshold: {distance:.1f}px, "
            f"stopping macro: {self._current_macro.name}"
        )

        # Stop the macro
        self.stop_macro()

    def set_stop_on_mouse_movement(self, enabled: bool) -> None:
        """Enable or disable stop on mouse movement.

        Args:
            enabled: True to enable stop on mouse movement, False otherwise.
        """
        self._stop_on_mouse_movement = enabled

    def set_mouse_movement_threshold(self, threshold: int) -> None:
        """Set mouse movement threshold in pixels.

        Args:
            threshold: Movement threshold in pixels.
        """
        self._mouse_movement_threshold = threshold


# Global singleton instance
_macro_engine: Optional[MacroEngine] = None


def get_macro_engine() -> MacroEngine:
    """Get the global macro engine instance.
    
    Raises:
        RuntimeError: If engine not initialized.
    
    Returns:
        MacroEngine: The global engine instance.
    """
    if _macro_engine is None:
        raise RuntimeError(
            "Macro engine not initialized. "
            "Call init_macro_engine() first."
        )
    return _macro_engine


def init_macro_engine(
    randomization_engine: RandomizationEngine,
    state_manager: StateManager,
    stats_service: StatsService,
    mouse_movement_service: Optional['MouseMovementService'] = None
) -> MacroEngine:
    """Initialize the global macro engine.

    Args:
        randomization_engine: Randomization engine.
        state_manager: State manager.
        stats_service: Statistics tracking service.
        mouse_movement_service: Optional mouse movement service.

    Returns:
        MacroEngine: The newly created engine instance.

    Raises:
        RuntimeError: If engine already initialized.
        ValueError: If any argument is None.
    """
    global _macro_engine
    if _macro_engine is not None:
        raise RuntimeError("Macro engine already initialized.")
    _macro_engine = MacroEngine(
        randomization_engine, state_manager, stats_service, mouse_movement_service
    )
    return _macro_engine
