"""
Pytest fixtures for EasyMacro tests.

Provides common fixtures for testing.
"""

import pytest
from pathlib import Path
import tempfile
import json
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from src.models.settings import AppSettings, RandomizationSettings, HotkeySettings
from src.models.macro import Macro, MacroStatus
from src.models.action import ClickAction, DelayAction, ActionType
from src.core.config import ConfigManager
from src.core.state import StateManager, init_state_manager, get_state_manager
from src.core.event_bus import EventBus, init_event_bus, get_event_bus
from src.core.randomization import RandomizationEngine, init_randomization_engine
from src.core.logger import setup_logger


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for the test session.
    
    Yields:
        QApplication instance.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit - let other tests use it


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests.
    
    Yields:
        Path to temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config file.
    
    Args:
        temp_dir: Temporary directory fixture.
    
    Yields:
        Path to config file.
    """
    config_path = temp_dir / "config.json"
    config_path.write_text("{}")
    yield config_path


@pytest.fixture
def temp_macros_file(temp_dir):
    """Create a temporary macros file.
    
    Args:
        temp_dir: Temporary directory fixture.
    
    Yields:
        Path to macros file.
    """
    macros_path = temp_dir / "macros.json"
    macros_path.write_text("[]")
    yield macros_path


@pytest.fixture
def default_settings():
    """Create default app settings.
    
    Returns:
        AppSettings with defaults.
    """
    return AppSettings()


@pytest.fixture
def randomization_settings():
    """Create default randomization settings.
    
    Returns:
        RandomizationSettings with defaults.
    """
    return RandomizationSettings()


@pytest.fixture
def sample_macro():
    """Create a sample macro for testing.
    
    Returns:
        Macro with sample actions.
    """
    return Macro(
        name="Test Macro",
        description="A test macro",
        actions=[
            ClickAction(x=100, y=200, button="left"),
            DelayAction(duration_ms=1000),
        ],
        hotkey="ctrl+shift+a",
        enabled=True,
    )


@pytest.fixture
def sample_click_action():
    """Create a sample click action.
    
    Returns:
        ClickAction instance.
    """
    return ClickAction(x=100, y=200, button="left", jitter_radius=5)


@pytest.fixture
def sample_delay_action():
    """Create a sample delay action.
    
    Returns:
        DelayAction instance.
    """
    return DelayAction(duration_ms=1000, variance_percent=20)


@pytest.fixture
def initialized_event_bus():
    """Initialize and return an event bus.
    
    Yields:
        EventBus instance.
    """
    # Reset singleton
    import src.core.event_bus as event_bus_module
    event_bus_module._event_bus = None
    
    bus = init_event_bus()
    yield bus
    
    # Cleanup
    event_bus_module._event_bus = None


@pytest.fixture
def initialized_state_manager():
    """Initialize and return a state manager.
    
    Yields:
        StateManager instance.
    """
    # Reset singleton
    import src.core.state as state_module
    state_module._state_manager = None
    
    manager = init_state_manager()
    yield manager
    
    # Cleanup
    state_module._state_manager = None


@pytest.fixture
def initialized_randomization_engine(randomization_settings):
    """Initialize and return a randomization engine.
    
    Args:
        randomization_settings: Randomization settings fixture.
    
    Yields:
        RandomizationEngine instance.
    """
    # Reset singleton
    import src.core.randomization as rand_module
    rand_module._randomization_engine = None
    
    engine = init_randomization_engine(randomization_settings)
    yield engine
    
    # Cleanup
    rand_module._randomization_engine = None


@pytest.fixture
def mock_ahk():
    """Create a mock AHK service.
    
    Returns:
        MagicMock for AHK service.
    """
    mock = MagicMock()
    mock.click = MagicMock()
    mock.mouse_move = MagicMock()
    mock.key_press = MagicMock()
    mock.key_down = MagicMock()
    mock.key_up = MagicMock()
    return mock


@pytest.fixture
def mock_hotkey_listener():
    """Create a mock hotkey listener.
    
    Returns:
        MagicMock for pynput keyboard listener.
    """
    with patch("pynput.keyboard.Listener") as mock_listener:
        listener = MagicMock()
        listener.start = MagicMock()
        listener.stop = MagicMock()
        mock_listener.return_value = listener
        yield listener
