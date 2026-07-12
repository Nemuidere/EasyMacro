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
from src.ui.pages.builder_page import MacroBuilderPage, summarize_action, ActionConfigDialog


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


def test_click_dialog_delay_after_round_trips(qapp):
    d = ActionConfigDialog("click")
    d._x_spin.setValue(10)
    d._y_spin.setValue(20)
    d._delay_after_check.setChecked(True)
    d._delay_after_ms.setValue(300)
    d._delay_after_variance.setValue(15)
    d._on_accept()
    action = d.result_action()

    assert action.delay_after_ms == 300
    assert action.delay_after_variance_percent == 15

    reloaded = ActionConfigDialog("click", existing=action)
    assert reloaded._delay_after_check.isChecked() is True
    assert reloaded._delay_after_ms.value() == 300
    assert reloaded._delay_after_variance.value() == 15


def test_click_dialog_delay_after_defaults_to_zero_when_unchecked(qapp):
    d = ActionConfigDialog("click")
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
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (7, True))

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
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

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
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

    page.reset()
    page._actions = [ClickAction(x=100, y=100), ClickAction(x=500, y=450)]
    page._on_realistic_movement()
    first_pass_len = len(page._actions)

    page._on_realistic_movement()

    assert len(page._actions) == first_pass_len


def test_realistic_movement_recurses_into_loop_blocks(page, monkeypatch):
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

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
    import src.ui.pages.builder_page as bm
    monkeypatch.setattr(bm.QInputDialog, "getInt", lambda *a, **k: (5, True))

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


def test_reorder_and_remove(page):
    page.reset()
    a = ClickAction(x=1, y=1)
    b = DelayAction(duration_ms=100)
    page._actions = [a, b]
    page._refresh_list(select_index=0)

    page._move(1)  # move 'a' down
    assert page._actions == [b, a]

    page._action_list.setCurrentRow(0)
    page._on_remove()
    assert page._actions == [a]


def test_duplicate_creates_distinct_action(page):
    page.reset()
    a = ClickAction(x=5, y=6)
    page._actions = [a]
    page._refresh_list(select_index=0)

    page._on_duplicate()
    assert len(page._actions) == 2
    assert page._actions[0].id != page._actions[1].id
    assert page._actions[1].x == 5 and page._actions[1].y == 6


def test_key_hold_with_modifiers(qapp):
    d = ActionConfigDialog("key_hold")
    d._key_capture.set_key("a")
    d._mod_checks["ctrl"].setChecked(True)
    d._mod_checks["shift"].setChecked(True)
    d._on_accept()
    actions = d.result_actions()
    assert len(actions) == 1
    assert actions[0].action_type == ActionType.KEY_HOLD
    assert set(actions[0].modifiers) == {"ctrl", "shift"}


def test_key_hold_for_duration_expands_to_three_steps(qapp):
    d = ActionConfigDialog("key_hold")
    d._key_capture.set_key("space")
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
        page._action_list.item(r).setSelected(True)

    page._on_loop_selected()

    assert len(page._actions) == 2
    assert isinstance(page._actions[0], LoopBlock)
    assert page._actions[0].count == 5
    assert len(page._actions[0].actions) == 2
    assert isinstance(page._actions[1], ClickAction)


def test_ungroup_expands_loop(page):
    page.reset()
    page._actions = [LoopBlock(count=3, actions=[ClickAction(x=1, y=1), ClickAction(x=2, y=2)])]
    page._refresh_list(select_index=0)
    page._action_list.setCurrentRow(0)

    page._on_ungroup()

    assert len(page._actions) == 2
    assert all(isinstance(a, ClickAction) for a in page._actions)


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


def test_save_requires_name_and_actions(page, macro_service, monkeypatch):
    # The invalid-save path pops a modal warning; stub it so the test doesn't block.
    import src.ui.pages.builder_page as builder_module
    monkeypatch.setattr(builder_module.QMessageBox, "warning", lambda *a, **k: None)

    page.reset()
    page._actions = [ClickAction(x=1, y=1)]
    # No name -> should not save.
    page._on_save()
    assert macro_service.count() == 0
