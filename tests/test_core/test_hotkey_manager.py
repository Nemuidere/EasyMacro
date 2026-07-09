"""
Tests for HotkeyManager: normalization, registration bookkeeping and the
press/release matching that decides whether a hotkey actually fires.
"""

import pytest
from pynput.keyboard import Key, KeyCode

from src.core.hotkey_manager import HotkeyManager
from src.core.exceptions import HotkeyError, HotkeyConflictError


@pytest.fixture
def manager(qapp):
    return HotkeyManager()


# --- normalization ---------------------------------------------------------

def test_normalize_lowercases(manager):
    assert manager._normalize_hotkey("Ctrl+Shift+A") == "ctrl+shift+a"


def test_normalize_sorts_modifiers(manager):
    assert manager._normalize_hotkey("shift+ctrl+a") == "ctrl+shift+a"


@pytest.mark.parametrize("raw", ["cmd+a", "win+a"])
def test_normalize_maps_cmd_win_to_meta(manager, raw):
    assert manager._normalize_hotkey(raw) == "meta+a"


def test_normalize_single_key(manager):
    assert manager._normalize_hotkey("F1") == "f1"


# --- registration bookkeeping ---------------------------------------------

def test_register_and_is_registered(manager):
    manager.register("ctrl+a", "id1", lambda: None)
    assert manager.is_registered("ctrl+a")
    assert manager.is_registered("a+ctrl")  # order-independent
    assert "ctrl+a" in manager.get_registered_hotkeys()


def test_duplicate_registration_conflicts(manager):
    manager.register("ctrl+a", "id1", lambda: None)
    with pytest.raises(HotkeyConflictError):
        manager.register("ctrl+a", "id2", lambda: None)


def test_unregister_removes(manager):
    manager.register("ctrl+a", "id1", lambda: None)
    manager.unregister("ctrl+a")
    assert not manager.is_registered("ctrl+a")


def test_unregister_missing_raises(manager):
    with pytest.raises(HotkeyError):
        manager.unregister("ctrl+z")


def test_register_empty_or_no_callback_raises(manager):
    with pytest.raises(ValueError):
        manager.register("", "id", lambda: None)
    with pytest.raises(ValueError):
        manager.register("ctrl+a", "id", None)


# --- press/release matching ------------------------------------------------

def test_modifier_combo_fires_callback(manager):
    fired = []
    manager.register("ctrl+a", "id1", lambda: fired.append(True))

    manager._on_key_press(Key.ctrl)          # modifier held
    manager._on_key_press(KeyCode(char="a"))  # main key

    assert fired == [True]


def test_modifier_alone_does_not_fire(manager):
    fired = []
    manager.register("ctrl+a", "id1", lambda: fired.append(True))

    manager._on_key_press(Key.ctrl)
    assert fired == []


def test_release_modifier_stops_matching(manager):
    fired = []
    manager.register("ctrl+a", "id1", lambda: fired.append(True))

    manager._on_key_press(Key.ctrl)
    manager._on_key_release(Key.ctrl)
    manager._on_key_press(KeyCode(char="a"))  # ctrl no longer held

    assert fired == []


def test_plain_key_fires(manager):
    fired = []
    manager.register("f1", "id1", lambda: fired.append(True))

    manager._on_key_press(Key.f1)
    assert fired == [True]


def test_unrelated_key_does_not_fire(manager):
    fired = []
    manager.register("ctrl+a", "id1", lambda: fired.append(True))

    manager._on_key_press(Key.ctrl)
    manager._on_key_press(KeyCode(char="b"))
    assert fired == []
