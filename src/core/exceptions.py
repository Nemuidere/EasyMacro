"""
Custom exceptions for EasyMacro.

Provides a clear exception hierarchy for error handling throughout the application.
"""


class EasyMacroError(Exception):
    """Base exception for all EasyMacro errors."""
    pass


class ConfigError(EasyMacroError):
    """Configuration-related errors."""
    pass


class MacroError(EasyMacroError):
    """Macro execution errors."""
    pass


class MacroNotFoundError(MacroError):
    """Raised when a macro is not found."""
    pass


class MacroExecutionError(MacroError):
    """Raised when macro execution fails."""
    pass


class HotkeyError(EasyMacroError):
    """Hotkey-related errors."""
    pass


class HotkeyConflictError(HotkeyError):
    """Raised when a hotkey is already registered."""
    pass


class PluginError(EasyMacroError):
    """Plugin-related errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""
    pass


class ValidationError(EasyMacroError):
    """Input validation errors."""
    pass
