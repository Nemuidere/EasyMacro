"""
Tests for ConfigManager and the shared config-path resolution.

Covers:
- Round-trip save/load of AppSettings.
- Tolerance of a corrupt/empty config file.
- Regression for the settings/dashboard split-config bug: every component must
  resolve the *same* config path. The settings page previously computed
  ``<repo>/src/data/config.json`` (off-by-one) while the app read
  ``<repo>/data/config.json``, so saved settings were invisible to the
  dashboard.
"""

from pathlib import Path

import pytest

from src.core.config import ConfigManager
from src.core.constants import (
    get_config_path,
    get_data_dir,
    get_macros_path,
    get_stats_path,
)
from src.models.settings import AppSettings, Theme


def test_config_path_is_under_data_not_src():
    """The canonical config path lives in <root>/data, never under src/."""
    path = get_config_path()
    assert path.name == "config.json"
    assert path.parent == get_data_dir()
    assert path.parent.name == "data"
    # The historical bug pointed at .../src/data/config.json.
    assert "src" not in path.parent.parts[-2:]


def test_data_paths_share_one_directory():
    """Config, macros and stats all resolve under the same data dir."""
    data_dir = get_data_dir()
    assert get_config_path().parent == data_dir
    assert get_macros_path().parent == data_dir
    assert get_stats_path().parent == data_dir


def test_save_then_load_round_trips(tmp_path):
    """Saving settings and loading them back yields equal values."""
    config_path = tmp_path / "config.json"
    manager = ConfigManager(config_path)

    settings = AppSettings(theme=Theme.LIGHT, mouse_movement_threshold=123)
    manager.save(settings)

    loaded = manager.load(AppSettings)
    assert loaded.theme == Theme.LIGHT
    assert loaded.mouse_movement_threshold == 123


def test_two_managers_same_path_see_each_others_writes(tmp_path):
    """A second manager on the same path reads the first manager's save.

    This is the exact interaction the settings page (writer) and the dashboard
    (reader) rely on; it only works when both point at the same file.
    """
    config_path = tmp_path / "config.json"
    writer = ConfigManager(config_path)
    reader = ConfigManager(config_path)

    writer.save(AppSettings(mouse_movement_threshold=250))

    assert reader.load(AppSettings).mouse_movement_threshold == 250


def test_load_tolerates_corrupt_json(tmp_path):
    """A corrupt config file falls back to defaults rather than raising."""
    config_path = tmp_path / "config.json"
    config_path.write_text("{ this is not valid json ")

    loaded = ConfigManager(config_path).load(AppSettings)
    defaults = AppSettings()
    assert loaded.theme == defaults.theme
    assert loaded.mouse_movement_threshold == defaults.mouse_movement_threshold
    assert loaded.randomization.jitter_radius == defaults.randomization.jitter_radius
