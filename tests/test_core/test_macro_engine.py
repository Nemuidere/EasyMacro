"""
Tests for the MacroEngine execution model.

These exercise the timer-driven, non-blocking step machine: single runs,
finite/infinite repeat, stop/pause/resume, non-blocking delays, error
handling, and mouse-movement baseline updates. They drive a real Qt event
loop via QTest.qWait and use a mocked AHK service so no real input is sent.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtTest import QTest

from src.core.macro_engine import MacroEngine, ExecutionState
from src.core.randomization import RandomizationEngine
from src.core.state import StateManager, AppState
from src.models.settings import RandomizationSettings
from src.models.macro import Macro
from src.models.action import ClickAction, DelayAction, KeyPressAction, MouseMoveAction
from src.models.action import ActionType, LoopBlock


@pytest.fixture
def make_engine(qapp, initialized_event_bus, monkeypatch):
    """Factory building a MacroEngine wired to a mocked AHK service.

    Returns a callable: make_engine(mouse_service=None) -> (engine, ahk, state).
    """
    def _factory(mouse_service=None):
        ahk = MagicMock()
        ahk.get_mouse_position.return_value = (5, 5)
        monkeypatch.setattr(
            "src.services.ahk_service.get_ahk_service", lambda: ahk
        )

        randomization = RandomizationEngine(RandomizationSettings(enabled=False))
        state = StateManager()
        stats = MagicMock()

        engine = MacroEngine(randomization, state, stats, mouse_service)
        return engine, ahk, state

    return _factory


def _macro(actions, repeat_count=1):
    """Build a macro with randomization off for deterministic timing."""
    return Macro(
        name="Test",
        actions=actions,
        repeat_count=repeat_count,
        randomization_enabled=False,
    )


def test_single_click_runs_once_and_completes(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=10, y=20)], repeat_count=1)

    engine.run_macro(macro)
    QTest.qWait(80)

    assert ahk.click.call_count == 1
    assert not engine.is_running()
    assert state.get() == AppState.IDLE


def test_run_macro_returns_immediately_and_delay_is_non_blocking(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([DelayAction(duration_ms=150)], repeat_count=1)

    engine.run_macro(macro)
    # Control returned without sleeping the full delay.
    assert engine.is_running()

    # Part-way through the delay it is still running (delay didn't block).
    QTest.qWait(60)
    assert engine.is_running()

    # After the delay elapses it completes.
    QTest.qWait(200)
    assert not engine.is_running()


def test_finite_repeat_runs_n_times(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1)], repeat_count=3)

    engine.run_macro(macro)
    QTest.qWait(120)

    assert ahk.click.call_count == 3
    assert not engine.is_running()


def test_infinite_repeat_loops_then_stops(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1), DelayAction(duration_ms=10)], repeat_count=0)

    engine.run_macro(macro)
    QTest.qWait(120)

    # It looped many times without recursing into a stack overflow.
    assert ahk.click.call_count >= 2
    assert engine.is_running()

    engine.stop_macro()
    count_at_stop = ahk.click.call_count
    QTest.qWait(60)

    assert not engine.is_running()
    assert state.get() == AppState.IDLE
    # No further clicks happen after stop.
    assert ahk.click.call_count == count_at_stop


def test_pause_halts_progress_and_resume_continues(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1), DelayAction(duration_ms=20)], repeat_count=0)

    engine.run_macro(macro)
    QTest.qWait(80)
    assert engine.is_running()

    engine.pause_macro()
    assert engine.is_paused()
    count_while_paused = ahk.click.call_count
    QTest.qWait(120)
    # Nothing advances while paused.
    assert ahk.click.call_count == count_while_paused

    engine.resume_macro()
    QTest.qWait(120)
    assert ahk.click.call_count > count_while_paused

    engine.stop_macro()


def test_error_during_action_stops_and_reports(make_engine):
    engine, ahk, state = make_engine()
    ahk.click.side_effect = RuntimeError("boom")

    errors = []
    engine.macro_error.connect(lambda mid, msg: errors.append((mid, msg)))

    macro = _macro([ClickAction(x=1, y=1)], repeat_count=0)
    engine.run_macro(macro)
    QTest.qWait(80)

    assert errors, "macro_error should have been emitted"
    assert not engine.is_running()
    assert state.get() == AppState.ERROR


def test_click_updates_mouse_movement_baseline(make_engine):
    mouse_service = MagicMock()
    mouse_service.is_monitoring.return_value = True
    engine, ahk, state = make_engine(mouse_service=mouse_service)

    macro = _macro([ClickAction(x=42, y=99)], repeat_count=1)
    engine.run_macro(macro)
    QTest.qWait(80)

    mouse_service.update_reference_position.assert_called_with(42, 99)


# ---------------------------------------------------------------------------
# Action-result contracts: the engine must issue the *correct* AHK calls.
# ---------------------------------------------------------------------------

def test_double_click_issues_two_clicks(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [ClickAction(x=1, y=1, action_type=ActionType.DOUBLE_CLICK)], repeat_count=1
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    assert ahk.click.call_count == 1
    assert ahk.click.call_args.kwargs["click_count"] == 2


def test_right_click_action_type_forces_right_button(make_engine):
    engine, ahk, state = make_engine()
    # Button left, but the RIGHT_CLICK type must win.
    macro = _macro(
        [ClickAction(x=1, y=1, button="left", action_type=ActionType.RIGHT_CLICK)],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    assert ahk.click.call_args.kwargs["button"] == "right"


def test_middle_button_passes_through(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1, button="middle")], repeat_count=1)

    engine.run_macro(macro)
    QTest.qWait(80)

    assert ahk.click.call_args.kwargs["button"] == "middle"


def test_modifiers_pressed_and_released_in_order(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [ClickAction(x=1, y=1, modifiers=["shift", "ctrl"])], repeat_count=1
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    # Order across all mock methods: ctrl down, shift down, click, shift up, ctrl up.
    names = [
        (c[0], c.args[0] if c[0] != "click" else None)
        for c in ahk.mock_calls
        if c[0] in ("key_down", "key_up", "click")
    ]
    assert names == [
        ("key_down", "ctrl"),
        ("key_down", "shift"),
        ("click", None),
        ("key_up", "shift"),
        ("key_up", "ctrl"),
    ]


def test_cursor_position_click_queries_mouse_position(make_engine):
    engine, ahk, state = make_engine()  # ahk.get_mouse_position -> (5, 5)
    macro = _macro([ClickAction(x=0, y=0, use_cursor_position=True)], repeat_count=1)

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.get_mouse_position.assert_called()
    assert ahk.click.call_args.args[:2] == (5, 5)


def test_key_hold_then_release(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            KeyPressAction(key="shift", action_type=ActionType.KEY_HOLD),
            KeyPressAction(key="shift", action_type=ActionType.KEY_RELEASE),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.key_down.assert_called_with("shift")
    ahk.key_up.assert_called_with("shift")
    assert engine._held_keys == set()


def test_stop_releases_held_key(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            KeyPressAction(key="shift", action_type=ActionType.KEY_HOLD),
            DelayAction(duration_ms=10000),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(60)

    # Held during the long delay; not released yet.
    ahk.key_down.assert_called_with("shift")
    assert "shift" in engine._held_keys
    ahk.key_up.assert_not_called()

    engine.stop_macro()

    ahk.key_up.assert_called_with("shift")
    assert engine._held_keys == set()


def test_key_hold_with_modifiers_presses_all(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            KeyPressAction(key="a", modifiers=["ctrl"], action_type=ActionType.KEY_HOLD),
            KeyPressAction(key="a", modifiers=["ctrl"], action_type=ActionType.KEY_RELEASE),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    downs = [c.args[0] for c in ahk.key_down.call_args_list]
    ups = [c.args[0] for c in ahk.key_up.call_args_list]
    assert downs == ["ctrl", "a"]      # modifier before key
    assert ups == ["a", "ctrl"]        # key before modifier
    assert engine._held_keys == set()


def test_key_press_sends_press_not_down(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [KeyPressAction(key="a", modifiers=["ctrl"])], repeat_count=1
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.key_press.assert_called_once_with("a", ["ctrl"])
    ahk.key_down.assert_not_called()


def test_stats_updated_with_click_count(make_engine):
    ahk = MagicMock()
    ahk.get_mouse_position.return_value = (5, 5)

    import src.services.ahk_service as ahk_module
    orig = ahk_module.get_ahk_service
    ahk_module.get_ahk_service = lambda: ahk
    try:
        randomization = RandomizationEngine(RandomizationSettings(enabled=False))
        state = StateManager()
        stats = MagicMock()
        engine = MacroEngine(randomization, state, stats, None)

        macro = _macro([ClickAction(x=1, y=1)], repeat_count=1)
        engine.run_macro(macro)
        QTest.qWait(80)

        stats.update_clicks.assert_called_with(macro.id, 1)
    finally:
        ahk_module.get_ahk_service = orig


def test_loop_block_repeats_its_actions(make_engine):
    engine, ahk, state = make_engine()
    macro = Macro(
        name="Loop",
        actions=[LoopBlock(count=3, actions=[ClickAction(x=1, y=1)])],
        repeat_count=1,
        randomization_enabled=False,
    )
    engine.run_macro(macro)
    QTest.qWait(120)
    assert ahk.click.call_count == 3


def test_mixed_loop_and_plain_actions(make_engine):
    engine, ahk, state = make_engine()
    macro = Macro(
        name="Mixed",
        actions=[
            ClickAction(x=1, y=1),
            LoopBlock(count=2, actions=[ClickAction(x=2, y=2)]),
            ClickAction(x=3, y=3),
        ],
        repeat_count=1,
        randomization_enabled=False,
    )
    engine.run_macro(macro)
    QTest.qWait(150)
    # 1 + (2) + 1 = 4 clicks per pass.
    assert ahk.click.call_count == 4


def test_nested_loop_blocks_execute_correct_click_count(make_engine):
    engine, ahk, state = make_engine()
    inner = LoopBlock(count=25, actions=[ClickAction(x=1, y=1)])
    outer = LoopBlock(count=10, actions=[ClickAction(x=2, y=2), inner])
    macro = Macro(
        name="Nested",
        actions=[outer, ClickAction(x=3, y=3)],
        repeat_count=1,
        randomization_enabled=False,
    )
    engine.run_macro(macro)
    QTest.qWait(200)

    # outer runs 10x: each pass is click(2,2) + inner's 25 clicks = 26 clicks,
    # plus 1 trailing click outside the loop.
    assert ahk.click.call_count == 10 * 26 + 1


def test_outer_repeat_wraps_loop_blocks(make_engine):
    engine, ahk, state = make_engine()
    macro = Macro(
        name="Outer",
        actions=[LoopBlock(count=2, actions=[ClickAction(x=1, y=1)])],
        repeat_count=2,  # whole macro runs twice
        randomization_enabled=False,
    )
    engine.run_macro(macro)
    QTest.qWait(150)
    assert ahk.click.call_count == 4  # 2 (loop) * 2 (outer)


def test_jitter_keeps_click_near_target(qapp, initialized_event_bus, monkeypatch):
    ahk = MagicMock()
    ahk.get_mouse_position.return_value = (0, 0)
    monkeypatch.setattr("src.services.ahk_service.get_ahk_service", lambda: ahk)

    # Randomization ON with a small jitter radius (std dev = 2 px).
    randomization = RandomizationEngine(
        RandomizationSettings(enabled=True, jitter_radius=2)
    )
    engine = MacroEngine(randomization, StateManager(), MagicMock(), None)

    macro = Macro(
        name="Jitter",
        actions=[ClickAction(x=500, y=500)],
        repeat_count=1,
        randomization_enabled=True,
    )
    engine.run_macro(macro)
    QTest.qWait(80)

    x, y = ahk.click.call_args.args[:2]
    # 10 standard deviations — a false failure is astronomically unlikely.
    assert 480 <= x <= 520
    assert 480 <= y <= 520


# ---------------------------------------------------------------------------
# Inline "delay after this step" and per-action delay variance.
# ---------------------------------------------------------------------------

def test_click_delay_after_ms_delays_next_step(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [ClickAction(x=1, y=1, delay_after_ms=150), ClickAction(x=2, y=2)],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(30)
    assert ahk.click.call_count == 1

    # Still within the delay_after_ms window — second click hasn't fired yet.
    QTest.qWait(60)
    assert ahk.click.call_count == 1

    # After delay_after_ms elapses, the second click fires.
    QTest.qWait(150)
    assert ahk.click.call_count == 2


def test_action_without_delay_after_schedules_next_step_immediately(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1), ClickAction(x=2, y=2)], repeat_count=1)

    engine.run_macro(macro)
    QTest.qWait(50)

    assert ahk.click.call_count == 2


def test_delay_action_variance_percent_is_used(make_engine, monkeypatch):
    """Regression: DelayAction.variance_percent used to be accepted but never
    actually consulted by the engine (it always used the global setting)."""
    engine, ahk, state = make_engine()
    captured = {}

    def fake_randomize_delay(base_ms, variance_percent=None):
        captured["variance_percent"] = variance_percent
        return base_ms

    monkeypatch.setattr(engine._randomization, "randomize_delay", fake_randomize_delay)

    macro = Macro(
        name="Variance",
        actions=[DelayAction(duration_ms=1000, variance_percent=33)],
        repeat_count=1,
        randomization_enabled=True,
    )
    engine.run_macro(macro)
    QTest.qWait(80)

    assert captured["variance_percent"] == 33


def test_click_delay_after_variance_percent_is_used(make_engine, monkeypatch):
    engine, ahk, state = make_engine()
    captured = {}

    def fake_randomize_delay(base_ms, variance_percent=None):
        captured["variance_percent"] = variance_percent
        return base_ms

    monkeypatch.setattr(engine._randomization, "randomize_delay", fake_randomize_delay)

    macro = Macro(
        name="Variance",
        actions=[ClickAction(x=1, y=1, delay_after_ms=100, delay_after_variance_percent=42)],
        repeat_count=1,
        randomization_enabled=True,
    )
    engine.run_macro(macro)
    QTest.qWait(80)

    assert captured["variance_percent"] == 42
