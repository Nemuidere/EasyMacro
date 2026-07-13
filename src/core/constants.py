"""
Application constants for EasyMacro.

Defines global constants used throughout the application.
"""

import sys
from pathlib import Path


def get_data_dir() -> Path:
    """Return the canonical ``data`` directory for the app.

    Resolves to an absolute path so every component reads/writes the *same*
    files regardless of the current working directory. When frozen (PyInstaller)
    the data dir sits next to the executable; otherwise it is ``<repo>/data``.

    Returns:
        Absolute path to the data directory.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        # This file is <repo>/src/core/constants.py → three parents reach <repo>.
        base = Path(__file__).resolve().parent.parent.parent
    return base / "data"


def get_config_path() -> Path:
    """Absolute path to the config file (see :func:`get_data_dir`)."""
    return get_data_dir() / "config.json"


def get_macros_path() -> Path:
    """Absolute path to the macros file (see :func:`get_data_dir`)."""
    return get_data_dir() / "macros.json"


def get_assets_dir() -> Path:
    """Absolute path to the reference-image assets dir (see :func:`get_data_dir`)."""
    return get_data_dir() / "assets"


def get_stats_path() -> Path:
    """Absolute path to the stats file (see :func:`get_data_dir`)."""
    return get_data_dir() / "stats.json"


def get_log_path() -> Path:
    """Absolute path to the log file (see :func:`get_data_dir`)."""
    return get_data_dir() / "logs" / "easymacro.log"


def get_resource_dir() -> Path:
    """Return the absolute ``resources`` directory (CWD-independent)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "resources"


def get_style_path(name: str = "dark_theme.qss") -> Path:
    """Absolute path to a stylesheet under ``resources/styles``."""
    return get_resource_dir() / "styles" / name


# Application metadata
APP_NAME = "EasyMacro"
APP_VERSION = "0.1.0"
APP_AUTHOR = "EasyMacro Team"

# Default paths (absolute, CWD-independent). Kept as module-level constants for
# backwards compatibility; prefer the get_*_path() helpers in new code.
DEFAULT_CONFIG_PATH = get_config_path()
DEFAULT_MACROS_PATH = get_macros_path()
DEFAULT_LOG_PATH = get_log_path()
DEFAULT_STATS_PATH = get_stats_path()

# Default settings
DEFAULT_JITTER_RADIUS = 2  # pixels
DEFAULT_TIMING_VARIANCE = 5  # percent
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

# Modifier key order for press/release
MODIFIER_KEY_DOWN_ORDER = ["ctrl", "alt", "shift"]
MODIFIER_KEY_UP_ORDER = ["shift", "alt", "ctrl"]  # Reverse order
