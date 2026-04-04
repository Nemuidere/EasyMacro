"""
EasyMacro Data Models.

This package contains Pydantic models for data validation at boundaries.
"""

from src.models.base import EasyMacroBaseModel, generate_id
from src.models.action import (
    ActionType,
    ClickAction,
    DelayAction,
    KeyPressAction,
    MouseMoveAction,
    Action,
    parse_action,
)
from src.models.macro import Macro, MacroStatus
from src.models.settings import AppSettings, RandomizationSettings, HotkeySettings, Theme

__all__ = [
    # Base
    "EasyMacroBaseModel",
    "generate_id",
    # Actions
    "ActionType",
    "ClickAction",
    "DelayAction",
    "KeyPressAction",
    "MouseMoveAction",
    "Action",
    "parse_action",
    # Macros
    "Macro",
    "MacroStatus",
    # Settings
    "AppSettings",
    "RandomizationSettings",
    "HotkeySettings",
    "Theme",
]
