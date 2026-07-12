"""
Logic tests for the Macro Builder page.

These exercise the non-visual behaviour: assembling a mixed action list,
inline per-step delays, the realistic-movement transform, reorder/duplicate/
remove, and save/reload round-trip through the macro service. GUI-only
concerns (dialog layout, live F2 capture) are covered by the physical
checklist, not here.
"""

import pytest

from src.services.macro_service import init_macro_service, get_macro_service
import src.services.macro_service as macro_service_module
from src.models.action import (
    ClickAction,
    DelayAction,
    KeyPressAction,
    MouseMoveAction,
    ActionType,
    LoopBlock,
)
from src.services.macro_service import MacroService
from src.ui.pages.builder_page import (
    MacroBuilderPage,
    summarize_action,
    ActionConfigDialog,
    InputActionDialog,
)


@pytest.fixture
def macro_service(tmp_path, initialized_event_bus):
    macro_service_module._macro_service = None
    svc = init_macro_service(tmp_path / "macros.json")
    yield svc
    macro_service_module._macro_service = None


@pytest.fixture
def page(qapp, macro_service):
    return MacroBuilderPage()


def _mixed_actions():
    return [
        ClickAction(x=300, y=400, button="left"),
        KeyPressAction(key="shift", action_type=ActionType.KEY_HOLD),
        MouseMoveAction(x=10, y=20),
        KeyPressAction(key="shift", action_type=ActionType.KEY_RELEASE),
    ]


def test_summaries_are_readable():
    assert "Left-click" in summarize_action(ClickAction(x=1, y=2))
    assert "Double-click" in summarize_action(
        ClickAction(x=1, y=2, action_type=ActionType.DOUBLE_CLICK)
    )
    assert "Hold key 'shift'" == summarize_action(
        KeyPressAction(key="shift", action_type=ActionType.KEY_HOLD)
    )
    assert "Release key 'shift'" == summarize_action(
        KeyPressAction(key="shift", action_type=ActionType.KEY_RELEASE)
    )
    assert "Delay 500 ms" == summarize_action(DelayAction(duration_ms=500))
    hold_summary = summarize_action(
        ClickAction(x=1, y=2, button="right", action_type=ActionType.CLICK_HOLD)
    )
    assert "Hold" in hold_summary and "right" in hold_summary
    release_summary = summarize_action(
        ClickAction(x=1, y=2, button="right", action_type=ActionType.CLICK_RELEASE)
    )
    assert "Release" in release_summary and "right" in release_summary
    # A hold/release summary must not be mistaken for an ordinary click.
    assert "click" not in hold_summary.lower().split(" @ ")[0]


def test_save_mixed_macro_round_trips(page, macro_service):
    page.reset()
    page._name_input.setText("Mixed")
    page._actions = _mixed_actions()

    page._on_save()

    saved = macro_service.get_all()
    assert len(saved) == 1
    macro = saved[0]
    assert macro.name == "Mixed"
    types = [a.action_type for a in macro.actions]
    assert types == [
        ActionType.CLICK,
        ActionType.KEY_HOLD,
        ActionType.MOUSE_MOVE,
        ActionType.KEY_RELEASE,
    ]


def test_edit_loads_existing_actions(page, macro_service):
    page.reset()
    page._name_input.setText("Editable")
    page._actions = _mixed_actions()
    page._on_save()
    macro_id = macro_service.get_all()[0].id

    fresh = MacroBuilderPage()
    fresh.set_macro_id(macro_id)
    assert fresh._name_input.text() == "Editable"
    assert len(fresh._actions) == 4


def test_add_appends_to_top_level_when_nothing_selected(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    new_click = ClickAction(x=42, y=42)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])

    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    page._refresh_list()

    page._on_add()

    assert len(page._actions) == 2
    assert page._actions[-1] is new_click


def test_add_inserts_after_selected_top_level_step(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    new_click = ClickAction(x=42, y=42)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])

    page.reset()
    page._actions = [ClickAction(x=1, y=1), ClickAction(x=2, y=2)]
    page._refresh_list()
    page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

    page._on_add()

    assert len(page._actions) == 3
    assert page._actions[1] is new_click
    assert page._actions[2].x == 2


