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
from src.models.action import ClickAction, DelayAction


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
