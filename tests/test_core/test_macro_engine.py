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


# ---------------------------------------------------------------------------
# Mouse-button hold/release (round J) — mirrors key hold/release.
# ---------------------------------------------------------------------------

def test_click_hold_then_release(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            ClickAction(x=10, y=20, button="right", action_type=ActionType.CLICK_HOLD),
            ClickAction(x=0, y=0, button="right", action_type=ActionType.CLICK_RELEASE),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.mouse_down.assert_called_once_with(10, 20, button="right")
    ahk.mouse_up.assert_called_once_with("right")
    assert engine._held_mouse_buttons == set()


def test_click_hold_with_modifiers_presses_all(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            ClickAction(x=1, y=1, button="left", modifiers=["ctrl"], action_type=ActionType.CLICK_HOLD),
            ClickAction(x=0, y=0, button="left", modifiers=["ctrl"], action_type=ActionType.CLICK_RELEASE),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.key_down.assert_called_once_with("ctrl")
    ahk.mouse_down.assert_called_once_with(1, 1, button="left")
    ahk.mouse_up.assert_called_once_with("left")
    ahk.key_up.assert_called_once_with("ctrl")
    assert engine._held_keys == set()
    assert engine._held_mouse_buttons == set()


def test_click_hold_uses_cursor_position(make_engine):
    engine, ahk, state = make_engine()  # ahk.get_mouse_position -> (5, 5)
    macro = _macro(
        [ClickAction(x=0, y=0, button="left", use_cursor_position=True, action_type=ActionType.CLICK_HOLD)],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(80)

    ahk.get_mouse_position.assert_called()
    ahk.mouse_down.assert_called_once_with(5, 5, button="left")


def test_click_hold_updates_stats(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro([ClickAction(x=1, y=1, action_type=ActionType.CLICK_HOLD)], repeat_count=1)

    engine.run_macro(macro)
    QTest.qWait(80)

    engine._stats.update_clicks.assert_called_with(macro.id, 1)


def test_stop_releases_held_mouse_button(make_engine):
    engine, ahk, state = make_engine()
    macro = _macro(
        [
            ClickAction(x=1, y=1, button="right", action_type=ActionType.CLICK_HOLD),
            DelayAction(duration_ms=10000),
        ],
        repeat_count=1,
    )

    engine.run_macro(macro)
    QTest.qWait(60)

    # Held during the long delay; not released yet.
    ahk.mouse_down.assert_called_once_with(1, 1, button="right")
    assert "right" in engine._held_mouse_buttons
    ahk.mouse_up.assert_not_called()

    engine.stop_macro()

    ahk.mouse_up.assert_called_once_with("right")
    assert engine._held_mouse_buttons == set()


class TestScreenConditionControlFlow:
    """If/While/Wait execution driven by mocked image_search results.

    The reference image file itself is never touched here — the mocked AHK
    service's image_search return value (coords or None) decides branches.
    """

    @staticmethod
    def _cond(negate=False):
        from src.models.action import ImageCondition
        return ImageCondition(
            image_file="ref.png", x1=0, y1=0, x2=10, y2=10, negate=negate
        )

    def test_if_true_runs_then_branch_only(self, make_engine):
        from src.models.action import IfBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = (5, 5)
        macro = _macro([
            IfBlock(
                condition=self._cond(),
                then_actions=[ClickAction(x=1, y=1)],
                else_actions=[ClickAction(x=2, y=2)],
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(80)

        assert ahk.click.call_count == 1
        assert ahk.click.call_args.args[:2] == (1, 1)
        assert not engine.is_running()

    def test_if_false_runs_else_branch_only(self, make_engine):
        from src.models.action import IfBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None
        macro = _macro([
            IfBlock(
                condition=self._cond(),
                then_actions=[ClickAction(x=1, y=1)],
                else_actions=[ClickAction(x=2, y=2)],
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(80)

        assert ahk.click.call_count == 1
        assert ahk.click.call_args.args[:2] == (2, 2)

    def test_if_false_without_else_skips_block(self, make_engine):
        from src.models.action import IfBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None
        macro = _macro([
            IfBlock(condition=self._cond(), then_actions=[ClickAction(x=1, y=1)]),
            ClickAction(x=9, y=9),
        ])

        engine.run_macro(macro)
        QTest.qWait(80)

        assert ahk.click.call_count == 1
        assert ahk.click.call_args.args[:2] == (9, 9)

    def test_negated_condition_inverts_branching(self, make_engine):
        from src.models.action import IfBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None  # not found + negate -> true
        macro = _macro([
            IfBlock(
                condition=self._cond(negate=True),
                then_actions=[ClickAction(x=1, y=1)],
                else_actions=[ClickAction(x=2, y=2)],
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(80)

        assert ahk.click.call_args.args[:2] == (1, 1)

    def test_condition_passes_region_and_variation_to_service(self, make_engine, monkeypatch, tmp_path):
        from src.models.action import IfBlock, ImageCondition
        from src.core import constants as constants_module
        engine, ahk, state = make_engine()
        monkeypatch.setattr(constants_module, "get_assets_dir", lambda: tmp_path)
        ahk.image_search.return_value = None
        cond = ImageCondition(
            image_file="ref.png", x1=-100, y1=20, x2=300, y2=260, color_variation=42
        )
        macro = _macro([IfBlock(condition=cond)])

        engine.run_macro(macro)
        QTest.qWait(80)

        args = ahk.image_search.call_args.args
        assert args[0] == str(tmp_path / "ref.png")
        assert args[1:] == (-100, 20, 300, 260)
        assert ahk.image_search.call_args.kwargs["color_variation"] == 42

    def test_while_repeats_until_condition_false(self, make_engine):
        from src.models.action import WhileBlock
        engine, ahk, state = make_engine()
        ahk.image_search.side_effect = [(1, 1), (1, 1), None]
        macro = _macro([
            WhileBlock(
                condition=self._cond(),
                actions=[ClickAction(x=1, y=1)],
                check_interval_ms=0,
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(150)

        assert ahk.click.call_count == 2
        assert ahk.image_search.call_count == 3
        assert not engine.is_running()

    def test_while_max_iterations_cap(self, make_engine):
        from src.models.action import WhileBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = (1, 1)  # always found
        macro = _macro([
            WhileBlock(
                condition=self._cond(),
                actions=[ClickAction(x=1, y=1)],
                max_iterations=3,
                check_interval_ms=0,
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(150)

        assert ahk.click.call_count == 3
        assert not engine.is_running()

    def test_while_timeout_cap(self, make_engine):
        from src.models.action import WhileBlock
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = (1, 1)  # never turns false
        macro = _macro([
            WhileBlock(
                condition=self._cond(),
                actions=[DelayAction(duration_ms=30)],
                timeout_seconds=1,
                check_interval_ms=0,
            ),
        ])

        engine.run_macro(macro)
        QTest.qWait(1400)

        assert not engine.is_running()

    def test_while_state_resets_across_outer_repeat(self, make_engine):
        from src.models.action import WhileBlock
        engine, ahk, state = make_engine()
        # Always found; max_iterations=1 exits each entry by cap after one
        # pass WITHOUT re-evaluating the condition, so each macro repeat
        # consumes exactly one search and one click.
        ahk.image_search.return_value = (1, 1)
        macro = _macro(
            [
                WhileBlock(
                    condition=self._cond(),
                    actions=[ClickAction(x=1, y=1)],
                    max_iterations=1,
                    check_interval_ms=0,
                ),
            ],
            repeat_count=2,
        )

        engine.run_macro(macro)
        QTest.qWait(200)

        # max_iterations=1 per entry: if the iteration counter leaked across
        # the repeat wrap, the second pass would exit immediately by cap with
        # only 1 total click.
        assert ahk.click.call_count == 2
        assert ahk.image_search.call_count == 2
        assert not engine.is_running()

    def test_wait_polls_until_found(self, make_engine):
        from src.models.action import WaitAction
        engine, ahk, state = make_engine()
        ahk.image_search.side_effect = [None, None, (1, 1)]
        macro = _macro([
            WaitAction(condition=self._cond(), poll_interval_ms=20),
            ClickAction(x=9, y=9),
        ])

        engine.run_macro(macro)
        QTest.qWait(300)

        assert ahk.image_search.call_count == 3
        assert ahk.click.call_count == 1
        assert not engine.is_running()

    def test_wait_timeout_continue_proceeds(self, make_engine):
        from src.models.action import WaitAction
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None  # never appears
        macro = _macro([
            WaitAction(
                condition=self._cond(),
                poll_interval_ms=20,
                timeout_ms=100,
                on_timeout="continue",
            ),
            ClickAction(x=9, y=9),
        ])

        engine.run_macro(macro)
        QTest.qWait(400)

        assert ahk.click.call_count == 1
        assert not engine.is_running()
        assert state.get() == AppState.IDLE

    def test_wait_timeout_error_stops_macro_and_releases_keys(self, make_engine):
        from src.models.action import WaitAction
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None
        errors = []
        macro = _macro([
            KeyPressAction(key="shift", action_type=ActionType.KEY_HOLD),
            WaitAction(
                condition=self._cond(),
                poll_interval_ms=20,
                timeout_ms=100,
                on_timeout="error",
            ),
            ClickAction(x=9, y=9),
        ])

        engine, ahk, state = engine, ahk, state
        engine.macro_error.connect(lambda mid, msg: errors.append(msg))
        ahk.image_search.return_value = None

        engine.run_macro(macro)
        QTest.qWait(400)

        assert errors and "Timed out" in errors[0]
        assert ahk.click.call_count == 0
        ahk.key_up.assert_any_call("shift")  # held key force-released
        assert state.get() == AppState.ERROR

    def test_wait_emits_action_started_once(self, make_engine):
        from src.models.action import WaitAction
        engine, ahk, state = make_engine()
        ahk.image_search.side_effect = [None, None, (1, 1)]
        started = []
        wait = WaitAction(condition=self._cond(), poll_interval_ms=20)
        macro = _macro([wait])

        engine.action_started.connect(lambda aid, atype: started.append(aid))
        engine.run_macro(macro)
        QTest.qWait(300)

        assert started.count(wait.id) == 1

    def test_stop_mid_wait_goes_idle(self, make_engine):
        from src.models.action import WaitAction
        engine, ahk, state = make_engine()
        ahk.image_search.return_value = None
        macro = _macro([
            WaitAction(condition=self._cond(), poll_interval_ms=20),
        ])

        engine.run_macro(macro)
        QTest.qWait(60)
        assert engine.is_running()

        engine.stop_macro()
        searches = ahk.image_search.call_count
        QTest.qWait(100)

        assert not engine.is_running()
        assert state.get() == AppState.IDLE
        assert ahk.image_search.call_count == searches  # no stray polls
