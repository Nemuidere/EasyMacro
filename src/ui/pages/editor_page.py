"""
Macro editor page for EasyMacro.

Provides a comprehensive interface for creating and editing macros.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from src.models.macro import Macro
from src.models.action import ClickAction, DelayAction
from src.services.macro_service import get_macro_service
from src.services.position_capture_service import get_position_capture_service
from src.core.state import get_state_manager
from src.core.event_bus import get_event_bus
from src.core.logger import get_logger
from src.ui.widgets.hotkey_input import HotkeyInput


class EditorPage(QWidget):
    """
    Macro editor page for creating and editing macros.
    
    Features:
    - Position mode selection (cursor vs fixed)
    - Mouse position capture with F2 hotkey
    - Click interval configuration
    - Mouse button selection
    - Modifier key toggles
    - Randomization settings
    - Macro hotkey assignment
    
    Signals:
        save_requested: Emitted when macro is saved
        cancel_requested: Emitted when editing is cancelled
    """
    
    # Signals
    save_requested = Signal(Macro)
    cancel_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None, macro_id: Optional[str] = None):
        """Initialize editor page.
        
        Args:
            parent: Optional parent widget.
            macro_id: Optional macro ID for editing existing macro.
        """
        super().__init__(parent)
        self.setObjectName("editorPage")
        
        self._macro_id = macro_id
        self._existing_macro: Optional[Macro] = None
        self._is_editing = macro_id is not None
        self._is_cursor_mode = True  # Default to cursor mode
        self._modifiers: list[str] = []  # TODO: Will be added to ClickAction in Phase 4
        self._logger = get_logger("editor_page")
        
        self._setup_ui()
        self._connect_signals()
        
        if self._is_editing:
            self._load_macro(macro_id)
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Page title
        self._title_label = QLabel("Create Macro" if not self._is_editing else "Edit Macro")
        self._title_label.setObjectName("pageTitle")
        self._title_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(self._title_label)
        
        # Macro name field
        name_layout = QHBoxLayout()
        name_label = QLabel("Macro Name:")
        name_label.setFont(QFont("Segoe UI", 12))
        name_layout.addWidget(name_label)
        
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter macro name...")
        self._name_input.setFont(QFont("Segoe UI", 12))
        name_layout.addWidget(self._name_input)
        
        layout.addLayout(name_layout)
        
        # Hotkey input (HotkeyInput is a QGroupBox with its own title)
        self._hotkey_input = HotkeyInput(
            label="Macro Hotkey",
            input_id=f"macro_hotkey_{self._macro_id or 'new'}",
            parent=self,
            on_conflict=self._check_hotkey_conflict
        )
        layout.addWidget(self._hotkey_input)
        
        # Running macro indicator (shown when editing running macro)
        self._running_indicator = QLabel("Macro is currently running - stop it before editing")
        self._running_indicator.setObjectName("runningIndicator")
        self._running_indicator.setStyleSheet("color: green; font-weight: bold;")
        self._running_indicator.setVisible(False)
        layout.addWidget(self._running_indicator)
        
        # Position Settings Group
        position_group = QGroupBox("Position Settings")
        position_group.setFont(QFont("Segoe UI", 11, QFont.Bold))
        position_layout = QFormLayout()
        position_layout.setSpacing(15)
        
        # Position mode radio buttons
        mode_layout = QHBoxLayout()
        self._cursor_radio = QRadioButton("Cursor Position")
        self._cursor_radio.setChecked(True)
        self._fixed_radio = QRadioButton("Fixed Position")
        
        self._position_mode_group = QButtonGroup(self)
        self._position_mode_group.addButton(self._cursor_radio, 0)
        self._position_mode_group.addButton(self._fixed_radio, 1)
        
        mode_layout.addWidget(self._cursor_radio)
        mode_layout.addWidget(self._fixed_radio)
        mode_layout.addStretch()
        position_layout.addRow("Position Mode:", mode_layout)
        
        # X/Y coordinates (for fixed position)
        coord_layout = QHBoxLayout()
        
        x_label = QLabel("X:")
        self._x_spinbox = QSpinBox()
        self._x_spinbox.setRange(0, 9999)
        self._x_spinbox.setEnabled(False)
        
        y_label = QLabel("Y:")
        self._y_spinbox = QSpinBox()
        self._y_spinbox.setRange(0, 9999)
        self._y_spinbox.setEnabled(False)
        
        self._capture_button = QPushButton("Capture")
        self._capture_button.setToolTip("Click to capture mouse position (Press F2 to capture, Esc to cancel)")
        self._capture_button.setEnabled(False)

        coord_layout.addWidget(x_label)
        coord_layout.addWidget(self._x_spinbox)
        coord_layout.addSpacing(15)
        coord_layout.addWidget(y_label)
        coord_layout.addWidget(self._y_spinbox)
        coord_layout.addSpacing(15)
        coord_layout.addWidget(self._capture_button)
        coord_layout.addStretch()

        self._coord_container = QWidget()
        self._coord_container.setLayout(coord_layout)
        position_layout.addRow("Coordinates:", self._coord_container)

        position_group.setLayout(position_layout)
        layout.addWidget(position_group)

        # Click Settings Group
        click_group = QGroupBox("Click Settings")
        click_group.setFont(QFont("Segoe UI", 11, QFont.Bold))
        click_layout = QFormLayout()
        click_layout.setSpacing(15)

        # Click interval (seconds + milliseconds)
        interval_layout = QHBoxLayout()

        self._seconds_spinbox = QSpinBox()
        self._seconds_spinbox.setRange(0, 3600)
        self._seconds_spinbox.setValue(1)
        self._seconds_spinbox.setSuffix(" seconds")

        self._ms_spinbox = QSpinBox()
        self._ms_spinbox.setRange(0, 999)
        self._ms_spinbox.setSuffix(" ms")

        interval_layout.addWidget(self._seconds_spinbox)
        interval_layout.addWidget(self._ms_spinbox)
        interval_layout.addStretch()

        click_layout.addRow("Interval:", interval_layout)

        # Mouse button selector
        self._button_combo = QComboBox()
        self._button_combo.addItems(["Left", "Right", "Middle"])
        self._button_combo.setCurrentText("Left")
        click_layout.addRow("Mouse Button:", self._button_combo)

        click_group.setLayout(click_layout)
        layout.addWidget(click_group)

        # Modifiers Group
        modifiers_group = QGroupBox("Modifiers")
        modifiers_group.setFont(QFont("Segoe UI", 11, QFont.Bold))
        modifiers_layout = QHBoxLayout()
        modifiers_layout.setSpacing(20)

        self._shift_checkbox = QCheckBox("Shift")
        self._ctrl_checkbox = QCheckBox("Ctrl")
        self._alt_checkbox = QCheckBox("Alt")

        modifiers_layout.addWidget(self._shift_checkbox)
        modifiers_layout.addWidget(self._ctrl_checkbox)
        modifiers_layout.addWidget(self._alt_checkbox)
        modifiers_layout.addStretch()

        modifiers_group.setLayout(modifiers_layout)
        layout.addWidget(modifiers_group)

        # Randomization toggle
        random_layout = QHBoxLayout()
        self._randomization_checkbox = QCheckBox("Enable Randomization")
        self._randomization_checkbox.setChecked(True)
        self._randomization_checkbox.setFont(QFont("Segoe UI", 11))
        random_layout.addWidget(self._randomization_checkbox)
        random_layout.addStretch()
        layout.addLayout(random_layout)

        # Spacer to push buttons to bottom
        layout.addStretch()

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("secondaryButton")
        button_layout.addWidget(self._cancel_button)

        button_layout.addStretch()

        self._save_button = QPushButton("Save Macro")
        self._save_button.setObjectName("primaryButton")
        self._save_button.setDefault(True)
        button_layout.addWidget(self._save_button)

        layout.addLayout(button_layout)

    def _check_hotkey_conflict(self, hotkey: str) -> bool:
        """Check if hotkey conflicts with existing macros.
        
        Args:
            hotkey: Hotkey string to check.
        
        Returns:
            True if no conflict, False if conflict exists.
        """
        if not hotkey:
            return True
        
        try:
            macro_service = get_macro_service()
            macros = macro_service.get_all()
            
            for macro in macros:
                # Skip current macro if editing
                if self._is_editing and macro.id == self._macro_id:
                    continue
                
                if macro.hotkey and macro.hotkey.lower() == hotkey.lower():
                    self._logger.warning(f"Hotkey conflict: {hotkey} already used by macro '{macro.name}'")
                    return False
            
            return True
        except RuntimeError as e:
            self._logger.warning(f"Macro service not initialized: {e}")
            return True  # Allow if service not available

    def _connect_signals(self) -> None:
        """Connect widget signals to handlers."""
        # Position mode toggle
        self._cursor_radio.toggled.connect(self._on_position_mode_changed)
        self._fixed_radio.toggled.connect(self._on_position_mode_changed)

        # Capture button
        self._capture_button.clicked.connect(self._on_capture_clicked)

        # Action buttons
        self._save_button.clicked.connect(self._on_save_clicked)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

        # Connect to EventBus signals
        try:
            event_bus = get_event_bus()
            event_bus.position_captured.connect(self._on_position_captured)
            event_bus.position_capture_cancelled.connect(self._on_position_cancelled)
        except RuntimeError as e:
            self._logger.warning(f"EventBus not initialized: {e}")

    def _on_position_captured(self, x: int, y: int) -> None:
        """Handle position captured event from EventBus.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        self._x_spinbox.setValue(x)
        self._y_spinbox.setValue(y)
        self._restore_window()
        self._close_capture_message()

    def _on_position_cancelled(self) -> None:
        """Handle position capture cancelled event from EventBus."""
        self._restore_window()
        self._close_capture_message()

    def _close_capture_message(self) -> None:
        """Close the capture message box if it exists."""
        if hasattr(self, '_capture_message') and self._capture_message:
            self._capture_message.close()
            self._capture_message = None

    def _on_position_mode_changed(self) -> None:
        """Handle position mode change."""
        self._is_cursor_mode = self._cursor_radio.isChecked()
        is_fixed = self._fixed_radio.isChecked()
        self._coord_container.setVisible(is_fixed)
        self._x_spinbox.setEnabled(is_fixed)
        self._y_spinbox.setEnabled(is_fixed)
        self._capture_button.setEnabled(is_fixed)

    def _on_capture_clicked(self) -> None:
        """Handle capture button click."""
        # Guard: Check if macro is running
        try:
            state_manager = get_state_manager()
            if state_manager.is_running():
                self._show_error_dialog(
                    "Cannot Capture",
                    "Cannot capture position while a macro is running."
                )
                return
        except RuntimeError as e:
            self._logger.warning(f"State manager not initialized: {e}")

        # Get capture key from settings (default: f2)
        capture_key = "f2"  # TODO: Get from AppSettings

        # Start capture via service (with 200ms delay to allow window to minimize)
        try:
            capture_service = get_position_capture_service()
            if not capture_service.start_capture_delayed(
                capture_key=capture_key, timeout_ms=30000, delay_ms=200
            ):
                self._logger.warning("Capture already in progress")
                return
        except RuntimeError as e:
            self._show_error_dialog("Capture Failed", f"Service not initialized: {e}")
            return

        # Minimize window
        window = self.window()
        if window:
            window.showMinimized()

        # Show instruction message
        self._capture_message = QMessageBox(self)
        self._capture_message.setWindowTitle("Capture Position")
        self._capture_message.setText(
            f"Press {capture_key.upper()} to capture mouse position\n"
            f"Press Esc to cancel\n"
            f"(Timeout in 30 seconds)"
        )
        self._capture_message.setStandardButtons(QMessageBox.NoButton)
        self._capture_message.show()

    def _stop_capture(self) -> None:
        """Stop capture and cleanup."""
        self._close_capture_message()

        # Stop the capture service
        try:
            capture_service = get_position_capture_service()
            capture_service.stop_capture()
        except RuntimeError:
            pass  # Service not initialized
    
    def _restore_window(self) -> None:
        """Restore the application window."""
        window = self.window()
        if window:
            window.showNormal()
            window.raise_()
            window.activateWindow()
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        # Guard: Check if macro is running
        try:
            state_manager = get_state_manager()
            if state_manager.is_running():
                if self._is_editing and state_manager.get_current_macro() == self._macro_id:
                    self._show_error_dialog(
                        "Cannot Save",
                        "Cannot save while macro is running. Stop the macro first."
                    )
                    return
        except RuntimeError as e:
            self._logger.warning(f"State manager not initialized during save check: {e}")
            # Continue with save
        
        # Validate inputs
        if not self._validate_inputs():
            return
        
        try:
            # Build the macro
            macro = self._build_macro()
            
            # Save to service
            service = get_macro_service()
            service.save(macro)
            
            # Emit signal
            self.save_requested.emit(macro)
            
        except RuntimeError as e:
            self._show_error_dialog("Save Failed", f"Service not initialized: {e}")
        except Exception as e:
            self._show_error_dialog("Save Failed", f"Error saving macro: {e}")
    
    def _on_cancel_clicked(self) -> None:
        """Handle cancel button click."""
        self.cancel_requested.emit()
    
    def _validate_inputs(self) -> bool:
        """Validate form inputs.
        
        Returns:
            True if all inputs are valid, False otherwise.
        """
        # Check macro name
        name = self._name_input.text().strip()
        if not name:
            self._show_error_dialog("Validation Error", "Macro name cannot be empty.")
            return False
        
        # Check fixed position has coordinates
        if self._fixed_radio.isChecked():
            x = self._x_spinbox.value()
            y = self._y_spinbox.value()
            if x == 0 and y == 0:
                # Allow zero values, but warn if both are zero
                # In practice, (0,0) is a valid screen position
                pass
        
        # Check interval is > 0
        seconds = self._seconds_spinbox.value()
        milliseconds = self._ms_spinbox.value()
        total_ms = seconds * 1000 + milliseconds
        if total_ms <= 0:
            self._show_error_dialog("Validation Error", "Interval must be greater than 0.")
            return False
        
        return True
    
    def _build_macro(self) -> Macro:
        """Build macro from form inputs.
        
        Returns:
            Macro instance with actions.
        """
        # Get position settings
        is_fixed = self._fixed_radio.isChecked()
        if is_fixed:
            x = self._x_spinbox.value()
            y = self._y_spinbox.value()
        else:
            # Cursor position - will be captured at runtime
            x, y = 0, 0
        
        # Get click settings
        button = self._button_combo.currentText().lower()
        
        # Get modifiers
        # TODO: Modifiers will be added to ClickAction in Phase 4
        # For now, store in instance variable for later use
        self._modifiers = self._get_selected_modifiers()
        
        # Get interval
        seconds = self._seconds_spinbox.value()
        milliseconds = self._ms_spinbox.value()
        total_ms = seconds * 1000 + milliseconds
        
        # Get name
        name = self._name_input.text().strip()
        
        # Get randomization setting
        randomization_enabled = self._randomization_checkbox.isChecked()
        
        # Build ClickAction with modifiers
        click_action = ClickAction(
            x=x,
            y=y,
            button=button,
            modifiers=self._modifiers,  # Use stored modifiers
            jitter_radius=5  # Default jitter
        )
        
        # Create actions
        actions = [
            click_action,
            DelayAction(duration_ms=total_ms),
        ]
        
        # Create or update macro
        if self._is_editing and self._existing_macro:
            # Update existing macro
            macro = self._existing_macro
            macro.name = name
            macro.actions = actions
            macro.randomization_enabled = randomization_enabled
            macro.touch()
        else:
            # Create new macro
            macro = Macro(
                name=name,
                actions=actions,
                randomization_enabled=randomization_enabled,
            )
        
        # Get hotkey
        hotkey = self._hotkey_input.get_hotkey()
        if hotkey:
            macro.hotkey = hotkey
        
        return macro
    
    def _load_macro(self, macro_id: str) -> None:
        """Load existing macro for editing.
        
        Args:
            macro_id: ID of macro to load.
        """
        try:
            service = get_macro_service()
            self._existing_macro = service.get(macro_id)
            
            # Populate form with macro data
            self._populate_form(self._existing_macro)
            
        except RuntimeError as e:
            self._logger.warning(f"Macro service not initialized during load: {e}")
            # Continue without loading
        except Exception as e:
            self._show_error_dialog("Load Failed", f"Could not load macro: {e}")
    
    def _get_selected_modifiers(self) -> list[str]:
        """Get list of selected modifier keys.
        
        Returns:
            List of modifier key names.
        """
        modifiers = []
        if self._shift_checkbox.isChecked():
            modifiers.append("shift")
        if self._ctrl_checkbox.isChecked():
            modifiers.append("ctrl")
        if self._alt_checkbox.isChecked():
            modifiers.append("alt")
        return modifiers
    
    def _populate_form(self, macro: Macro) -> None:
        """Populate form fields from macro.
        
        Args:
            macro: Macro to populate from.
        """
        # Set name
        self._name_input.setText(macro.name)
        
        # Set randomization
        self._randomization_checkbox.setChecked(macro.randomization_enabled)
        
        # Load hotkey
        if macro.hotkey:
            self._hotkey_input.set_hotkey(macro.hotkey)
        else:
            self._hotkey_input.set_hotkey("")
        
        # Extract actions
        click_action: Optional[ClickAction] = None
        delay_action: Optional[DelayAction] = None
        
        for action in macro.actions:
            if isinstance(action, ClickAction):
                click_action = action
            elif isinstance(action, DelayAction):
                delay_action = action
        
        # Set position mode and coordinates
        if click_action:
            # Use stored cursor mode flag instead of guessing from coordinates
            if self._is_cursor_mode:
                self._cursor_radio.setChecked(True)
            else:
                self._fixed_radio.setChecked(True)
                self._x_spinbox.setValue(click_action.x)
                self._y_spinbox.setValue(click_action.y)
            
            # Set mouse button
            button_index = self._button_combo.findText(
                click_action.button.capitalize()
            )
            if button_index >= 0:
                self._button_combo.setCurrentIndex(button_index)
            
            # Load modifiers from ClickAction
            self._modifiers = click_action.modifiers or []
            self._shift_checkbox.setChecked("shift" in self._modifiers)
            self._ctrl_checkbox.setChecked("ctrl" in self._modifiers)
            self._alt_checkbox.setChecked("alt" in self._modifiers)
        
        # Set interval
        if delay_action:
            total_ms = delay_action.duration_ms
            seconds = total_ms // 1000
            milliseconds = total_ms % 1000
            self._seconds_spinbox.setValue(seconds)
            self._ms_spinbox.setValue(milliseconds)
    
    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show error dialog.
        
        Args:
            title: Dialog title.
            message: Error message.
        """
        QMessageBox.critical(self, title, message)
    
    def reset(self) -> None:
        """Reset the editor to default state."""
        self._macro_id = None
        self._existing_macro = None
        self._is_editing = False
        
        # Reset title
        self._title_label.setText("Create Macro")
        
        # Reset inputs
        self._name_input.clear()
        self._name_input.setStyleSheet("")
        
        # Reset hotkey
        self._hotkey_input.set_hotkey("")
        
        self._cursor_radio.setChecked(True)
        self._x_spinbox.setValue(0)
        self._y_spinbox.setValue(0)
        
        self._seconds_spinbox.setValue(1)
        self._ms_spinbox.setValue(0)
        
        self._button_combo.setCurrentText("Left")
        
        self._shift_checkbox.setChecked(False)
        self._ctrl_checkbox.setChecked(False)
        self._alt_checkbox.setChecked(False)
        
        self._randomization_checkbox.setChecked(True)
        
        # Reset save button
        self._save_button.setEnabled(True)
        self._save_button.setToolTip("")
        self._running_indicator.setVisible(False)
    
    def set_macro_id(self, macro_id: Optional[str]) -> None:
        """Set the macro ID for editing.
        
        Args:
            macro_id: Macro ID to edit, or None for new macro.
        """
        if macro_id is None:
            self.reset()
            return
        
        self._macro_id = macro_id
        self._is_editing = True
        self._title_label.setText("Edit Macro")
        self._load_macro(macro_id)
    
    def _cleanup(self) -> None:
        """Clean up resources when page is hidden/destroyed."""
        self._stop_capture()

        # Disconnect from EventBus - wrap each disconnect in try/except
        try:
            event_bus = get_event_bus()
            try:
                event_bus.position_captured.disconnect(self._on_position_captured)
            except (RuntimeError, TypeError):
                pass  # Signal not connected or EventBus destroyed
        except RuntimeError:
            pass  # EventBus not initialized

        try:
            event_bus = get_event_bus()
            try:
                event_bus.position_capture_cancelled.disconnect(self._on_position_cancelled)
            except (RuntimeError, TypeError):
                pass  # Signal not connected or EventBus destroyed
        except RuntimeError:
            pass  # EventBus not initialized

        # Cleanup hotkey input
        if hasattr(self, '_hotkey_input'):
            try:
                self._hotkey_input.cleanup()
            except Exception:
                pass  # Ignore cleanup errors during shutdown
    
    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        self._cleanup()
        super().closeEvent(event)
    
    def hideEvent(self, event) -> None:
        """Handle widget hide event."""
        self._cleanup()
        super().hideEvent(event)
