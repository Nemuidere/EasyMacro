"""
Event Bus - Central communication hub for EasyMacro.

Uses Qt signals for type-safe, thread-safe communication between components.
"""

from typing import Any, Callable
from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    Central event bus for application-wide communication.
    
    All events flow through this bus, enabling loose coupling between components.
    Components subscribe to events they care about and emit events when state changes.
    
    Usage:
        bus = EventBus()
        bus.macro_started.connect(lambda m: print(f"Started: {m}"))
        bus.macro_started.emit("my_macro")
    """
    
    # Macro events
    macro_started = Signal(str)  # macro_id
    macro_stopped = Signal(str)  # macro_id
    macro_paused = Signal(str)  # macro_id
    macro_error = Signal(str, str)  # macro_id, error_message
    
    # Hotkey events
    hotkey_registered = Signal(str)  # hotkey_id
    hotkey_unregistered = Signal(str)  # hotkey_id
    hotkey_triggered = Signal(str)  # hotkey_id
    
    # Plugin events
    plugin_loaded = Signal(str)  # plugin_name
    plugin_unloaded = Signal(str)  # plugin_name
    
    # Settings events
    settings_changed = Signal(str, object)  # key, value
    
    # Stats events
    stats_updated = Signal(str, int, float)  # macro_id, clicks, time_seconds
    stats_saved = Signal()  # emitted when stats are persisted
    position_captured = Signal(int, int)  # x, y coordinates
    position_capture_cancelled = Signal()  # when capture is cancelled
    
    # Application events
    app_ready = Signal()
    app_shutdown = Signal()
    
    def __init__(self):
        super().__init__()


# Global singleton instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.
    
    Raises:
        RuntimeError: If event bus not initialized.
    
    Returns:
        EventBus: The global event bus instance.
    """
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized. Call init_event_bus() first.")
    return _event_bus


def init_event_bus() -> EventBus:
    """Initialize the global event bus.
    
    Returns:
        EventBus: The newly created event bus instance.
    """
    global _event_bus
    
    if _event_bus is not None:
        raise RuntimeError("Event bus already initialized.")
    
    _event_bus = EventBus()
    return _event_bus
