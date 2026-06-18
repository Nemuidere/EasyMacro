"""
Macro hotkey service for EasyMacro.

Registers macro hotkeys with the HotkeyManager and executes macros on hotkey press.
"""

from typing import Optional, Dict, Callable
from PySide6.QtCore import QObject, Signal, Qt

from src.core.hotkey_manager import HotkeyManager, get_hotkey_manager
from src.core.event_bus import EventBus, get_event_bus
from src.core.exceptions import MacroNotFoundError
from src.core.logger import get_logger
from src.services.macro_service import MacroService, get_macro_service
from src.models.macro import Macro
from src.models.settings import HotkeySettings


class MacroHotkeyService(QObject):
    """
    Manages macro hotkey registration and execution.
    
    Registers macro hotkeys with the HotkeyManager and executes
    macros when their hotkeys are pressed.
    
    Hotkey callbacks fire on the pynput listener's background thread. To touch
    the macro engine and Qt objects safely, those callbacks only emit the
    internal ``_macro_fired`` / ``_control_fired`` signals; the matching slots
    run on the main (GUI) thread via queued connections.

    Signals:
        macro_triggered: Emitted when a macro is triggered by hotkey (macro_id)
    """

    macro_triggered = Signal(str)  # macro_id

    # Internal signals emitted from the pynput thread and handled on the main
    # thread (queued connection). Keeps all engine access on the GUI thread.
    _macro_fired = Signal(str)    # macro_id
    _control_fired = Signal(str)  # "stop" | "pause" | "resume"

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize macro hotkey service.
        
        Args:
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        
        self._logger = get_logger("macro_hotkey_service")
        self._hotkey_manager: Optional[HotkeyManager] = None
        self._macro_service: Optional[MacroService] = None
        self._event_bus: Optional[EventBus] = None
        self._registered_hotkeys: Dict[str, str] = {}  # hotkey_id -> macro_id
        self._macro_callbacks: Dict[str, Callable[[], None]] = {}  # macro_id -> callback
        
    def initialize(
        self,
        hotkey_manager: HotkeyManager,
        macro_service: MacroService,
        event_bus: EventBus
    ) -> None:
        """Initialize the service with required dependencies.
        
        Args:
            hotkey_manager: Global hotkey manager.
            macro_service: Macro persistence service.
            event_bus: Application event bus.
        """
        self._hotkey_manager = hotkey_manager
        self._macro_service = macro_service
        self._event_bus = event_bus

        # Marshal background-thread hotkey events onto the main thread. The
        # QueuedConnection guarantees the slots run in the GUI thread's event
        # loop regardless of which thread emitted the signal.
        self._macro_fired.connect(self._handle_macro_fired, Qt.QueuedConnection)
        self._control_fired.connect(self._handle_control_fired, Qt.QueuedConnection)

        self._logger.info("MacroHotkeyService initialized")
    
    def register_macro(self, macro: Macro) -> None:
        """Register a macro's hotkey with the HotkeyManager.

        The registered callback only marshals the trigger onto the main thread;
        the actual start/stop decision happens in ``_handle_macro_fired``.

        Args:
            macro: Macro to register.
        """
        if not macro.hotkey:
            self._logger.warning(f"Macro {macro.id} has no hotkey, skipping registration")
            return

        if not self._hotkey_manager:
            self._logger.error("HotkeyManager not initialized")
            return

        hotkey_id = f"macro_{macro.id}"
        callback = self._make_macro_callback(macro.id)

        try:
            # Unregister existing hotkey if any
            if macro.id in self._registered_hotkeys.values():
                self.unregister_macro_hotkey(macro.id)

            self._hotkey_manager.register(
                hotkey=macro.hotkey,
                hotkey_id=hotkey_id,
                callback=callback
            )

            self._registered_hotkeys[hotkey_id] = macro.id
            self._macro_callbacks[macro.id] = callback

            self._logger.info(f"Registered hotkey '{macro.hotkey}' for macro '{macro.name}'")

        except Exception as e:
            self._logger.error(f"Failed to register hotkey for macro {macro.id}: {e}")

    def _make_macro_callback(self, macro_id: str) -> Callable[[], None]:
        """Build a hotkey callback that marshals to the main thread.

        Args:
            macro_id: ID of the macro the hotkey controls.

        Returns:
            A zero-argument callable safe to invoke from the pynput thread.
        """
        def callback() -> None:
            self._macro_fired.emit(macro_id)
        return callback

    def unregister_macro_hotkey(self, macro_id: str) -> None:
        """Unregister a macro's hotkey.
        
        Args:
            macro_id: ID of macro to unregister.
        """
        if not self._hotkey_manager:
            return
        
        # Find hotkey_id for this macro
        hotkey_id = None
        for hid, mid in self._registered_hotkeys.items():
            if mid == macro_id:
                hotkey_id = hid
                break
        
        if not hotkey_id:
            return
        
        try:
            # Get hotkey string from manager
            for hotkey in self._hotkey_manager.get_registered_hotkeys():
                if self._hotkey_manager._hotkey_ids.get(hotkey) == hotkey_id:
                    self._hotkey_manager.unregister(hotkey)
                    break
            
            del self._registered_hotkeys[hotkey_id]
            if macro_id in self._macro_callbacks:
                del self._macro_callbacks[macro_id]
            
            self._logger.info(f"Unregistered hotkey for macro {macro_id}")
            
        except Exception as e:
            self._logger.error(f"Failed to unregister hotkey for macro {macro_id}: {e}")
    
    def register_all_macros(self) -> None:
        """Register hotkeys for all enabled macros that have them."""
        if not self._macro_service:
            self._logger.error("MacroService not initialized")
            return

        try:
            for macro in self._macro_service.get_all():
                if macro.hotkey and macro.enabled:
                    self.register_macro(macro)

            self._logger.info(f"Registered hotkeys for {len(self._registered_hotkeys)} macros")

        except Exception as e:
            self._logger.error(f"Failed to register macro hotkeys: {e}")

    def register_global_hotkeys(self, hotkeys: HotkeySettings) -> None:
        """Register the global stop/pause/resume hotkeys with the engine.

        Args:
            hotkeys: Hotkey settings holding the global bindings.
        """
        if not self._hotkey_manager:
            self._logger.error("HotkeyManager not initialized")
            return

        bindings = [
            (hotkeys.stop_all, "stop"),
            (hotkeys.pause_all, "pause"),
            (hotkeys.resume_all, "resume"),
        ]

        for hotkey, kind in bindings:
            if not hotkey:
                continue
            try:
                self._hotkey_manager.register(
                    hotkey=hotkey,
                    hotkey_id=f"global_{kind}",
                    callback=self._make_control_callback(kind),
                )
                self._logger.info(f"Registered global '{kind}' hotkey: {hotkey}")
            except Exception as e:
                # Most likely a conflict with a macro hotkey; log and continue.
                self._logger.error(f"Failed to register global '{kind}' hotkey '{hotkey}': {e}")

    def _make_control_callback(self, kind: str) -> Callable[[], None]:
        """Build a global-control callback that marshals to the main thread.

        Args:
            kind: One of "stop", "pause", "resume".

        Returns:
            A zero-argument callable safe to invoke from the pynput thread.
        """
        def callback() -> None:
            self._control_fired.emit(kind)
        return callback

    def _handle_macro_fired(self, macro_id: str) -> None:
        """Start or stop a macro in response to its hotkey (main thread).

        Pressing a macro's hotkey toggles it: if that macro is currently
        running (or paused) it is stopped; otherwise it is started. Pressing a
        different macro's hotkey stops the current run and starts the new one.

        Args:
            macro_id: ID of the macro whose hotkey was pressed.
        """
        self._logger.info(f"Macro hotkey pressed: {macro_id}")

        if not self._macro_service:
            self._logger.error("MacroService not initialized")
            return

        try:
            macro = self._macro_service.get(macro_id)
        except MacroNotFoundError:
            self._logger.error(f"Macro not found: {macro_id}")
            return

        if not macro.enabled:
            self._logger.warning(f"Macro {macro.name} is disabled, skipping execution")
            return

        from src.core.macro_engine import get_macro_engine
        try:
            engine = get_macro_engine()
        except RuntimeError as e:
            self._logger.error(f"Failed to get MacroEngine: {e}")
            return

        # Toggle: if a macro is already active, stop it first. If it was this
        # same macro, treat the press as "stop" and don't restart.
        if engine.is_running() or engine.is_paused():
            current = engine.get_current_macro()
            engine.stop_macro()
            if current is not None and current.id == macro_id:
                self._logger.info(f"Toggled macro off: {macro.name}")
                return

        try:
            engine.run_macro(macro)
            self._logger.info(f"Started macro: {macro.name}")
            # run_macro already emits EventBus.macro_started; only notify the
            # service-level signal here to avoid a duplicate event.
            self.macro_triggered.emit(macro_id)
        except Exception as e:
            self._logger.error(f"Failed to execute macro {macro_id}: {e}")

    def _handle_control_fired(self, kind: str) -> None:
        """Apply a global stop/pause/resume control on the engine (main thread).

        Args:
            kind: One of "stop", "pause", "resume".
        """
        from src.core.macro_engine import get_macro_engine
        try:
            engine = get_macro_engine()
        except RuntimeError as e:
            self._logger.error(f"Failed to get MacroEngine: {e}")
            return

        try:
            if kind == "stop":
                engine.stop_macro()
            elif kind == "pause":
                if engine.is_running():
                    engine.pause_macro()
            elif kind == "resume":
                if engine.is_paused():
                    engine.resume_macro()
            self._logger.info(f"Applied global control: {kind}")
        except Exception as e:
            self._logger.error(f"Failed to apply global control '{kind}': {e}")


# Global singleton
_macro_hotkey_service: Optional[MacroHotkeyService] = None


def get_macro_hotkey_service() -> MacroHotkeyService:
    """Get the global macro hotkey service instance.
    
    Raises:
        RuntimeError: If service not initialized.
    
    Returns:
        MacroHotkeyService: The global instance.
    """
    if _macro_hotkey_service is None:
        raise RuntimeError(
            "MacroHotkeyService not initialized. "
            "Call init_macro_hotkey_service() first."
        )
    return _macro_hotkey_service


def init_macro_hotkey_service() -> MacroHotkeyService:
    """Initialize the global macro hotkey service.
    
    Returns:
        MacroHotkeyService: The newly created instance.
    
    Raises:
        RuntimeError: If service already initialized.
    """
    global _macro_hotkey_service
    if _macro_hotkey_service is not None:
        raise RuntimeError("MacroHotkeyService already initialized.")
    _macro_hotkey_service = MacroHotkeyService()
    return _macro_hotkey_service
