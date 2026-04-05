"""
Settings page for EasyMacro.

Allows configuration of application settings with scrollable layout.
"""

import sys
from typing import Optional, Dict
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
    QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.models.settings import AppSettings, RandomizationSettings, HotkeySettings, Theme
from src.core.config import ConfigManager
from src.core.randomization import get_randomization_engine
from src.core.logger import get_logger
from src.ui.widgets.hotkey_input import HotkeyInput


def get_config_path() -> Path:
    """Get absolute path to config file."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = Path(sys.executable).parent
    else:
        # Running as script
        app_dir = Path(__file__).parent.parent.parent
    return app_dir / "data" / "config.json"


class SettingsPage(QWidget):
    """
    Settings page for configuring EasyMacro.
    
    Displays:
    - Safety settings (stop on mouse movement)
    - Randomization defaults
    - Global hotkey bindings (configurable)
    - Theme selection
    - Application preferences
    
    Features scrollable layout to handle many settings.
    """
    
    # Signals
    settings_saved = Signal()
    hotkey_conflict = Signal(str, str)  # hotkey, action
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize settings page.
        
        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._logger = get_logger("settings_page")
        
        self._hotkey_inputs: Dict[str, HotkeyInput] = {}
        
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
    
    def _setup_ui(self) -> None:
        """Set up the user interface with scrollable layout."""
        # Main layout for this widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # Create content widget
        content_widget = QWidget()
        content_widget.setObjectName("settingsContent")
        
        layout = QVBoxLayout(content_widget)
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
        
        # Application settings group
        app_group = QGroupBox("Application")
        app_group.setMinimumWidth(400)
        app_layout = QFormLayout(app_group)
        app_layout.setSpacing(10)
        
        self._start_minimized = QCheckBox("Start minimized to tray")
        app_layout.addRow(self._start_minimized)
        
        self._close_to_tray = QCheckBox("Close to system tray")
        self._close_to_tray.setChecked(True)
        app_layout.addRow(self._close_to_tray)
        
        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(True)
        app_layout.addRow(self._check_updates)
        
        # Safety features - Stop on mouse movement
        self._stop_on_mouse_move = QCheckBox("Stop on Mouse Movement")
        self._stop_on_mouse_move.setChecked(True)
        self._stop_on_mouse_move.setToolTip(
            "Automatically stop running macros when mouse moves significantly"
        )
        app_layout.addRow(self._stop_on_mouse_move)
        
        # Mouse movement threshold
        self._mouse_threshold = QSpinBox()
        self._mouse_threshold.setRange(0, 500)
        self._mouse_threshold.setValue(50)
        self._mouse_threshold.setSuffix(" px")
        self._mouse_threshold.setToolTip(
            "Distance in pixels before macro is stopped (0-500)"
        )
        app_layout.addRow("Mouse Movement Threshold:", self._mouse_threshold)
        
        layout.addWidget(app_group)
        
        # Safety settings group
        safety_group = QGroupBox("Safety Features")
        safety_group.setMinimumWidth(400)
        safety_layout = QVBoxLayout(safety_group)
        
        safety_info = QLabel(
            "Macro execution can be interrupted by moving your mouse "
            "beyond the configured threshold distance."
        )
        safety_info.setWordWrap(True)
        safety_info.setStyleSheet("color: #888; font-size: 12px;")
        safety_layout.addWidget(safety_info)
        
        layout.addWidget(safety_group)
        
        # Randomization settings group (for defaults)
        randomization_group = QGroupBox("Randomization Defaults")
        randomization_group.setMinimumWidth(400)
        randomization_group.setToolTip(
            "Default randomization settings for new macros"
        )
        randomization_layout = QFormLayout(randomization_group)
        randomization_layout.setSpacing(10)
        
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
        
        randomization_info = QLabel(
            "These settings are used as defaults when creating new macros."
        )
        randomization_info.setWordWrap(True)
        randomization_info.setStyleSheet("color: #888; font-size: 12px;")
        randomization_layout.addRow(randomization_info)
        
        layout.addWidget(randomization_group)
        
        # Hotkey settings group (configurable)
        hotkey_group = QGroupBox("Global Hotkeys")
        hotkey_group.setMinimumWidth(400)
        hotkey_group.setToolTip("Configure global keyboard shortcuts")
        hotkey_layout = QVBoxLayout(hotkey_group)
        hotkey_layout.setSpacing(15)
        
        hotkey_info = QLabel(
            "Click 'Capture' on any hotkey below, then press your desired key combination."
        )
        hotkey_info.setWordWrap(True)
        hotkey_info.setStyleSheet("color: #888; font-size: 12px;")
        hotkey_layout.addWidget(hotkey_info)
        
        # Pause All hotkey
        self._pause_hotkey_input = HotkeyInput(
            label="Pause All Macros",
            input_id="pause_all",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        self._hotkey_inputs["pause_all"] = self._pause_hotkey_input
        hotkey_layout.addWidget(self._pause_hotkey_input)

        # Resume All hotkey
        self._resume_hotkey_input = HotkeyInput(
            label="Resume All Macros",
            input_id="resume_all",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        self._hotkey_inputs["resume_all"] = self._resume_hotkey_input
        hotkey_layout.addWidget(self._resume_hotkey_input)

        # Stop All hotkey
        self._stop_hotkey_input = HotkeyInput(
            label="Stop All Macros",
            input_id="stop_all",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        self._hotkey_inputs["stop_all"] = self._stop_hotkey_input
        hotkey_layout.addWidget(self._stop_hotkey_input)

        # Capture Position hotkey
        self._capture_pos_hotkey_input = HotkeyInput(
            label="Capture Position",
            input_id="capture_position",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        self._hotkey_inputs["capture_position"] = self._capture_pos_hotkey_input
        hotkey_layout.addWidget(self._capture_pos_hotkey_input)

        # Cancel Capture hotkey
        self._cancel_capture_hotkey_input = HotkeyInput(
            label="Cancel Capture",
            input_id="cancel_capture",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        self._hotkey_inputs["cancel_capture"] = self._cancel_capture_hotkey_input
        hotkey_layout.addWidget(self._cancel_capture_hotkey_input)
        
        layout.addWidget(hotkey_group)
        
        # Appearance settings group
        appearance_group = QGroupBox("Appearance")
        appearance_group.setMinimumWidth(400)
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)
        
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", Theme.DARK.value)
        self._theme_combo.addItem("Light", Theme.LIGHT.value)
        self._theme_combo.addItem("System", Theme.SYSTEM.value)
        appearance_layout.addRow("Theme:", self._theme_combo)
        
        layout.addWidget(appearance_group)
        
        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._save_button = QPushButton("Save Settings")
        self._save_button.setObjectName("primaryButton")
        button_layout.addWidget(self._save_button)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        # Set content widget on scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._save_button.clicked.connect(self._on_save_clicked)
        self._stop_on_mouse_move.toggled.connect(self._on_stop_on_mouse_move_toggled)

    def _on_stop_on_mouse_move_toggled(self, enabled: bool) -> None:
        """Handle stop on mouse movement toggle.

        Args:
            enabled: Whether stop on mouse movement is enabled.
        """
        self._mouse_threshold.setEnabled(enabled)
    
    def _check_hotkey_conflict(self, hotkey: str, input_id: str) -> bool:
        """Check if hotkey conflicts with existing bindings.

        Args:
            hotkey: Hotkey string to check.
            input_id: ID of the input widget making the check (excluded from conflict check).

        Returns:
            True if no conflict, False to reject.
        """
        if not hotkey:
            return True

        for key_name, input_widget in self._hotkey_inputs.items():
            if key_name != input_id and input_widget.get_hotkey() == hotkey:
                self._logger.warning(f"Hotkey conflict: {hotkey} already used by {key_name}")
                return False

        return True
    
    def _load_settings(self) -> None:
        """Load settings from config."""
        try:
            config_path = get_config_path()
            config_manager = ConfigManager(config_path)
            settings = config_manager.load(AppSettings)
            

            
            # Load application settings
            self._start_minimized.setChecked(settings.start_minimized)
            self._close_to_tray.setChecked(settings.close_to_tray)
            self._check_updates.setChecked(settings.check_updates)
            self._stop_on_mouse_move.setChecked(settings.stop_on_mouse_movement)
            self._mouse_threshold.setValue(settings.mouse_movement_threshold)
            
            # Load randomization settings
            self._jitter_radius.setValue(settings.randomization.jitter_radius)
            self._timing_variance.setValue(settings.randomization.timing_variance_percent)
            self._speed_variation.setValue(settings.randomization.mouse_speed_variation)
            
            # Load hotkey settings
            hotkeys = settings.hotkeys
            self._pause_hotkey_input.set_hotkey(hotkeys.pause_all)
            self._resume_hotkey_input.set_hotkey(hotkeys.resume_all)
            self._stop_hotkey_input.set_hotkey(hotkeys.stop_all)
            self._capture_pos_hotkey_input.set_hotkey(hotkeys.capture_position_key)
            self._cancel_capture_hotkey_input.set_hotkey(hotkeys.cancel_capture_key)
            
            # Load theme
            theme_index = self._theme_combo.findData(settings.theme.value)
            if theme_index >= 0:
                self._theme_combo.setCurrentIndex(theme_index)
            
            self._logger.info("Settings loaded successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to load settings: {e}")
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        try:
            # Validate hotkeys
            if not self._validate_hotkeys():
                return
            
            # Get current settings
            settings = AppSettings(
                theme=Theme(self._theme_combo.currentData()),
                randomization=RandomizationSettings(
                    enabled=True,  # Always enabled for defaults
                    jitter_radius=self._jitter_radius.value(),
                    timing_variance_percent=self._timing_variance.value(),
                    mouse_speed_variation=self._speed_variation.value(),
                ),
                hotkeys=HotkeySettings(
                    pause_all=self._pause_hotkey_input.get_hotkey(),
                    resume_all=self._resume_hotkey_input.get_hotkey(),
                    stop_all=self._stop_hotkey_input.get_hotkey(),
                    capture_position_key=self._capture_pos_hotkey_input.get_hotkey(),
                    cancel_capture_key=self._cancel_capture_hotkey_input.get_hotkey(),
                ),
                start_minimized=self._start_minimized.isChecked(),
                close_to_tray=self._close_to_tray.isChecked(),
                check_updates=self._check_updates.isChecked(),
                stop_on_mouse_movement=self._stop_on_mouse_move.isChecked(),
                mouse_movement_threshold=self._mouse_threshold.value(),
            )
            
            # Save to config
            config_path = get_config_path()
            config_manager = ConfigManager(config_path)
            config_manager.save(settings)
            
            # Update randomization engine
            engine = get_randomization_engine()
            engine.update_settings(settings.randomization)
            
            self._logger.info("Settings saved")
            self.settings_saved.emit()
            
            # Show success message
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Settings Saved")
            msg.setText("Your settings have been saved successfully.")
            msg.exec()
            
        except Exception as e:
            self._logger.error(f"Failed to save settings: {e}")
            
            # Show error message
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Error")
            msg.setText("Failed to save settings.")
            msg.setDetailedText(str(e))
            msg.exec()
    
    def _validate_hotkeys(self) -> bool:
        """Validate that all required hotkeys are set.
        
        Returns:
            True if all valid.
        """
        required_hotkeys = {
            "pause_all": self._pause_hotkey_input,
            "resume_all": self._resume_hotkey_input,
            "stop_all": self._stop_hotkey_input,
        }
        
        missing = []
        for name, input_widget in required_hotkeys.items():
            if not input_widget.get_hotkey():
                missing.append(name.replace("_", " ").title())
        
        if missing:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Missing Hotkeys")
            msg.setText(
                f"The following required hotkeys are not set:\n\n"
                f"{', '.join(missing)}\n\n"
                f"Please configure all required hotkeys before saving."
            )
            msg.exec()
            return False
        
        return True
    
    def refresh(self) -> None:
        """Refresh the settings page."""
        self._load_settings()
    
    def hideEvent(self, event) -> None:
        """Handle hide event - stop any active captures."""
        for input_widget in self._hotkey_inputs.values():
            if input_widget.is_capturing():
                input_widget.stop_capture()
        super().hideEvent(event)
    
    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        for input_widget in self._hotkey_inputs.values():
            input_widget.cleanup()
