"""
Settings models for EasyMacro.

Defines application settings and user preferences.
"""

from enum import Enum
from typing import Optional
from pathlib import Path
from pydantic import Field, field_validator

from src.models.base import EasyMacroBaseModel


class Theme(str, Enum):
    """Application theme."""
    
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


class RandomizationSettings(EasyMacroBaseModel):
    """Settings for randomization behavior.
    
    Attributes:
        enabled: Whether randomization is enabled.
        jitter_radius: Maximum pixel offset for clicks.
        timing_variance_percent: Percentage variance for delays.
        mouse_speed_variation: Variation in mouse movement speed.
    """
    
    enabled: bool = Field(default=True, description="Enable randomization")
    jitter_radius: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Maximum pixel offset for clicks"
    )
    timing_variance_percent: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Percentage variance for delays"
    )
    mouse_speed_variation: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Variation in mouse movement speed"
    )


class HotkeySettings(EasyMacroBaseModel):
    """Settings for hotkey bindings.
    
    Attributes:
        pause_all: Hotkey to pause all macros.
        resume_all: Hotkey to resume all macros.
        stop_all: Hotkey to stop all macros.
    """
    
    pause_all: str = Field(default="ctrl+shift+p", description="Pause all macros")
    resume_all: str = Field(default="ctrl+shift+r", description="Resume all macros")
    stop_all: str = Field(default="ctrl+shift+s", description="Stop all macros")


class AppSettings(EasyMacroBaseModel):
    """Application settings.
    
    Attributes:
        theme: UI theme preference.
        randomization: Randomization settings.
        hotkeys: Hotkey bindings.
        start_minimized: Start app minimized to tray.
        close_to_tray: Close to system tray instead of quitting.
        check_updates: Check for updates on startup.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        config_version: Configuration schema version.
    """
    
    theme: Theme = Field(default=Theme.DARK, description="UI theme")
    randomization: RandomizationSettings = Field(
        default_factory=RandomizationSettings,
        description="Randomization settings"
    )
    hotkeys: HotkeySettings = Field(
        default_factory=HotkeySettings,
        description="Hotkey bindings"
    )
    start_minimized: bool = Field(default=False, description="Start minimized to tray")
    close_to_tray: bool = Field(default=True, description="Close to system tray")
    check_updates: bool = Field(default=True, description="Check for updates on startup")
    log_level: str = Field(default="INFO", description="Logging level")
    config_version: int = Field(default=1, description="Configuration schema version")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.
        
        Args:
            v: Log level to validate.
        
        Returns:
            Validated log level (uppercase).
        
        Raises:
            ValueError: If log level is invalid.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}, got {v}")
        return v_upper
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation.
        """
        return self.model_dump()