def test_add_inserts_inside_selected_loop(page, monkeypatch):
    """Selecting a loop row and hitting Add puts the new step inside that
    loop's own body, at the end."""
    import src.ui.pages.builder_page as bm
    new_click = ClickAction(x=42, y=42)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])

    page.reset()
    page._actions = [LoopBlock(count=5, actions=[ClickAction(x=1, y=1)])]
    page._refresh_list()
    page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

    page._on_add()

    block = page._actions[0]
    assert len(page._actions) == 1  # nothing new at the top level
    assert len(block.actions) == 2
    assert block.actions[-1] is new_click


def test_add_inserts_after_selected_step_inside_loop(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    new_click = ClickAction(x=42, y=42)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])

    page.reset()
    page._actions = [LoopBlock(count=5, actions=[ClickAction(x=1, y=1), ClickAction(x=2, y=2)])]
    page._refresh_list()
    loop_item = page._action_list.topLevelItem(0)
    page._action_list.setCurrentItem(loop_item.child(0))

    page._on_add()

    block = page._actions[0]
    assert len(block.actions) == 3
    assert block.actions[1] is new_click
    assert block.actions[2].x == 2


def test_add_inserts_inside_nested_loop(page, monkeypatch):
    """Add works at any nesting depth, not just one level in."""
    import src.ui.pages.builder_page as bm
    new_click = ClickAction(x=42, y=42)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_actions", lambda self: [new_click])

    page.reset()
    page._actions = [
        LoopBlock(count=10, actions=[
            ClickAction(x=2, y=2),
            LoopBlock(count=25, actions=[ClickAction(x=1, y=1)]),
        ]),
    ]
    page._refresh_list()
    outer_item = page._action_list.topLevelItem(0)
    inner_loop_item = outer_item.child(1)
    page._action_list.setCurrentItem(inner_loop_item)

    page._on_add()

    inner = page._actions[0].actions[1]
    assert len(inner.actions) == 2
    assert inner.actions[-1] is new_click


def test_double_click_editing_does_not_also_toggle_expand(page):
    assert page._action_list.expandsOnDoubleClick() is False


def test_edit_updates_click_nested_inside_loop(page, monkeypatch):
    """Regression: editing a click that's part of a loop must update the
    click in place, not silently no-op (this was impossible pre-tree-view,
    when a loop's body was a single collapsed summary row)."""
    import src.ui.pages.builder_page as bm
    edited = ClickAction(x=999, y=888)
    monkeypatch.setattr(bm.InputActionDialog, "exec", lambda self: bm.QDialog.Accepted)
    monkeypatch.setattr(bm.InputActionDialog, "result_action", lambda self: edited)

    page.reset()
    page._actions = [LoopBlock(count=5, actions=[ClickAction(x=1, y=1), ClickAction(x=2, y=2)])]
    page._refresh_list()
    loop_item = page._action_list.topLevelItem(0)
    child_item = loop_item.child(0)

    page._on_edit_item(child_item, 0)

    assert page._actions[0].actions[0] is edited
    assert page._actions[0].actions[1].x == 2


def test_click_dialog_delay_after_round_trips(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._x_spin.setValue(10)
    d._y_spin.setValue(20)
    d._delay_after_check.setChecked(True)
    d._delay_after_ms.setValue(300)
    d._delay_after_variance.setValue(15)
    d._on_accept()
    action = d.result_action()

    assert action.delay_after_ms == 300
    assert action.delay_after_variance_percent == 15

    reloaded = InputActionDialog(existing=action)
    assert reloaded._delay_after_check.isChecked() is True
    assert reloaded._delay_after_ms.value() == 300
    assert reloaded._delay_after_variance.value() == 15


def test_click_dialog_delay_after_defaults_to_zero_when_unchecked(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._x_spin.setValue(10)
    d._y_spin.setValue(20)
    d._on_accept()
    action = d.result_action()

    assert action.delay_after_ms == 0


def test_summaries_show_delay_after_suffix():
    action = ClickAction(x=1, y=2, delay_after_ms=250)
    assert "+250ms delay" in summarize_action(action)
    assert "+" not in summarize_action(ClickAction(x=1, y=2))


def test_realistic_movement_inserts_moves_between_different_positions(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (7, False))

    page.reset()
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=450)]
    page._on_realistic_movement()

    # A leading move to the first target, plus one between the two clicks.
    assert len(page._actions) == 4
    assert isinstance(page._actions[0], MouseMoveAction)
    assert isinstance(page._actions[1], ClickAction)
    assert isinstance(page._actions[2], MouseMoveAction)
    assert (page._actions[2].x, page._actions[2].y) == (500, 450)
    assert page._actions[2].speed == 7
    assert isinstance(page._actions[3], ClickAction)


