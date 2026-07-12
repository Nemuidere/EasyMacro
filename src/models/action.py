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
    CLICK_HOLD = "click_hold"
    CLICK_RELEASE = "click_release"
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
        x: X coordinate (ignored if use_cursor_position is True).
        y: Y coordinate (ignored if use_cursor_position is True).
        button: Mouse button (left, right, middle).
        modifiers: Modifier keys to hold during click.
        jitter_radius: Randomization radius in pixels.
        use_cursor_position: If True, use current cursor position instead of x,y.
        delay_after_ms: Optional delay after this action completes, before the
            next step runs (0 = none).
        delay_after_variance_percent: Randomization variance for delay_after_ms.
    """

    action_type: ActionType = Field(default=ActionType.CLICK, frozen=True)
    x: int = Field(ge=0, description="X coordinate")
    y: int = Field(ge=0, description="Y coordinate")
    button: str = Field(default="left", description="Mouse button")
    modifiers: list[str] = Field(default_factory=list, description="Modifier keys to hold during click")
    jitter_radius: int = Field(default=2, ge=0, description="Randomization radius in pixels")
    use_cursor_position: bool = Field(default=False, description="Use current cursor position")
    delay_after_ms: int = Field(default=0, ge=0, description="Optional delay after this action completes")
    delay_after_variance_percent: int = Field(
        default=5, ge=0, le=100, description="Randomization variance for delay_after_ms"
    )

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
        default=5,
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
        delay_after_ms: Optional delay after this action completes, before the
            next step runs (0 = none).
        delay_after_variance_percent: Randomization variance for delay_after_ms.
    """

    action_type: ActionType = Field(default=ActionType.KEY_PRESS, frozen=True)
    key: str = Field(min_length=1, description="Key to press")
    modifiers: list[str] = Field(default_factory=list, description="Modifier keys")
    delay_after_ms: int = Field(default=0, ge=0, description="Optional delay after this action completes")
    delay_after_variance_percent: int = Field(
        default=5, ge=0, le=100, description="Randomization variance for delay_after_ms"
    )

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
        delay_after_ms: Optional delay after this action completes, before the
            next step runs (0 = none).
        delay_after_variance_percent: Randomization variance for delay_after_ms.
    """

    action_type: ActionType = Field(default=ActionType.MOUSE_MOVE, frozen=True)
    x: int = Field(ge=0, description="Target X coordinate")
    y: int = Field(ge=0, description="Target Y coordinate")
    smooth: bool = Field(default=True, description="Use smooth movement")
    speed: int = Field(default=5, ge=1, le=10, description="Movement speed (1-10)")
    delay_after_ms: int = Field(default=0, ge=0, description="Optional delay after this action completes")
    delay_after_variance_percent: int = Field(
        default=5, ge=0, le=100, description="Randomization variance for delay_after_ms"
    )


# Union type for all executable (leaf) actions
Action = ClickAction | DelayAction | KeyPressAction | MouseMoveAction


class LoopBlock(EasyMacroBaseModel):
    """A group of actions repeated a fixed number of times (a loop).

    Used to loop *parts* of a macro: e.g. repeat steps 1-6 ten times, then run
    the rest. Loop blocks sit alongside plain actions in a macro's item list and
    are expanded into a flat action sequence at run time. The whole macro is
    still wrapped by the macro-level ``repeat_count`` (the outer loop).

    Loop blocks can nest to any depth: a loop's own ``actions`` may themselves
    contain further ``LoopBlock``s (e.g. loop A x25, then loop [A, B] x10).

    Attributes:
        count: Number of times to repeat the block (>= 1).
        actions: The actions (and/or nested loop blocks) performed on each pass.
    """

    count: int = Field(default=1, ge=1, description="Times to repeat this block")
    actions: list["MacroItem"] = Field(
        default_factory=list, description="Actions and/or nested loop blocks in the loop"
    )


# An item in a macro body is either a leaf action or a loop block. Loop blocks
# can nest (see LoopBlock docstring), so this is a self-referencing type — the
# forward reference above is resolved by the model_rebuild() call below, once
# LoopBlock itself is fully defined.
MacroItem = ClickAction | DelayAction | KeyPressAction | MouseMoveAction | LoopBlock

LoopBlock.model_rebuild()


def flatten_items(items: list) -> list:
    """Expand loop blocks into a flat list of executable actions.

    Args:
        items: A list of Actions and/or LoopBlocks.

    Returns:
        A flat list of Actions with every LoopBlock unrolled ``count`` times.
    """
    flat: list = []
    for item in items:
        if isinstance(item, LoopBlock):
            inner = flatten_items(item.actions)
            for _ in range(item.count):
                flat.extend(inner)
        else:
            flat.append(item)
    return flat


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
        ActionType.CLICK_HOLD: ClickAction,
        ActionType.CLICK_RELEASE: ClickAction,
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
