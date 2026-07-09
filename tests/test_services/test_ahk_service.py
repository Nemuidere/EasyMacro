"""
Contract tests for AHKService.

The real ``AHK`` object (which spawns the AutoHotkey binary) is replaced with a
MagicMock so we can assert the exact command sequence the service issues — this
is the final layer that turns a macro action into real input, so getting the
button/click-count/modifier-order right is what "correct results" means.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.services.ahk_service as ahk_module
from src.services.ahk_service import AHKService
from src.core.exceptions import MacroExecutionError


@pytest.fixture
def service(monkeypatch):
    """An AHKService whose underlying AHK object is a mock (no binary spawned)."""
    monkeypatch.setattr(ahk_module, "AHK", MagicMock)
    svc = AHKService()
    svc._ahk = MagicMock()
    return svc


def test_sets_screen_coord_mode_on_init(monkeypatch):
    # A freshly constructed service must pin AHK mouse coords to Screen so
    # clicks are absolute, not relative to the active window.
    monkeypatch.setattr(ahk_module, "AHK", MagicMock)
    svc = AHKService()
    svc._ahk.set_coord_mode.assert_called_with("Mouse", "Screen")


def test_click_moves_then_clicks(service):
    service.click(100, 200, button="left", click_count=1)

    service._ahk.mouse_move.assert_called_once_with(100, 200, speed=0)
    service._ahk.click.assert_called_once_with(button="left", click_count=1)


def test_double_click_passes_count(service):
    service.click(10, 20, button="left", click_count=2)
    assert service._ahk.click.call_args.kwargs["click_count"] == 2


def test_click_right_button(service):
    service.click(10, 20, button="right")
    assert service._ahk.click.call_args.kwargs["button"] == "right"


def test_click_negative_coords_raise(service):
    with pytest.raises(ValueError):
        service.click(-1, 5)
    with pytest.raises(ValueError):
        service.click(5, -1)


def test_click_invalid_button_raises(service):
    with pytest.raises(ValueError):
        service.click(1, 1, button="scroll")


def test_mouse_move_smooth_uses_speed(service):
    service.mouse_move(10, 20, speed=7, smooth=True)
    service._ahk.mouse_move.assert_called_once_with(10, 20, speed=7)


def test_mouse_move_not_smooth_uses_zero_speed(service):
    service.mouse_move(10, 20, speed=7, smooth=False)
    service._ahk.mouse_move.assert_called_once_with(10, 20, speed=0)


def test_mouse_move_speed_out_of_range_raises(service):
    with pytest.raises(ValueError):
        service.mouse_move(10, 20, speed=0)
    with pytest.raises(ValueError):
        service.mouse_move(10, 20, speed=11)


def test_key_press_wraps_modifiers_in_order(service):
    service.key_press("a", modifiers=["ctrl", "shift"])

    ordered = [
        (c[0], c.args[0] if c.args else None)
        for c in service._ahk.mock_calls
        if c[0] in ("key_down", "key_up", "key_press")
    ]
    assert ordered == [
        ("key_down", "ctrl"),
        ("key_down", "shift"),
        ("key_press", "a"),
        ("key_up", "shift"),
        ("key_up", "ctrl"),
    ]


def test_key_press_empty_raises(service):
    with pytest.raises(ValueError):
        service.key_press("")


def test_key_down_and_up_delegate(service):
    service.key_down("shift")
    service.key_up("shift")
    service._ahk.key_down.assert_called_once_with("shift")
    service._ahk.key_up.assert_called_once_with("shift")


def test_get_mouse_position_returns_tuple(service):
    service._ahk.mouse_position = SimpleNamespace(x=3, y=4)
    assert service.get_mouse_position() == (3, 4)


def test_click_failure_wrapped(service):
    service._ahk.click.side_effect = RuntimeError("boom")
    with pytest.raises(MacroExecutionError):
        service.click(1, 1)