def test_realistic_movement_skips_repeated_same_position(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))

    page.reset()
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=100, y=100)]
    page._on_realistic_movement()

    # Leading move to the first target, but nothing inserted between the two
    # identical-position clicks.
    assert len(page._actions) == 3
    assert isinstance(page._actions[0], MouseMoveAction)
    assert isinstance(page._actions[1], ClickAction)
    assert isinstance(page._actions[2], ClickAction)


def test_realistic_movement_is_idempotent(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))

    page.reset()
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=450)]
    page._on_realistic_movement()
    first_pass_len = len(page._actions)

    page._on_realistic_movement()

    assert len(page._actions) == first_pass_len


def test_realistic_movement_recurses_into_loop_blocks(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))

    page.reset()
    page._actions = [LoopBlock(count=3, actions=[ClickAction(x=1, y=1), ClickAction(x=9, y=9)])]
    page._on_realistic_movement()

    block = page._actions[0]
    assert isinstance(block, LoopBlock)
    # A leading move into the loop body (each pass through the loop needs to
    # travel back to the start), plus one between the two clicks.
    assert len(block.actions) == 4
    assert isinstance(block.actions[0], MouseMoveAction)
    assert (block.actions[0].x, block.actions[0].y) == (1, 1)
    assert isinstance(block.actions[1], ClickAction)
    assert isinstance(block.actions[2], MouseMoveAction)
    assert (block.actions[2].x, block.actions[2].y) == (9, 9)
    assert isinstance(block.actions[3], ClickAction)


def test_realistic_movement_skips_cursor_position_clicks(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, False))

    page.reset()
    page._actions = [
        ClickAction(x=0, y=0, use_cursor_position=True),
        ClickAction(x=200, y=200),
    ]
    page._on_realistic_movement()

    # No move before the cursor-position click (its target is unknown); one
    # gets inserted before the fixed-position click that follows.
    assert len(page._actions) == 3
    assert isinstance(page._actions[0], ClickAction)
    assert page._actions[0].use_cursor_position is True
    assert isinstance(page._actions[1], MouseMoveAction)
    assert isinstance(page._actions[2], ClickAction)


def test_realistic_movement_requires_actions(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    called = []
    monkeypatch.setattr(bm.QMessageBox, "information", lambda *a, **k: called.append(True))

    page.reset()
    page._on_realistic_movement()

    assert called == [True]
    assert page._actions == []


def test_realistic_movement_account_for_loop_connects_macro_ends(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, True))

    page.reset()
    page._loop_check.setChecked(True)  # "Loop until stopped" -> macro repeats
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=500)]

    page._on_realistic_movement()

    last = page._actions[-1]
    assert isinstance(last, MouseMoveAction)
    assert (last.x, last.y) == (100, 100)


def test_realistic_movement_account_for_loop_connects_nested_loop_ends(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, True))

    page.reset()
    page._loop_check.setChecked(False)
    page._repeat_spin.setValue(1)  # macro itself runs once -> no macro-level connector
    page._actions = [
        LoopBlock(count=25, actions=[ClickAction(x=1, y=1), ClickAction(x=9, y=9)]),
    ]

    page._on_realistic_movement()

    block = page._actions[0]
    last_in_loop = block.actions[-1]
    assert isinstance(last_in_loop, MouseMoveAction)
    assert (last_in_loop.x, last_in_loop.y) == (1, 1)
    # No macro-level connector appended after the loop (single run).
    assert len(page._actions) == 1


