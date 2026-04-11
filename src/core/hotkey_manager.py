"""
Hotkey manager for EasyMacro.

Handles global hotkey registration and detection using pynput.
"""

from typing import Optional, Callable, Dict
from pynput import keyboard
from pynput.keyboard import Key
from PySide6.QtCore import QObject, Signal

from src.core.exceptions import HotkeyError, HotkeyConflictError
from src.core.logger import get_logger


class HotkeyManager(QObject):
    """
    Manages global hotkey registration and detection.
    
    Uses pynput for system-wide hotkey detection. Hotkeys work
    even when the application is minimized or not focused.
    
    Signals:
        hotkey_pressed: Emitted when a registered hotkey is pressed (hotkey_id)
        hotkey_registered: Emitted when a hotkey is registered (hotkey_id)
        hotkey_unregistered: Emitted when a hotkey is unregistered (hotkey_id)
    
    Usage:
        manager = HotkeyManager()
        manager.register("ctrl+shift+a", "my_hotkey", callback)
        manager.start()
    """
    
    # Signals
    hotkey_pressed = Signal(str)  # hotkey_id
    hotkey_registered = Signal(str)  # hotkey_id
    hotkey_unregistered = Signal(str)  # hotkey_id
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize hotkey manager.
        
        Args:
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        
        self._logger = get_logger("hotkey_manager")
        self._hotkeys: Dict[str, Callable[[], None]] = {}  # hotkey_str -> callback
        self._hotkey_ids: Dict[str, str] = {}  # hotkey_str -> hotkey_id
        self._listener: Optional[keyboard.Listener] = None
        self._running = False
        
        # Track currently pressed modifier keys
        self._pressed_modifiers: set = set()  # Set of currently pressed modifier names
    
    def register(
        self,
        hotkey: str,
        hotkey_id: str,
        callback: Callable[[], None]
    ) -> None:
        """Register a hotkey.
        
        Args:
            hotkey: Hotkey string (e.g., "ctrl+shift+a").
            hotkey_id: Unique identifier for this hotkey.
            callback: Function to call when hotkey is pressed.
        
        Raises:
            ValueError: If hotkey is empty or callback is None.
            HotkeyConflictError: If hotkey is already registered.
        """
        if not hotkey:
            raise ValueError("Hotkey cannot be empty")
        if callback is None:
            raise ValueError("Callback cannot be None")
        
        hotkey = self._normalize_hotkey(hotkey)
        
        if hotkey in self._hotkeys:
            raise HotkeyConflictError(f"Hotkey already registered: {hotkey}")
        
        self._hotkeys[hotkey] = callback
        self._hotkey_ids[hotkey] = hotkey_id
        
        self._logger.info(f"Registered hotkey: {hotkey} (id: {hotkey_id})")
        self.hotkey_registered.emit(hotkey_id)
    
    def unregister(self, hotkey: str) -> None:
        """Unregister a hotkey.
        
        Args:
            hotkey: Hotkey string to unregister.
        
        Raises:
            ValueError: If hotkey is empty.
            HotkeyError: If hotkey is not registered.
        """
        if not hotkey:
            raise ValueError("Hotkey cannot be empty")
        
        hotkey = self._normalize_hotkey(hotkey)
        
        if hotkey not in self._hotkeys:
            raise HotkeyError(f"Hotkey not registered: {hotkey}")
        
        hotkey_id = self._hotkey_ids.pop(hotkey)
        del self._hotkeys[hotkey]
        
        self._logger.info(f"Unregistered hotkey: {hotkey} (id: {hotkey_id})")
        self.hotkey_unregistered.emit(hotkey_id)
    
    def unregister_all(self) -> None:
        """Unregister all hotkeys."""
        self._hotkeys.clear()
        self._hotkey_ids.clear()
        self._logger.info("Unregistered all hotkeys")
    
    def start(self) -> None:
        """Start listening for hotkeys.
        
        Raises:
            RuntimeError: If already running.
        """
        if self._running:
            raise RuntimeError("Hotkey manager is already running")
        
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._listener.start()
        self._running = True
        
        self._logger.info("Hotkey manager started")
    
    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if not self._running:
            return
        
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        self._pressed_modifiers.clear()
        self._running = False
        self._logger.info("Hotkey manager stopped")
    
    def is_running(self) -> bool:
        """Check if the manager is running.
        
        Returns:
            True if running, False otherwise.
        """
        return self._running
    
    def is_registered(self, hotkey: str) -> bool:
        """Check if a hotkey is registered.
        
        Args:
            hotkey: Hotkey string to check.
        
        Returns:
            True if registered, False otherwise.
        """
        hotkey = self._normalize_hotkey(hotkey)
        return hotkey in self._hotkeys
    
    def get_registered_hotkeys(self) -> list[str]:
        """Get all registered hotkeys.
        
        Returns:
            List of registered hotkey strings.
        """
        return list(self._hotkeys.keys())
    
    def _normalize_hotkey(self, hotkey: str) -> str:
        """Normalize a hotkey string.
        
        Converts to lowercase and sorts modifiers.
        
        Args:
            hotkey: Hotkey string to normalize.
        
        Returns:
            Normalized hotkey string.
        """
        parts = [p.strip().lower() for p in hotkey.split("+")]
        
        # Separate modifiers and key
        modifiers = []
        key = None
        
        modifier_set = {"ctrl", "alt", "shift", "meta", "cmd", "win"}
        
        for part in parts:
            if part in modifier_set:
                # Normalize modifier names
                if part in ("cmd", "win"):
                    modifiers.append("meta")
                else:
                    modifiers.append(part)
            else:
                key = part
        
        if key is None:
            raise ValueError(f"Invalid hotkey format: {hotkey}")
        
        # Sort modifiers for consistent representation
        modifiers.sort()
        
        if modifiers:
            return "+".join(modifiers + [key])
        return key
    
    def _on_key_press(self, key) -> None:
        """Handle key press events.
        
        Args:
            key: Key that was pressed.
        """
        # Track modifier keys
        key_name = self._get_key_name(key)
        if key_name in ("ctrl", "alt", "shift", "meta"):
            self._pressed_modifiers.add(key_name)
            return  # Don't trigger hotkey on modifier press alone
        
        # Build hotkey string from current modifiers + key
        current_hotkey = self._build_hotkey_string(key)
        
        if current_hotkey and current_hotkey in self._hotkeys:
            self._logger.debug(f"Hotkey pressed: {current_hotkey}")
            callback = self._hotkeys[current_hotkey]
            callback()
            
            hotkey_id = self._hotkey_ids.get(current_hotkey)
            if hotkey_id:
                self.hotkey_pressed.emit(hotkey_id)
    
    def _on_key_release(self, key) -> None:
        """Handle key release events.
        
        Args:
            key: Key that was released.
        """
        key_name = self._get_key_name(key)
        if key_name in ("ctrl", "alt", "shift", "meta"):
            self._pressed_modifiers.discard(key_name)
    
    def _get_key_name(self, key) -> Optional[str]:
        """Extract key name from pynput key object.
        
        Args:
            key: pynput keyboard key object.
        
        Returns:
            Key name string or None if cannot be determined.
        """
        if isinstance(key, Key):
            name = key.name.lower()
            # Normalize modifier names
            if name in ("cmd", "win", "command"):
                return "meta"
            return name
        
        try:
            # Handle character keys
            char = key.char
            if char:
                return char.lower()
        except AttributeError:
            pass
        
        return None
    
    def _build_hotkey_string(self, key) -> Optional[str]:
        """Build a hotkey string from the current keyboard state.
        
        Args:
            key: The key that was pressed.
        
        Returns:
            Hotkey string or None if not a valid hotkey.
        """
        key_name = self._get_key_name(key)
        if not key_name:
            return None
        
        # Don't include modifiers as the main key
        if key_name in ("ctrl", "alt", "shift", "meta"):
            return None
        
        # Build hotkey string with modifiers
        modifiers = sorted(self._pressed_modifiers)  # Sort for consistent order
        if modifiers:
            return "+".join(modifiers + [key_name])
        return key_name


# Global singleton instance
_hotkey_manager: Optional[HotkeyManager] = None


def get_hotkey_manager() -> HotkeyManager:
    """Get the global hotkey manager instance.
    
    Raises:
        RuntimeError: If manager not initialized.
    
    Returns:
        HotkeyManager: The global manager instance.
    """
    if _hotkey_manager is None:
        raise RuntimeError(
            "Hotkey manager not initialized. "
            "Call init_hotkey_manager() first."
        )
    return _hotkey_manager


def init_hotkey_manager() -> HotkeyManager:
    """Initialize the global hotkey manager.
    
    Returns:
        HotkeyManager: The newly created manager instance.
    
    Raises:
        RuntimeError: If manager already initialized.
    """
    global _hotkey_manager
    if _hotkey_manager is not None:
        raise RuntimeError("Hotkey manager already initialized.")
    _hotkey_manager = HotkeyManager()
    return _hotkey_manager
