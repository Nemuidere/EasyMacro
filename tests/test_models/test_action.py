"""
Tests for action models.

Tests Pydantic validation for action types.
"""

import pytest

from src.models.action import (
    ActionType,
    ClickAction,
    DelayAction,
    IfBlock,
    ImageCondition,
    KeyPressAction,
    LoopBlock,
    MouseMoveAction,
    WaitAction,
    WhileBlock,
    child_lists,
    collect_image_files,
    flatten_items,
    is_container,
    parse_action,
)


class TestClickAction:
    """Tests for ClickAction model."""
    
    def test_create_click_action(self):
        """Test creating a click action."""
        action = ClickAction(x=100, y=200)
        
        assert action.x == 100
        assert action.y == 200
        assert action.button == "left"
        assert action.jitter_radius == 2
        assert action.action_type == ActionType.CLICK
    
    def test_create_click_action_with_custom_button(self):
        """Test creating a click action with custom button."""
        action = ClickAction(x=100, y=200, button="right")
        
        assert action.button == "right"
    
    def test_create_click_action_with_invalid_button_raises_error(self):
        """Test that invalid button raises ValueError."""
        with pytest.raises(ValueError, match="Button must be one of"):
            ClickAction(x=100, y=200, button="invalid")
    
    def test_create_click_action_with_negative_coordinates_raises_error(self):
        """Test that negative coordinates raise ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=-1, y=200)

        with pytest.raises(ValueError):
            ClickAction(x=100, y=-1)

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = ClickAction(x=100, y=200)

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5

    def test_delay_after_can_be_set(self):
        """Test that inline post-action delay can be configured."""
        action = ClickAction(x=100, y=200, delay_after_ms=250, delay_after_variance_percent=20)

        assert action.delay_after_ms == 250
        assert action.delay_after_variance_percent == 20

    def test_delay_after_negative_raises_error(self):
        """Test that a negative inline delay raises ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=100, y=200, delay_after_ms=-1)

    def test_delay_after_variance_out_of_range_raises_error(self):
        """Test that an out-of-range inline delay variance raises ValueError."""
        with pytest.raises(ValueError):
            ClickAction(x=100, y=200, delay_after_variance_percent=101)

    def test_create_click_hold_action(self):
        """Test creating a click-hold action (mirrors KeyPressAction's hold)."""
        action = ClickAction(x=100, y=200, button="right", action_type=ActionType.CLICK_HOLD)

        assert action.action_type == ActionType.CLICK_HOLD
        assert action.button == "right"

    def test_create_click_release_action(self):
        """Test creating a click-release action."""
        action = ClickAction(x=0, y=0, button="middle", action_type=ActionType.CLICK_RELEASE)

        assert action.action_type == ActionType.CLICK_RELEASE
        assert action.button == "middle"


class TestDelayAction:
    """Tests for DelayAction model."""
    
    def test_create_delay_action(self):
        """Test creating a delay action."""
        action = DelayAction(duration_ms=1000)
        
        assert action.duration_ms == 1000
        assert action.variance_percent == 5
        assert action.action_type == ActionType.DELAY
    
    def test_create_delay_action_with_custom_variance(self):
        """Test creating a delay action with custom variance."""
        action = DelayAction(duration_ms=1000, variance_percent=50)
        
        assert action.variance_percent == 50
    
    def test_create_delay_action_with_negative_duration_raises_error(self):
        """Test that negative duration raises ValueError."""
        with pytest.raises(ValueError):
            DelayAction(duration_ms=-1)
    
    def test_create_delay_action_with_invalid_variance_raises_error(self):
        """Test that invalid variance raises ValueError."""
        with pytest.raises(ValueError):
            DelayAction(duration_ms=1000, variance_percent=101)