def test_realistic_movement_account_for_loop_skips_single_run_macro(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, True))

    page.reset()
    page._loop_check.setChecked(False)
    page._repeat_spin.setValue(1)
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=500)]

    page._on_realistic_movement()

    # Macro runs once — nothing to connect back to.
    last = page._actions[-1]
    assert isinstance(last, ClickAction)


def test_realistic_movement_account_for_loop_skips_a_loop_that_runs_once(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, True))

    page.reset()
    page._loop_check.setChecked(False)
    page._repeat_spin.setValue(1)
    page._actions = [LoopBlock(count=1, actions=[ClickAction(x=1, y=1), ClickAction(x=9, y=9)])]

    page._on_realistic_movement()

    block = page._actions[0]
    # count=1 never wraps around, so no connector inside the loop body either.
    assert isinstance(block.actions[-1], ClickAction)


def test_realistic_movement_account_for_loop_is_idempotent(page, monkeypatch):
    monkeypatch.setattr(page, "_prompt_realistic_movement_options", lambda: (5, True))

    page.reset()
    page._loop_check.setChecked(True)
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=500)]

    page._on_realistic_movement()
    first_pass_len = len(page._actions)

    page._on_realistic_movement()

    assert len(page._actions) == first_pass_len


def test_reorder_and_remove(page):
    page.reset()
    a = ClickAction(x=1, y=1)
    b = DelayAction(duration_ms=100)
    page._actions = [a, b]
    page._refresh_list(select_path=[0])

    page._move(1)  # move 'a' down
    assert page._actions == [b, a]

    page._action_list.setCurrentItem(page._action_list.topLevelItem(0))
    page._on_remove()
    assert page._actions == [a]


def test_duplicate_creates_distinct_action(page):
    page.reset()
    a = ClickAction(x=5, y=6)
    page._actions = [a]
    page._refresh_list(select_path=[0])

    page._on_duplicate()
    assert len(page._actions) == 2
    assert page._actions[0].id != page._actions[1].id
    assert page._actions[1].x == 5 and page._actions[1].y == 6


def test_key_hold_with_modifiers(qapp):
    d = InputActionDialog()
    d._key_capture.set_key("a")
    d._hold_radio.setChecked(True)
    d._mod_checks["ctrl"].setChecked(True)
    d._mod_checks["shift"].setChecked(True)
    d._on_accept()
    actions = d.result_actions()
    assert len(actions) == 1
    assert actions[0].action_type == ActionType.KEY_HOLD
    assert set(actions[0].modifiers) == {"ctrl", "shift"}


def test_key_hold_for_duration_expands_to_three_steps(qapp):
    d = InputActionDialog()
    d._key_capture.set_key("space")
    d._hold_radio.setChecked(True)
    d._hold_for_radio.setChecked(True)
    d._hold_ms.setValue(750)
    d._on_accept()
    actions = d.result_actions()
    assert [a.action_type for a in actions] == [
        ActionType.KEY_HOLD,
        ActionType.DELAY,
        ActionType.KEY_RELEASE,
    ]
    assert actions[1].duration_ms == 750


def test_loop_selected_wraps_contiguous_range(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

    page.reset()
    page._actions = [ClickAction(x=1, y=1), ClickAction(x=2, y=2), ClickAction(x=3, y=3)]
    page._refresh_list()
    for r in (0, 1):
        page._action_list.topLevelItem(r).setSelected(True)

    page._on_loop_selected()

    assert len(page._actions) == 2
    assert isinstance(page._actions[0], LoopBlock)
    assert page._actions[0].count == 5
    assert len(page._actions[0].actions) == 2
    assert isinstance(page._actions[1], ClickAction)


def test_loop_selected_can_wrap_a_selection_that_already_contains_a_loop(page, monkeypatch):
    """Nested loops: selecting a loop block alongside a plain step and
    looping again should wrap them together instead of being blocked."""
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (10, True))

    page.reset()
    page._actions = [
        LoopBlock(count=25, actions=[ClickAction(x=1, y=1)]),
        ClickAction(x=2, y=2),
    ]
    page._refresh_list()
    for r in (0, 1):
        page._action_list.topLevelItem(r).setSelected(True)

    page._on_loop_selected()

    assert len(page._actions) == 1
    outer = page._actions[0]
    assert isinstance(outer, LoopBlock)
    assert outer.count == 10
    assert len(outer.actions) == 2
    inner = outer.actions[0]
    assert isinstance(inner, LoopBlock)
    assert inner.count == 25


