"""
Action models for EasyMacro.

Defines the different types of actions a macro can perform.
"""

from enum import Enum
from typing import Optional
from pydantic import Field, field_validator

from src.models.base import EasyMacroBaseModel


class ActionType(str, Enum):
    """Types of actions a macro can perform."""
    
    CLICK = "click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    DELAY = "delay"
    MOUSE_MOVE = "mouse_move"
    KEY_PRESS = "key_press"
    KEY_HOLD = "key_hold"
    KEY_RELEASE = "key_release"
    SCROLL = "scroll"


class ClickAction(EasyMacroBaseModel):
    """Action for mouse clicks.
    
    Attributes:
        action_type: Always ActionType.CLICK.
        x: X coordinate.
        y: Y coordinate.
        button: Mouse button (left, right, middle).
        modifiers: Modifier keys to hold during click.
        jitter_radius: Randomization radius in pixels.
    """
    
    action_type: ActionType = Field(default=ActionType.CLICK, frozen=True)
    x: int = Field(ge=0, description="X coordinate")
    y: int = Field(ge=0, description="Y coordinate")
    button: str = Field(default="left", description="Mouse button")
    modifiers: list[str] = Field(default_factory=list, description="Modifier keys to hold during click")
    jitter_radius: int = Field(default=5, ge=0, description="Randomization radius in pixels")
    
    @field_validator("button")
    @classmethod
    def validate_button(cls, v: str) -> str:
        """Validate mouse button.
        
        Args:
            v: Button value to validate.
        
        Returns:
            Validated button value.
        
        Raises:
            ValueError: If button is invalid.
        """
        valid_buttons = {"left", "right", "middle"}
        if v.lower() not in valid_buttons:
            raise ValueError(f"Button must be one of {valid_buttons}, got {v}")
        return v.lower()
    
    @field_validator("modifiers")
    @classmethod
    def validate_modifiers(cls, v: list[str]) -> list[str]:
        """Validate modifier keys.
        
        Args:
            v: Modifiers list to validate.
        
        Returns:
            Validated modifiers list.
        
        Raises:
            ValueError: If any modifier is invalid.
        """
        valid_modifiers = {"ctrl", "alt", "shift"}
        for mod in v:
            if mod.lower() not in valid_modifiers:
                raise ValueError(f"Modifier must be one of {valid_modifiers}, got {mod}")
        return [m.lower() for m in v]


class DelayAction(EasyMacroBaseModel):
    """Action for delays.
    
    Attributes:
        action_type: Always ActionType.DELAY.
        duration_ms: Duration in milliseconds.
        variance_percent: Randomization variance percentage.
    """
    
    action_type: ActionType = Field(default=ActionType.DELAY, frozen=True)
    duration_ms: int = Field(ge=0, description="Duration in milliseconds")
    variance_percent: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Randomization variance percentage"
    )


class KeyPressAction(EasyMacroBaseModel):
    """Action for key presses.
    
    Attributes:
        action_type: Always ActionType.KEY_PRESS.
        key: Key to press.
        modifiers: Modifier keys (ctrl, alt, shift).
    """
    
    action_type: ActionType = Field(default=ActionType.KEY_PRESS, frozen=True)
    key: str = Field(min_length=1, description="Key to press")
    modifiers: list[str] = Field(default_factory=list, description="Modifier keys")
    
    @field_validator("modifiers")
    @classmethod
    def validate_modifiers(cls, v: list[str]) -> list[str]:
        """Validate modifier keys.
        
        Args:
            v: Modifiers list to validate.
        
        Returns:
            Validated modifiers list.
        
        Raises:
            ValueError: If any modifier is invalid.
        """
        valid_modifiers = {"ctrl", "alt", "shift", "meta"}
        for mod in v:
            if mod.lower() not in valid_modifiers:
                raise ValueError(f"Modifier must be one of {valid_modifiers}, got {mod}")
        return [m.lower() for m in v]


class MouseMoveAction(EasyMacroBaseModel):
    """Action for mouse movement.
    
    Attributes:
        action_type: Always ActionType.MOUSE_MOVE.
        x: Target X coordinate.
        y: Target Y coordinate.
        smooth: Whether to use smooth movement.
        speed: Movement speed (1-10).
    """
    
    action_type: ActionType = Field(default=ActionType.MOUSE_MOVE, frozen=True)
    x: int = Field(ge=0, description="Target X coordinate")
    y: int = Field(ge=0, description="Target Y coordinate")
    smooth: bool = Field(default=True, description="Use smooth movement")
    speed: int = Field(default=5, ge=1, le=10, description="Movement speed (1-10)")


# Union type for all actions
Action = ClickAction | DelayAction | KeyPressAction | MouseMoveAction


def parse_action(data: dict) -> Action:
    """Parse action data into the correct action type.
    
    Args:
        data: Dictionary containing action data.
    
    Returns:
        Appropriate action model instance.
    
    Raises:
        ValueError: If action type is unknown.
    """
    if "action_type" not in data:
        raise ValueError("Action data must contain 'action_type'")
    
    action_type = data["action_type"]
    
    action_map = {
        ActionType.CLICK: ClickAction,
        ActionType.RIGHT_CLICK: ClickAction,
        ActionType.DOUBLE_CLICK: ClickAction,
        ActionType.DELAY: DelayAction,
        ActionType.KEY_PRESS: KeyPressAction,
        ActionType.KEY_HOLD: KeyPressAction,
        ActionType.KEY_RELEASE: KeyPressAction,
        ActionType.MOUSE_MOVE: MouseMoveAction,
        ActionType.SCROLL: ClickAction,
    }
    
    if action_type not in action_map:
        raise ValueError(f"Unknown action type: {action_type}")
    
    return action_map[action_type].model_validate(data)
