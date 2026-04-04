"""
Settings page for EasyMacro.

Allows configuration of application settings.
"""

from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.models.settings import AppSettings, RandomizationSettings, Theme
from src.core.config import ConfigManager
from src.core.randomization import get_randomization_engine
from src.core.logger import get_logger


class SettingsPage(QWidget):
    """
    Settings page for configuring EasyMacro.
    
    Displays:
    - Randomization settings
    - Hotkey bindings
    - Theme selection
    - Application preferences
    """
    
    # Signals
    settings_saved = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize settings page.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._logger = get_logger("settings_page")
        
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Page title
        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(title)
        
        subtitle = QLabel("Configure EasyMacro preferences")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        
        # Randomization settings
        randomization_group = QGroupBox("Randomization")
        randomization_layout = QFormLayout(randomization_group)
        
        self._randomization_enabled = QCheckBox("Enable randomization")
        self._randomization_enabled.setChecked(True)
        randomization_layout.addRow(self._randomization_enabled)
        
        self._jitter_radius = QSpinBox()
        self._jitter_radius.setRange(0, 50)
        self._jitter_radius.setValue(5)
        self._jitter_radius.setSuffix(" px")
        randomization_layout.addRow("Jitter Radius:", self._jitter_radius)
        
        self._timing_variance = QSpinBox()
        self._timing_variance.setRange(0, 100)
        self._timing_variance.setValue(20)
        self._timing_variance.setSuffix(" %")
        randomization_layout.addRow("Timing Variance:", self._timing_variance)
        
        self._speed_variation = QSpinBox()
        self._speed_variation.setRange(0, 50)
        self._speed_variation.setValue(10)
        self._speed_variation.setSuffix(" %")
        randomization_layout.addRow("Speed Variation:", self._speed_variation)
        
        layout.addWidget(randomization_group)
        
        # Hotkey settings
        hotkey_group = QGroupBox("Hotkeys")
        hotkey_layout = QFormLayout(hotkey_group)
        
        self._pause_hotkey = QLabel("Ctrl+Shift+P")
        hotkey_layout.addRow("Pause All:", self._pause_hotkey)
        
        self._resume_hotkey = QLabel("Ctrl+Shift+R")
        hotkey_layout.addRow("Resume All:", self._resume_hotkey)
        
        self._stop_hotkey = QLabel("Ctrl+Shift+S")
        hotkey_layout.addRow("Stop All:", self._stop_hotkey)
        
        # TODO: Add hotkey capture widgets
        
        layout.addWidget(hotkey_group)
        
        # Appearance settings
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", Theme.DARK.value)
        self._theme_combo.addItem("Light", Theme.LIGHT.value)
        self._theme_combo.addItem("System", Theme.SYSTEM.value)
        appearance_layout.addRow("Theme:", self._theme_combo)
        
        layout.addWidget(appearance_group)
        
        # Application settings
        app_group = QGroupBox("Application")
        app_layout = QFormLayout(app_group)
        
        self._start_minimized = QCheckBox("Start minimized to tray")
        app_layout.addRow(self._start_minimized)
        
        self._close_to_tray = QCheckBox("Close to system tray")
        self._close_to_tray.setChecked(True)
        app_layout.addRow(self._close_to_tray)
        
        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(True)
        app_layout.addRow(self._check_updates)
        
        layout.addWidget(app_group)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._save_button = QPushButton("Save Settings")
        self._save_button.setObjectName("primaryButton")
        button_layout.addWidget(self._save_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._save_button.clicked.connect(self._on_save_clicked)
        self._randomization_enabled.toggled.connect(self._on_randomization_toggled)
    
    def _load_settings(self) -> None:
        """Load settings from config."""
        # TODO: Load from ConfigManager
        pass
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        try:
            # Get current settings
            settings = AppSettings(
                theme=Theme(self._theme_combo.currentData()),
                randomization=RandomizationSettings(
                    enabled=self._randomization_enabled.isChecked(),
                    jitter_radius=self._jitter_radius.value(),
                    timing_variance_percent=self._timing_variance.value(),
                    mouse_speed_variation=self._speed_variation.value(),
                ),
                start_minimized=self._start_minimized.isChecked(),
                close_to_tray=self._close_to_tray.isChecked(),
                check_updates=self._check_updates.isChecked(),
            )

            # Save to config
            config_path = Path("data/config.json")
            config_manager = ConfigManager(config_path)
            config_manager.save(settings)

            # Update randomization engine
            engine = get_randomization_engine()
            engine.update_settings(settings.randomization)

            self._logger.info("Settings saved")
            self.settings_saved.emit()

        except Exception as e:
            self._logger.error(f"Failed to save settings: {e}")
    
    def _on_randomization_toggled(self, enabled: bool) -> None:
        """Handle randomization toggle.
        
        Args:
            enabled: Whether randomization is enabled.
        """
        self._jitter_radius.setEnabled(enabled)
        self._timing_variance.setEnabled(enabled)
        self._speed_variation.setEnabled(enabled)
    
    def refresh(self) -> None:
        """Refresh the settings page."""
        self._load_settings()