def test_loop_selected_rejects_non_sibling_selection(page, monkeypatch):
    """A step inside a loop and a step outside it aren't at the same level,
    so they can't be wrapped together."""
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))
    warned = []
    monkeypatch.setattr(bm.QMessageBox, "warning", lambda *a, **k: warned.append(True))

    page.reset()
    page._actions = [
        LoopBlock(count=3, actions=[ClickAction(x=1, y=1)]),
        ClickAction(x=2, y=2),
    ]
    page._refresh_list()
    inner_item = page._action_list.topLevelItem(0).child(0)
    inner_item.setSelected(True)
    page._action_list.topLevelItem(1).setSelected(True)

    page._on_loop_selected()

    assert warned == [True]
    # Nothing changed.
    assert len(page._actions) == 2
    assert isinstance(page._actions[0], LoopBlock)


def test_ungroup_expands_loop(page):
    page.reset()
    page._actions = [LoopBlock(count=3, actions=[ClickAction(x=1, y=1), ClickAction(x=2, y=2)])]
    page._refresh_list(select_path=[0])
    page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

    page._on_ungroup()

    assert len(page._actions) == 2
    assert all(isinstance(a, ClickAction) for a in page._actions)


def test_ungroup_only_expands_one_level(page):
    """Ungrouping an outer loop leaves a loop nested inside it intact."""
    page.reset()
    page._actions = [
        LoopBlock(count=10, actions=[
            ClickAction(x=2, y=2),
            LoopBlock(count=25, actions=[ClickAction(x=1, y=1)]),
        ]),
    ]
    page._refresh_list(select_path=[0])
    page._action_list.setCurrentItem(page._action_list.topLevelItem(0))

    page._on_ungroup()

    assert len(page._actions) == 2
    assert isinstance(page._actions[0], ClickAction)
    assert isinstance(page._actions[1], LoopBlock)
    assert page._actions[1].count == 25


def test_move_and_remove_inside_nested_loop(page):
    """Move/Remove operate on whatever's selected, including a step nested
    inside a loop block — not just the top level."""
    page.reset()
    inner_a = ClickAction(x=1, y=1)
    inner_b = ClickAction(x=2, y=2)
    block = LoopBlock(count=5, actions=[inner_a, inner_b])
    page._actions = [block]
    page._refresh_list()

    loop_item = page._action_list.topLevelItem(0)
    page._action_list.setCurrentItem(loop_item.child(0))
    page._move(1)  # swap inner_a/inner_b within the loop body
    assert page._actions[0].actions == [inner_b, inner_a]

    page._refresh_list()
    loop_item = page._action_list.topLevelItem(0)
    page._action_list.setCurrentItem(loop_item.child(0))
    page._on_remove()
    assert page._actions[0].actions == [inner_a]


def test_loop_macro_round_trips_through_json(page, macro_service):
    page.reset()
    page._name_input.setText("Looped")
    page._actions = [
        ClickAction(x=1, y=1),
        LoopBlock(count=4, actions=[ClickAction(x=2, y=2), DelayAction(duration_ms=50)]),
    ]
    page._on_save()

    # Force a real JSON reload from disk via a fresh service on the same path.
    reloaded = MacroService(macro_service._macros_path)
    macro = reloaded.get_all()[0]
    assert isinstance(macro.actions[1], LoopBlock)
    assert macro.actions[1].count == 4
    assert len(macro.actions[1].actions) == 2