class TestKeyPressAction:
    """Tests for KeyPressAction model."""
    
    def test_create_key_press_action(self):
        """Test creating a key press action."""
        action = KeyPressAction(key="a")
        
        assert action.key == "a"
        assert action.modifiers == []
        assert action.action_type == ActionType.KEY_PRESS
    
    def test_create_key_press_action_with_modifiers(self):
        """Test creating a key press action with modifiers."""
        action = KeyPressAction(key="a", modifiers=["ctrl", "shift"])
        
        assert action.modifiers == ["ctrl", "shift"]
    
    def test_create_key_press_action_with_invalid_modifier_raises_error(self):
        """Test that invalid modifier raises ValueError."""
        with pytest.raises(ValueError, match="Modifier must be one of"):
            KeyPressAction(key="a", modifiers=["invalid"])
    
    def test_create_key_press_action_with_empty_key_raises_error(self):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError):
            KeyPressAction(key="")

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = KeyPressAction(key="a")

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5


class TestMouseMoveAction:
    """Tests for MouseMoveAction model."""
    
    def test_create_mouse_move_action(self):
        """Test creating a mouse move action."""
        action = MouseMoveAction(x=100, y=200)
        
        assert action.x == 100
        assert action.y == 200
        assert action.smooth is True
        assert action.speed == 5
        assert action.action_type == ActionType.MOUSE_MOVE
    
    def test_create_mouse_move_action_with_custom_speed(self):
        """Test creating a mouse move action with custom speed."""
        action = MouseMoveAction(x=100, y=200, speed=10)
        
        assert action.speed == 10
    
    def test_create_mouse_move_action_with_invalid_speed_raises_error(self):
        """Test that invalid speed raises ValueError."""
        with pytest.raises(ValueError):
            MouseMoveAction(x=100, y=200, speed=0)

        with pytest.raises(ValueError):
            MouseMoveAction(x=100, y=200, speed=11)

    def test_delay_after_defaults_to_none(self):
        """Test that inline post-action delay defaults to off."""
        action = MouseMoveAction(x=100, y=200)

        assert action.delay_after_ms == 0
        assert action.delay_after_variance_percent == 5


