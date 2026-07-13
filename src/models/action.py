"""
Action models for EasyMacro.

Defines the different types of actions a macro can perform.
"""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    WAIT_FOR_IMAGE = "wait_for_image"


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


class ImageCondition(BaseModel):
    """A screen condition: "this reference image appears inside this region".

    Embedded value object used by IfBlock/WhileBlock/WaitAction — not itself a
    macro item. The reference image is a screenshot the user captured in the
    builder, stored as a PNG under the assets dir (see
    ``src.core.constants.get_assets_dir``); only the filename is persisted.

    Coordinates are screen-absolute and may be negative (a monitor left of or
    above the primary one has negative screen coords).

    Attributes:
        image_file: Reference image filename inside the assets dir.
        x1: Region left edge (screen-absolute).
        y1: Region top edge.
        x2: Region right edge.
        y2: Region bottom edge.
        color_variation: Per-channel color tolerance (0-255) when matching pixels.
        negate: If True the condition means "image NOT found".
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    image_file: str = Field(min_length=1, description="Reference image filename in the assets dir")
    x1: int = Field(description="Region left edge (screen-absolute)")
    y1: int = Field(description="Region top edge (screen-absolute)")
    x2: int = Field(description="Region right edge (screen-absolute)")
    y2: int = Field(description="Region bottom edge (screen-absolute)")
    color_variation: int = Field(default=20, ge=0, le=255, description="Per-channel color tolerance")
    negate: bool = Field(default=False, description="True = condition is 'image NOT found'")

    @model_validator(mode="after")
    def _normalize_rect(self) -> "ImageCondition":
        """Normalize swapped corners and reject a zero-area region."""
        if self.x1 == self.x2 or self.y1 == self.y2:
            raise ValueError("Condition region must have a non-zero area")
        # Bypass validate_assignment (each assignment would re-run this
        # validator on a half-swapped rect).
        if self.x1 > self.x2:
            x1, x2 = self.x2, self.x1
            object.__setattr__(self, "x1", x1)
            object.__setattr__(self, "x2", x2)
        if self.y1 > self.y2:
            y1, y2 = self.y2, self.y1
            object.__setattr__(self, "y1", y1)
            object.__setattr__(self, "y2", y2)
        return self


class WaitAction(EasyMacroBaseModel):
    """Action that pauses the macro until a screen condition is met.

    Polls the condition every ``poll_interval_ms`` without blocking the UI.
    "Wait until the image appears" is a plain condition; "wait until it
    disappears" is the same condition with ``negate=True``.

    Note: the timeout clock keeps running while the macro is paused.

    Attributes:
        action_type: Always ActionType.WAIT_FOR_IMAGE.
        condition: The screen condition to wait for.
        poll_interval_ms: Delay between condition checks.
        timeout_ms: Give up after this long (0 = wait forever).
        on_timeout: What to do on timeout: continue the macro or stop with an error.
    """

    action_type: ActionType = Field(default=ActionType.WAIT_FOR_IMAGE, frozen=True)
    condition: ImageCondition
    poll_interval_ms: int = Field(default=200, ge=20, description="Delay between condition checks")
    timeout_ms: int = Field(default=0, ge=0, description="Give up after this long (0 = forever)")
    on_timeout: Literal["continue", "error"] = Field(
        default="error", description="On timeout: continue the macro or stop with an error"
    )


# Union type for all executable (leaf) actions
Action = ClickAction | DelayAction | KeyPressAction | MouseMoveAction | WaitAction


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


class IfBlock(EasyMacroBaseModel):
    """A conditional branch: run one body if a screen condition holds, else another.

    The condition is evaluated once when execution reaches the block. Both
    bodies may nest further blocks to any depth; an empty ``else_actions`` is
    simply a no-op when the condition is false.

    Attributes:
        condition: The screen condition deciding which branch runs.
        then_actions: Steps run when the condition is true.
        else_actions: Steps run when the condition is false.
    """

    condition: ImageCondition
    then_actions: list["MacroItem"] = Field(
        default_factory=list, description="Steps run when the condition is true"
    )
    else_actions: list["MacroItem"] = Field(
        default_factory=list, description="Steps run when the condition is false"
    )


class WhileBlock(EasyMacroBaseModel):
    """A loop that repeats its body while a screen condition holds.

    The condition is re-evaluated before every pass, with at least
    ``check_interval_ms`` between re-checks so a fast/empty body can't hammer
    the screen search. Optional caps guard against a condition that never
    turns false; the global stop hotkey always works regardless.

    Note: the timeout clock keeps running while the macro is paused.

    Attributes:
        condition: The screen condition checked before each pass.
        actions: The loop body.
        timeout_seconds: Give up after this long (0 = unlimited).
        max_iterations: Stop after this many passes (0 = unlimited).
        check_interval_ms: Minimum delay between condition re-checks.
    """

    condition: ImageCondition
    actions: list["MacroItem"] = Field(default_factory=list, description="The loop body")
    timeout_seconds: int = Field(default=0, ge=0, description="Give up after this long (0 = unlimited)")
    max_iterations: int = Field(default=0, ge=0, description="Stop after this many passes (0 = unlimited)")
    check_interval_ms: int = Field(default=100, ge=0, description="Minimum delay between condition re-checks")


# An item in a macro body is either a leaf action or a container block (loop /
# if / while). Containers can nest (see LoopBlock docstring), so these are
# self-referencing types — the forward references above are resolved by the
# model_rebuild() calls below, once MacroItem itself is fully defined.
#
# Discrimination on load relies on extra="forbid" plus full model_dump()s:
# each model's dump always carries a key the others forbid (action_type for
# leaves, count for LoopBlock, then_actions/else_actions for IfBlock,
# condition+actions for WhileBlock). Never switch persistence to
# exclude_defaults, and always include a distinguishing key in hand-written
# dicts (a bare {"condition": ...} is ambiguous between If/While/Wait).
MacroItem = (
    ClickAction
    | DelayAction
    | KeyPressAction
    | MouseMoveAction
    | WaitAction
    | LoopBlock
    | IfBlock
    | WhileBlock
)

LoopBlock.model_rebuild()
IfBlock.model_rebuild()
WhileBlock.model_rebuild()


def is_container(item) -> bool:
    """Return True if the item is a block that contains other macro items."""
    return isinstance(item, (LoopBlock, IfBlock, WhileBlock))


def child_lists(item) -> list[tuple[str, list]]:
    """The child item lists of a container, as (label, list) pairs.

    Returns an empty list for leaf actions. This is the single place that
    knows which blocks have which bodies — use it instead of isinstance
    chains when recursing through a macro's item tree.

    Args:
        item: A MacroItem.

    Returns:
        [("body", actions)] for LoopBlock/WhileBlock,
        [("then", then_actions), ("else", else_actions)] for IfBlock,
        [] for leaf actions.
    """
    if isinstance(item, (LoopBlock, WhileBlock)):
        return [("body", item.actions)]
    if isinstance(item, IfBlock):
        return [("then", item.then_actions), ("else", item.else_actions)]
    return []


def collect_image_files(items: list) -> set[str]:
    """All reference-image filenames referenced anywhere in an item tree.

    Args:
        items: A list of MacroItems (a macro body).

    Returns:
        The set of ImageCondition.image_file values found at any depth.
    """
    files: set[str] = set()
    for item in items:
        condition = getattr(item, "condition", None)
        if isinstance(condition, ImageCondition):
            files.add(condition.image_file)
        for _, child_items in child_lists(item):
            files |= collect_image_files(child_items)
    return files


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
        ActionType.WAIT_FOR_IMAGE: WaitAction,
    }
    
    if action_type not in action_map:
        raise ValueError(f"Unknown action type: {action_type}")
    
    return action_map[action_type].model_validate(data)
