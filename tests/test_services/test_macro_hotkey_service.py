"""
Integration tests for MacroHotkeyService.

Cover the two behaviours that were previously broken/missing:
  - a macro's hotkey toggles its run on/off (and runs via the engine on the
    main thread, not the pynput listener thread);
  - the global stop hotkey is registered and stops the engine.

The pynput callback is invoked directly (as the listener thread would) and we
pump the Qt event loop so the queued, main-thread slots run.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtTest import QTest

import src.core.event_bus as event_bus_module
import src.core.state as state_module
import src.core.randomization as rand_module
import src.core.macro_engine as engine_module

from src.core.event_bus import init_event_bus, get_event_bus
from src.core.state import init_state_manager, get_state_manager
from src.core.randomization import init_randomization_engine, get_randomization_engine
from src.core.macro_engine import init_macro_engine, get_macro_engine
from src.core.hotkey_manager import HotkeyManager
from src.services.macro_service import MacroService
from src.services.macro_hotkey_service import MacroHotkeyService
from src.models.settings import RandomizationSettings, HotkeySettings
from src.models.macro import Macro
from src.models.action import ClickAction, DelayAction


@pytest.fixture
def wired(qapp, monkeypatch, tmp_path):
    """Build the full hotkey -> engine wiring with a mocked AHK service."""
    # Reset singletons so each test starts clean.
    for mod, attr in (
        (event_bus_module, "_event_bus"),
        (state_module, "_state_manager"),
        (rand_module, "_randomization_engine"),
        (engine_module, "_macro_engine"),
    ):
        setattr(mod, attr, None)

    init_event_bus()
    init_state_manager()
    init_randomization_engine(RandomizationSettings(enabled=False))

    ahk = MagicMock()
    ahk.get_mouse_position.return_value = (0, 0)
    monkeypatch.setattr("src.services.ahk_service.get_ahk_service", lambda: ahk)

    init_macro_engine(
        get_randomization_engine(), get_state_manager(), MagicMock(), None
    )

    macros_path = tmp_path / "macros.json"
    macros_path.write_text("[]")
    macro_service = MacroService(macros_path)

    macro = Macro(
        name="Looper",
        hotkey="f8",
        actions=[ClickAction(x=1, y=2), DelayAction(duration_ms=15)],
        repeat_count=0,
        randomization_enabled=False,
    )
    macro_service.save(macro)

    hotkey_manager = HotkeyManager()
    service = MacroHotkeyService()
    service.initialize(hotkey_manager, macro_service, get_event_bus())
    service.register_macro(macro)

    yield service, hotkey_manager, macro, ahk

    # Cleanup singletons.
    get_macro_engine().stop_macro()
    for mod, attr in (
        (engine_module, "_macro_engine"),
        (rand_module, "_randomization_engine"),
        (state_module, "_state_manager"),
        (event_bus_module, "_event_bus"),
    ):
        setattr(mod, attr, None)


def test_macro_hotkey_toggles_run(wired):
    service, hotkey_manager, macro, ahk = wired
    engine = get_macro_engine()

    callback = service._macro_callbacks[macro.id]

    # First press starts the macro (queued onto the main thread).
    callback()
    QTest.qWait(60)
    assert engine.is_running()
    assert ahk.click.call_count >= 1

    # Second press of the same hotkey toggles it off.
    callback()
    QTest.qWait(60)
    assert not engine.is_running()


def test_global_stop_hotkey_stops_engine(wired):
    service, hotkey_manager, macro, ahk = wired
    engine = get_macro_engine()

    service.register_global_hotkeys(
        HotkeySettings(
            pause_all="ctrl+shift+p",
            resume_all="ctrl+shift+r",
            stop_all="ctrl+shift+s",
        )
    )
    assert hotkey_manager.is_registered("ctrl+shift+s")

    # Start the macro, then trigger the global stop callback.
    service._macro_callbacks[macro.id]()
    QTest.qWait(60)
    assert engine.is_running()

    stop_callback = hotkey_manager._hotkeys["ctrl+shift+s"]
    stop_callback()
    QTest.qWait(60)
    assert not engine.is_running()