class TestParseAction:
    """Tests for parse_action function."""
    
    def test_parse_click_action(self):
        """Test parsing a click action."""
        data = {"action_type": "click", "x": 100, "y": 200}
        
        action = parse_action(data)
        
        assert isinstance(action, ClickAction)
        assert action.x == 100
        assert action.y == 200
    
    def test_parse_delay_action(self):
        """Test parsing a delay action."""
        data = {"action_type": "delay", "duration_ms": 1000}
        
        action = parse_action(data)
        
        assert isinstance(action, DelayAction)
        assert action.duration_ms == 1000
    
    def test_parse_key_press_action(self):
        """Test parsing a key press action."""
        data = {"action_type": "key_press", "key": "a"}
        
        action = parse_action(data)
        
        assert isinstance(action, KeyPressAction)
        assert action.key == "a"
    
    def test_parse_mouse_move_action(self):
        """Test parsing a mouse move action."""
        data = {"action_type": "mouse_move", "x": 100, "y": 200}
        
        action = parse_action(data)
        
        assert isinstance(action, MouseMoveAction)
        assert action.x == 100
    
    def test_parse_action_without_type_raises_error(self):
        """Test that parsing without action_type raises ValueError."""
        with pytest.raises(ValueError, match="must contain 'action_type'"):
            parse_action({"x": 100})
    
    def test_parse_action_with_unknown_type_raises_error(self):
        """Test that parsing with unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown action type"):
            parse_action({"action_type": "unknown"})

    def test_parse_click_hold_action(self):
        """Test parsing a click-hold action."""
        data = {"action_type": "click_hold", "x": 10, "y": 20, "button": "right"}

        action = parse_action(data)

        assert isinstance(action, ClickAction)
        assert action.action_type == ActionType.CLICK_HOLD
        assert action.button == "right"

    def test_parse_click_release_action(self):
        """Test parsing a click-release action."""
        data = {"action_type": "click_release", "x": 0, "y": 0, "button": "middle"}

        action = parse_action(data)

        assert isinstance(action, ClickAction)
        assert action.action_type == ActionType.CLICK_RELEASE
        assert action.button == "middle"


class TestLoopBlockNesting:
    """Tests for LoopBlock, including nesting to arbitrary depth."""

    def test_create_loop_block_with_leaf_actions(self):
        block = LoopBlock(count=5, actions=[ClickAction(x=1, y=1)])

        assert block.count == 5
        assert len(block.actions) == 1

    def test_count_must_be_at_least_one(self):
        with pytest.raises(ValueError):
            LoopBlock(count=0, actions=[ClickAction(x=1, y=1)])

    def test_loop_block_can_contain_a_nested_loop_block(self):
        inner = LoopBlock(count=25, actions=[ClickAction(x=1, y=1)])
        outer = LoopBlock(count=10, actions=[ClickAction(x=2, y=2), inner])

        assert isinstance(outer.actions[1], LoopBlock)
        assert outer.actions[1].count == 25

    def test_nested_loop_blocks_round_trip_through_dict(self):
        inner = LoopBlock(count=25, actions=[ClickAction(x=1, y=1)])
        outer = LoopBlock(count=10, actions=[ClickAction(x=2, y=2), inner])

        data = outer.model_dump()
        reloaded = LoopBlock.model_validate(data)

        assert isinstance(reloaded.actions[1], LoopBlock)
        assert reloaded.actions[1].count == 25
        assert isinstance(reloaded.actions[1].actions[0], ClickAction)

    def test_flatten_items_handles_arbitrary_nesting_depth(self):
        # Loop A (x25) inside loop B (x10), then a trailing click.
        inner = LoopBlock(count=25, actions=[ClickAction(x=1, y=1)])
        outer = LoopBlock(count=10, actions=[ClickAction(x=2, y=2), inner])
        items = [outer, ClickAction(x=3, y=3)]

        flat = flatten_items(items)

        # outer runs 10x: each pass is [click(2,2), inner(25x click(1,1))] = 26 items
        # + 1 trailing click(3,3)
        assert len(flat) == 10 * 26 + 1
        assert flat[-1].x == 3


def _cond(**overrides) -> ImageCondition:
    """A valid ImageCondition for tests, with optional field overrides."""
    fields = {"image_file": "ref_test.png", "x1": 100, "y1": 200, "x2": 300, "y2": 260}
    fields.update(overrides)
    return ImageCondition(**fields)


class TestImageCondition:
    """Tests for the ImageCondition embedded value object."""

    def test_create_with_defaults(self):
        cond = _cond()

        assert cond.color_variation == 20
        assert cond.negate is False

    def test_swapped_corners_are_normalized(self):
        cond = _cond(x1=300, y1=260, x2=100, y2=200)

        assert (cond.x1, cond.y1, cond.x2, cond.y2) == (100, 200, 300, 260)

    def test_zero_area_region_rejected(self):
        with pytest.raises(ValueError):
            _cond(x1=100, x2=100)
        with pytest.raises(ValueError):
            _cond(y1=200, y2=200)

    def test_negative_coordinates_allowed_for_secondary_monitors(self):
        cond = _cond(x1=-1920, y1=-100, x2=-100, y2=500)

        assert cond.x1 == -1920
        assert cond.y1 == -100

    def test_color_variation_bounds(self):
        with pytest.raises(ValueError):
            _cond(color_variation=-1)
        with pytest.raises(ValueError):
            _cond(color_variation=256)

    def test_empty_image_file_rejected(self):
        with pytest.raises(ValueError):
            _cond(image_file="")


class TestWaitAction:
    """Tests for the wait-for-image leaf action."""

    def test_create_with_defaults(self):
        action = WaitAction(condition=_cond())

        assert action.action_type == ActionType.WAIT_FOR_IMAGE
        assert action.poll_interval_ms == 200
        assert action.timeout_ms == 0
        assert action.on_timeout == "error"

    def test_poll_interval_floor(self):
        with pytest.raises(ValueError):
            WaitAction(condition=_cond(), poll_interval_ms=10)

    def test_on_timeout_restricted(self):
        with pytest.raises(ValueError):
            WaitAction(condition=_cond(), on_timeout="explode")

    def test_parse_action_maps_wait_for_image(self):
        data = WaitAction(condition=_cond()).model_dump()

        action = parse_action(data)

        assert isinstance(action, WaitAction)


class TestConditionBlocks:
    """Tests for IfBlock/WhileBlock construction and validation."""

    def test_if_block_bodies_default_empty(self):
        block = IfBlock(condition=_cond())

        assert block.then_actions == []
        assert block.else_actions == []

    def test_while_block_defaults(self):
        block = WhileBlock(condition=_cond())

        assert block.timeout_seconds == 0
        assert block.max_iterations == 0
        assert block.check_interval_ms == 100

    def test_while_caps_must_be_non_negative(self):
        with pytest.raises(ValueError):
            WhileBlock(condition=_cond(), timeout_seconds=-1)
        with pytest.raises(ValueError):
            WhileBlock(condition=_cond(), max_iterations=-1)


class TestMacroItemDiscrimination:
    """Lock in smart-union discrimination for the full MacroItem union.

    Discrimination relies on extra="forbid" + full model_dump()s always
    carrying a key the other models forbid. This test pins that behavior for
    every container nested inside every other container.
    """

    def test_nested_blocks_round_trip_with_exact_types(self):
        from src.models.macro import Macro

        macro = Macro(
            name="conditional",
            actions=[
                IfBlock(
                    condition=_cond(),
                    then_actions=[
                        WhileBlock(
                            condition=_cond(image_file="ref_b.png"),
                            actions=[WaitAction(condition=_cond()), ClickAction(x=1, y=2)],
                        ),
                    ],
                    else_actions=[LoopBlock(count=2, actions=[ClickAction(x=3, y=4)])],
                ),
                WaitAction(condition=_cond(image_file="ref_c.png")),
            ],
        )

        reloaded = Macro.model_validate(macro.model_dump())

        if_block = reloaded.actions[0]
        assert type(if_block) is IfBlock
        while_block = if_block.then_actions[0]
        assert type(while_block) is WhileBlock
        assert type(while_block.actions[0]) is WaitAction
        assert type(while_block.actions[1]) is ClickAction
        assert type(if_block.else_actions[0]) is LoopBlock
        assert type(reloaded.actions[1]) is WaitAction

    def test_loop_block_still_discriminates_against_new_blocks(self):
        block = LoopBlock(count=3, actions=[ClickAction(x=1, y=1)])

        reloaded = LoopBlock.model_validate(block.model_dump())

        assert type(reloaded) is LoopBlock


class TestContainerHelpers:
    """Tests for is_container / child_lists / collect_image_files."""

    def test_is_container(self):
        assert is_container(LoopBlock(count=1))
        assert is_container(IfBlock(condition=_cond()))
        assert is_container(WhileBlock(condition=_cond()))
        assert not is_container(ClickAction(x=1, y=1))
        assert not is_container(WaitAction(condition=_cond()))

    def test_child_lists_shapes(self):
        loop = LoopBlock(count=1, actions=[ClickAction(x=1, y=1)])
        while_block = WhileBlock(condition=_cond(), actions=[ClickAction(x=2, y=2)])
        if_block = IfBlock(condition=_cond(), then_actions=[ClickAction(x=3, y=3)])

        assert child_lists(loop) == [("body", loop.actions)]
        assert child_lists(while_block) == [("body", while_block.actions)]
        assert child_lists(if_block) == [
            ("then", if_block.then_actions),
            ("else", if_block.else_actions),
        ]
        assert child_lists(ClickAction(x=1, y=1)) == []

    def test_collect_image_files_finds_all_depths(self):
        items = [
            IfBlock(
                condition=_cond(image_file="a.png"),
                then_actions=[
                    LoopBlock(count=2, actions=[WaitAction(condition=_cond(image_file="b.png"))]),
                ],
                else_actions=[WhileBlock(condition=_cond(image_file="c.png"))],
            ),
            ClickAction(x=1, y=1),
        ]

        assert collect_image_files(items) == {"a.png", "b.png", "c.png"}
