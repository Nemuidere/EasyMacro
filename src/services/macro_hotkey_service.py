"""
Macro hotkey service for EasyMacro.

Registers macro hotkeys with the HotkeyManager and executes macros on hotkey press.
"""

from typing import Optional, Dict, Callable
from PySide6.QtCore import QObject, Signal

from src.core.hotkey_manager import HotkeyManager, get_hotkey_manager
from src.core.event_bus import EventBus, get_event_bus
from src.core.logger import get_logger
from src.services.macro_service import MacroService, get_macro_service
from src.models.macro import Macro


class MacroHotkeyService(QObject):
    """
    Manages macro hotkey registration and execution.
    
    Registers macro hotkeys with the HotkeyManager and executes
    macros when their hotkeys are pressed.
    
    Signals:
        macro_triggered: Emitted when a macro is triggered by hotkey (macro_id)
    """
    
    macro_triggered = Signal(str)  # macro_id
    
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
        
        self._logger.info("MacroHotkeyService initialized")
    
    def register_macro_hotkey(self, macro: Macro, callback: Callable[[], None]) -> None:
        """Register a macro's hotkey with the HotkeyManager.
        
        Args:
            macro: Macro to register.
            callback: Function to call when hotkey is pressed.
        
        Raises:
            ValueError: If macro has no hotkey.
        """
        if not macro.hotkey:
            self._logger.warning(f"Macro {macro.id} has no hotkey, skipping registration")
            return
        
        if not self._hotkey_manager:
            self._logger.error("HotkeyManager not initialized")
            return
        
        hotkey_id = f"macro_{macro.id}"
        
        try:
            # Unregister existing hotkey if any
            if macro.id in self._registered_hotkeys.values():
                self.unregister_macro_hotkey(macro.id)
            
            # Register new hotkey
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
        """Register hotkeys for all macros that have them."""
        if not self._macro_service:
            self._logger.error("MacroService not initialized")
            return
        
        try:
            macros = self._macro_service.get_all()
            
            for macro in macros:
                if macro.hotkey and macro.enabled:
                    # Create callback for this macro
                    def make_callback(m: Macro) -> Callable[[], None]:
                        def callback():
                            self._on_macro_hotkey_pressed(m.id)
                        return callback
                    
                    self.register_macro_hotkey(macro, make_callback(macro))
            
            self._logger.info(f"Registered hotkeys for {len(self._registered_hotkeys)} macros")
            
        except Exception as e:
            self._logger.error(f"Failed to register macro hotkeys: {e}")
    
    def _on_macro_hotkey_pressed(self, macro_id: str) -> None:
        """Handle macro hotkey press.
        
        Args:
            macro_id: ID of macro to execute.
        """
        self._logger.info(f"Macro hotkey pressed: {macro_id}")
        
        # Emit signal for UI to handle
        self.macro_triggered.emit(macro_id)
        
        # Also emit via EventBus
        if self._event_bus:
            self._event_bus.macro_started.emit(macro_id)


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