def test_nested_loop_macro_round_trips_through_json(page, macro_service):
    page.reset()
    page._name_input.setText("Nested")
    page._actions = [
        LoopBlock(count=10, actions=[
            ClickAction(x=2, y=2),
            LoopBlock(count=25, actions=[ClickAction(x=1, y=1)]),
        ]),
    ]
    page._on_save()

    reloaded = MacroService(macro_service._macros_path)
    macro = reloaded.get_all()[0]
    outer = macro.actions[0]
    assert isinstance(outer, LoopBlock)
    assert outer.count == 10
    inner = outer.actions[1]
    assert isinstance(inner, LoopBlock)
    assert inner.count == 25
    assert inner.actions[0].x == 1


def test_save_requires_name_and_actions(page, macro_service, monkeypatch):
    # The invalid-save path pops a modal warning; stub it so the test doesn't block.
    import src.ui.pages.builder_page as builder_module
    monkeypatch.setattr(builder_module.QMessageBox, "warning", lambda *a, **k: None)

    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    # No name -> should not save.
    page._on_save()
    assert macro_service.count() == 0


# ---------------------------------------------------------------------------
# InputActionDialog: unified key/mouse press/hold/release (round J).
# ---------------------------------------------------------------------------

def test_input_dialog_defaults_to_key_press(qapp):
    d = InputActionDialog()
    d._key_capture.set_key("a")
    d._on_accept()
    action = d.result_action()
    assert isinstance(action, KeyPressAction)
    assert action.action_type == ActionType.KEY_PRESS


def test_input_dialog_key_release(qapp):
    d = InputActionDialog()
    d._key_capture.set_key("shift")
    d._release_radio.setChecked(True)
    d._on_accept()
    action = d.result_action()
    assert action.action_type == ActionType.KEY_RELEASE
    assert action.key == "shift"


