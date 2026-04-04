"""
Application constants for EasyMacro.

Defines global constants used throughout the application.
"""

from pathlib import Path

# Application metadata
APP_NAME = "EasyMacro"
APP_VERSION = "0.1.0"
APP_AUTHOR = "EasyMacro Team"

# Default paths
DEFAULT_CONFIG_PATH = Path("data/config.json")
DEFAULT_MACROS_PATH = Path("data/macros.json")
DEFAULT_LOG_PATH = Path("data/logs/easymacro.log")

# Default settings
DEFAULT_JITTER_RADIUS = 5  # pixels
DEFAULT_TIMING_VARIANCE = 20  # percent
DEFAULT_THEME = "dark"

# State transitions
VALID_STATE_TRANSITIONS = {
    "idle": ["running"],
    "running": ["paused", "idle", "error"],
    "paused": ["running", "idle"],
    "error": ["idle"],
}

# Hotkey modifiers
HOTKEY_MODIFIERS = ["ctrl", "alt", "shift", "meta"]

# Mouse buttons
MOUSE_BUTTONS = ["left", "right", "middle"]

# Action types
ACTION_TYPES = ["click", "right_click", "double_click", "delay", "mouse_move", "key_press"]