def test_input_dialog_mouse_press_with_double_click(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._x_spin.setValue(100)
    d._y_spin.setValue(200)
    d._button_combo.setCurrentText("right")
    d._double_check.setChecked(True)
    d._on_accept()
    action = d.result_action()
    assert isinstance(action, ClickAction)
    assert action.action_type == ActionType.DOUBLE_CLICK
    assert action.button == "right"
    assert (action.x, action.y) == (100, 200)


def test_input_dialog_mouse_cursor_position(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._cursor_check.setChecked(True)
    d._on_accept()
    action = d.result_action()
    assert action.use_cursor_position is True


def test_input_dialog_mouse_hold(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._button_combo.setCurrentText("middle")
    d._x_spin.setValue(5)
    d._y_spin.setValue(6)
    d._mod_checks["ctrl"].setChecked(True)
    d._hold_radio.setChecked(True)
    d._on_accept()
    action = d.result_action()
    assert action.action_type == ActionType.CLICK_HOLD
    assert action.button == "middle"
    assert action.modifiers == ["ctrl"]


def test_input_dialog_mouse_hold_for_duration_expands_to_three_steps(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._button_combo.setCurrentText("left")
    d._x_spin.setValue(1)
    d._y_spin.setValue(2)
    d._hold_radio.setChecked(True)
    d._hold_for_radio.setChecked(True)
    d._hold_ms.setValue(400)
    d._on_accept()
    actions = d.result_actions()
    assert [a.action_type for a in actions] == [
        ActionType.CLICK_HOLD,
        ActionType.DELAY,
        ActionType.CLICK_RELEASE,
    ]
    assert actions[1].duration_ms == 400
    assert actions[2].button == "left"


def test_input_dialog_mouse_release(qapp):
    d = InputActionDialog()
    d._mouse_radio.setChecked(True)
    d._button_combo.setCurrentText("right")
    d._release_radio.setChecked(True)
    d._on_accept()
    action = d.result_action()
    assert action.action_type == ActionType.CLICK_RELEASE
    assert action.button == "right"


def test_input_dialog_key_requires_a_captured_key(qapp, monkeypatch):
    import src.ui.pages.builder_page as bm
    # Missing input pops a modal warning; stub it so the test doesn't block.
    monkeypatch.setattr(bm.QMessageBox, "warning", lambda *a, **k: None)

    d = InputActionDialog()
    d._on_accept()
    assert d.result_action() is None  # rejected: no key captured, warning shown instead


def test_input_dialog_loads_existing_key_hold(qapp):
    existing = KeyPressAction(key="f5", modifiers=["alt"], action_type=ActionType.KEY_HOLD)
    d = InputActionDialog(existing=existing)
    assert d._key_radio.isChecked() is True
    assert d._hold_radio.isChecked() is True
    assert d._key_capture.key() == "f5"
    assert d._mod_checks["alt"].isChecked() is True


def test_input_dialog_loads_existing_mouse_release(qapp):
    existing = ClickAction(x=0, y=0, button="right", action_type=ActionType.CLICK_RELEASE)
    d = InputActionDialog(existing=existing)
    assert d._mouse_radio.isChecked() is True
    assert d._release_radio.isChecked() is True
    assert d._button_combo.currentText() == "right"


def test_input_dialog_row_visibility_follows_mode(qapp):
    d = InputActionDialog()
    # Default: key + press.
    assert d._form.isRowVisible(d._key_capture) is True
    assert d._form.isRowVisible(d._button_combo) is False
    assert d._form.isRowVisible(d._x_spin) is False

    d._mouse_radio.setChecked(True)
    assert d._form.isRowVisible(d._key_capture) is False
    assert d._form.isRowVisible(d._button_combo) is True
    assert d._form.isRowVisible(d._x_spin) is True
    assert d._form.isRowVisible(d._double_check) is True

    d._hold_radio.setChecked(True)
    assert d._form.isRowVisible(d._double_check) is False
    assert d._form.isRowVisible(d._hold_until_radio) is True

    d._release_radio.setChecked(True)
    assert d._form.isRowVisible(d._x_spin) is False  # release needs no position
    assert d._form.isRowVisible(d._hold_until_radio) is False


def test_editing_existing_click_opens_input_dialog(page):
    """Double-clicking a Click step must open InputActionDialog, not the
    old (now move/delay-only) ActionConfigDialog."""
    click = ClickAction(x=1, y=1)
    dialog = page._dialog_for_existing(click)
    assert isinstance(dialog, InputActionDialog)


def test_editing_existing_move_opens_action_config_dialog(page):
    move = MouseMoveAction(x=1, y=1)
    dialog = page._dialog_for_existing(move)
    assert isinstance(dialog, ActionConfigDialog)


# ---------------------------------------------------------------------------
# Drag-and-drop reordering / reparenting (round J).
# ---------------------------------------------------------------------------

def test_drop_reconciliation_moves_step_into_loop(page):
    """Simulates what Qt's InternalMove drag-drop produces (a QTreeWidgetItem
    reparented into another), then checks _on_tree_dropped correctly rebuilds
    self._actions to match — this is the part we're responsible for; the
    actual mouse-drag gesture is Qt's own well-tested machinery."""
    page.reset()
    page._actions = [ClickAction(x=1, y=1), LoopBlock(count=5, actions=[ClickAction(x=2, y=2)])]
    page._refresh_list()

    moved_item = page._action_list.takeTopLevelItem(0)  # the Click(1,1) row
    loop_item = page._action_list.topLevelItem(0)  # now the only top-level row
    loop_item.addChild(moved_item)

    page._on_tree_dropped()

    assert len(page._actions) == 1
    loop = page._actions[0]
    assert isinstance(loop, LoopBlock)
    assert [(a.x, a.y) for a in loop.actions] == [(2, 2), (1, 1)]


def test_drop_reconciliation_moves_step_out_of_loop(page):
    page.reset()
    inner = ClickAction(x=9, y=9)
    page._actions = [LoopBlock(count=5, actions=[ClickAction(x=1, y=1), inner])]
    page._refresh_list()

    loop_item = page._action_list.topLevelItem(0)
    taken = loop_item.takeChild(1)  # the inner=Click(9,9) row
    page._action_list.addTopLevelItem(taken)  # promote it to top level

    page._on_tree_dropped()

    assert len(page._actions) == 2
    assert isinstance(page._actions[0], LoopBlock)
    assert len(page._actions[0].actions) == 1
    assert page._actions[1].x == 9


def test_drop_reconciliation_preserves_moved_loops_children(page):
    """Dragging a whole loop block (with its own body) must bring its
    children along intact, not lose or flatten them."""
    page.reset()
    page._actions = [
        ClickAction(x=1, y=1),
        LoopBlock(count=3, actions=[ClickAction(x=2, y=2), ClickAction(x=3, y=3)]),
    ]
    page._refresh_list()

    loop_item = page._action_list.takeTopLevelItem(1)
    page._action_list.insertTopLevelItem(0, loop_item)  # reorder: loop first now

    page._on_tree_dropped()

    assert isinstance(page._actions[0], LoopBlock)
    assert [(a.x, a.y) for a in page._actions[0].actions] == [(2, 2), (3, 3)]
    assert page._actions[1].x == 1


def test_drop_reconciliation_pushes_undo(page):
    page.reset()
    page._actions = [ClickAction(x=1, y=1), LoopBlock(count=5, actions=[ClickAction(x=2, y=2)])]
    page._refresh_list()

    moved_item = page._action_list.takeTopLevelItem(0)
    loop_item = page._action_list.topLevelItem(0)
    loop_item.addChild(moved_item)

    assert len(page._undo_stack) == 0
    page._on_tree_dropped()
    assert len(page._undo_stack) == 1


# ---------------------------------------------------------------------------
# Undo (round J).
# ---------------------------------------------------------------------------

def test_undo_restores_after_remove(page):
    page.reset()
    a = ClickAction(x=1, y=1)
    page._actions = [a]
    page._refresh_list(select_path=[0])

    page._on_remove()
    assert page._actions == []

    page._on_undo()
    assert page._actions == [a]


def test_undo_restores_after_move(page):
    page.reset()
    a, b = ClickAction(x=1, y=1), ClickAction(x=2, y=2)
    page._actions = [a, b]
    page._refresh_list(select_path=[0])

    page._move(1)
    assert page._actions == [b, a]

    page._on_undo()
    assert page._actions == [a, b]


def test_undo_button_enabled_state(page):
    page.reset()
    assert page._undo_btn.isEnabled() is False

    page._actions = [ClickAction(x=1, y=1)]
    page._refresh_list(select_path=[0])
    page._on_remove()
    assert page._undo_btn.isEnabled() is True

    page._on_undo()
    assert page._undo_btn.isEnabled() is False


def test_undo_is_noop_when_stack_empty(page):
    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    page._on_undo()  # nothing to undo
    assert len(page._actions) == 1


def test_undo_stack_capped_at_limit(page):
    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    page._refresh_list(select_path=[0])

    for _ in range(page._UNDO_LIMIT + 5):
        page._push_undo()

    assert len(page._undo_stack) == page._UNDO_LIMIT


def test_undo_stack_cleared_on_reset(page):
    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    page._refresh_list(select_path=[0])
    page._on_remove()
    assert page._undo_stack

    page.reset()
    assert page._undo_stack == []
    assert page._undo_btn.isEnabled() is False


def test_undo_covers_loop_and_ungroup(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

    page.reset()
    page._actions = [ClickAction(x=1, y=1), ClickAction(x=2, y=2)]
    page._refresh_list()
    for r in (0, 1):
        page._action_list.topLevelItem(r).setSelected(True)
    page._on_loop_selected()
    assert isinstance(page._actions[0], LoopBlock)

    page._on_undo()
    assert len(page._actions) == 2
    assert all(isinstance(a, ClickAction) for a in page._actions)


def test_undo_does_not_cover_settings_fields(page):
    """Undo scope is the step list only — name/hotkey/repeat/randomization
    aren't snapshotted, per the agreed scope."""
    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    page._refresh_list(select_path=[0])
    page._name_input.setText("Changed name")

    page._on_remove()
    page._on_undo()

    # The step list came back, but the name edit was never part of Undo.
    assert page._actions
    assert page._name_input.text() == "Changed name"
