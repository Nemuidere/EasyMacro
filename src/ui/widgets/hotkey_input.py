"""
Hotkey input widget for EasyMacro.

Captures key combinations using pynput keyboard listener.
"""

from typing import Optional, Callable
from dataclasses import dataclass
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

from src.core.logger import get_logger


@dataclass
class HotkeyState:
    """Immutable state for hotkey capture.

    Attributes:
        keys: Set of currently pressed key names.
        is_capturing: Whether currently listening for input.
    """
    keys: frozenset[str]
    is_capturing: bool

    def add_key(self, key: str) -> "HotkeyState":
        """Return new state with key added."""
        return HotkeyState(
            keys=self.keys | {key.lower()},
            is_capturing=self.is_capturing
        )

    def remove_key(self, key: str) -> "HotkeyState":
        """Return new state with key removed."""
        return HotkeyState(
            keys=self.keys - {key.lower()},
            is_capturing=self.is_capturing
        )

    def start_capturing(self) -> "HotkeyState":
        """Return new state with capturing enabled."""
        return HotkeyState(keys=frozenset(), is_capturing=True)

    def stop_capturing(self) -> "HotkeyState":
        """Return new state with capturing disabled."""
        return HotkeyState(keys=frozenset(), is_capturing=False)

    def get_hotkey_string(self) -> str:
        """Convert pressed keys to hotkey string format."""
        modifier_order = ["ctrl", "alt", "shift", "meta"]
        modifiers = [k for k in modifier_order if k in self.keys]
        other_keys = [k for k in self.keys if k not in modifier_order]
        all_keys = modifiers + sorted(other_keys)
        return "+".join(all_keys) if all_keys else ""


class HotkeyInput(QGroupBox):
    """Widget for capturing and displaying hotkey combinations.

    Uses pynput for global keyboard capture with proper resource cleanup.
    Thread-safe updates via Qt signals with queued connections.

    Signals:
        hotkey_changed: Emitted when hotkey changes (str: new hotkey or empty).
        capture_error: Emitted when capture fails (str: error message).
    """

    hotkey_changed = Signal(str)
    capture_error = Signal(str)

    # Internal signals for thread-safe UI updates from background thread
    _keys_updated = Signal(object)  # frozenset of keys
    _capture_finalized = Signal()

    def __init__(
        self,
        label: str,
        parent: Optional[QWidget] = None,
        on_conflict: Optional[Callable[[str], bool]] = None,
        input_id: Optional[str] = None,
        default_hotkey: str = ""
    ):
        """Initialize hotkey input widget.

        Args:
            label: Display label for the hotkey (e.g., "Pause All").
            parent: Optional parent widget.
            on_conflict: Optional callback for conflict resolution.
                        Receives hotkey string, returns True if accepted.
            input_id: Optional unique identifier for this input instance,
                     used for conflict detection and debugging.
            default_hotkey: Default hotkey to reset to (empty string for no default).
        """
        super().__init__(parent)

        if not label:
            raise ValueError("Label cannot be empty")

        self._label_text = label
        self._on_conflict = on_conflict
        self._input_id = input_id or label.lower().replace(" ", "_")
        self._default_hotkey = default_hotkey
        self._logger = get_logger("hotkey_input")
        self._state = HotkeyState(keys=frozenset(), is_capturing=False)
        self._current_hotkey = ""
        self._keyboard_listener = None

        # Validate default_hotkey
        if default_hotkey and not self._is_valid_hotkey(default_hotkey):
            raise ValueError(f"Invalid default_hotkey format: {default_hotkey}")

        self._setup_ui()
        self._setup_signals()

    def __del__(self):
        """Cleanup resources as safety net during garbage collection."""
        try:
            if self._keyboard_listener:
                self._keyboard_listener.stop()
                self._keyboard_listener = None
        except Exception:
            pass

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setTitle(self._label_text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(10)

        # Hotkey display label
        self._hotkey_label = QLabel("No hotkey set")
        self._hotkey_label.setStyleSheet("font-weight: bold; padding: 5px;")
        self._hotkey_label.setMinimumWidth(150)
        layout.addWidget(self._hotkey_label)

        layout.addStretch()

        # Capture button
        self._capture_button = QPushButton("Capture")
        self._capture_button.clicked.connect(self._start_capture)
        layout.addWidget(self._capture_button)

        # Cancel button (only visible during capture)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._stop_capture)
        layout.addWidget(self._cancel_button)

        # Default button
        self._default_button = QPushButton("Default")
        self._default_button.clicked.connect(self._on_default_clicked)
        layout.addWidget(self._default_button)

    def _setup_signals(self) -> None:
        """Set up internal signals for thread-safe updates."""
        # Connect signals to slots - queued connection ensures main thread execution
        self._keys_updated.connect(self._on_keys_updated)
        self._capture_finalized.connect(self._finalize_capture)

    @Slot(object)
    def _on_keys_updated(self, keys: frozenset) -> None:
        """Handle keys updated signal - runs in main thread.

        Args:
            keys: Set of currently pressed key names.
        """
        if not self._state.is_capturing:
            return

        self._state = HotkeyState(keys=keys, is_capturing=True)
        self._update_display()

    def _start_capture(self) -> None:
        """Start listening for hotkey input."""
        # Guard: Already capturing, do nothing
        if self._state.is_capturing:
            self._logger.debug("Already capturing, ignoring start request")
            return

        self._state = self._state.start_capturing()
        self._hotkey_label.setText("Press keys...")
        self._hotkey_label.setStyleSheet(
            "font-weight: bold; padding: 5px; color: #2196F3;"
        )

        # Show cancel button during capture
        self._cancel_button.setVisible(True)

        try:
            self._keyboard_listener = self._create_keyboard_listener()
            self._keyboard_listener.start()
            self._logger.debug(f"Started keyboard listener for {self._input_id}")
        except Exception as e:
            self._logger.error(f"Failed to start keyboard listener: {e}")
            self._stop_capture()
            self.capture_error.emit(f"Failed to start capture: {e}")

    def _create_keyboard_listener(self):
        """Create pynput keyboard listener.

        Returns:
            Configured keyboard listener.
        """
        from pynput import keyboard

        def on_press(key) -> None:
            """Handle key press event - runs in background thread."""
            try:
                key_name = self._get_key_name(key)
                if key_name:
                    # Emit signal to update UI in main thread
                    self._keys_updated.emit(self._state.keys | {key_name.lower()})
            except Exception as e:
                self._logger.error(f"Error in key press handler: {e}")

        def on_release(key) -> None:
            """Handle key release event - runs in background thread."""
            try:
                key_name = self._get_key_name(key)
                if key_name:
                    # Emit signal to finalize capture in main thread
                    # This schedules capture after brief delay for multi-key combinations
                    QTimer.singleShot(200, self._capture_finalized.emit)
            except Exception as e:
                self._logger.error(f"Error in key release handler: {e}")

        return keyboard.Listener(on_press=on_press, on_release=on_release)

    def _get_key_name(self, key) -> Optional[str]:
        """Extract key name from pynput key object.

        Args:
            key: pynput keyboard key object.

        Returns:
            Key name string or None if cannot be determined.
        """
        from pynput.keyboard import Key

        if isinstance(key, Key):
            return key.name.lower()

        try:
            # Handle character keys
            char = key.char
            if char:
                return char.lower()
        except AttributeError:
            pass

        return None

    def _update_display(self) -> None:
        """Update hotkey display label."""
        if not self._state.is_capturing:
            return

        hotkey_str = self._state.get_hotkey_string()
        if hotkey_str:
            self._hotkey_label.setText(hotkey_str)

    @Slot()
    def _finalize_capture(self) -> None:
        """Finalize hotkey capture after key release."""
        if not self._state.is_capturing:
            return

        hotkey_str = self._state.get_hotkey_string()

        if not hotkey_str:
            self._logger.debug("No keys captured, continuing capture")
            return

        # Check for conflicts if callback provided
        if self._on_conflict and not self._on_conflict(hotkey_str):
            self._logger.info(f"Hotkey conflict detected: {hotkey_str}")
            self._show_conflict_dialog(hotkey_str)
            self._state = self._state.start_capturing()  # Reset but keep capturing
            return

        self._set_hotkey(hotkey_str)
        self._stop_capture()

    def _show_conflict_dialog(self, hotkey: str) -> None:
        """Show conflict error dialog.

        Args:
            hotkey: The conflicting hotkey string.
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Hotkey Conflict")
        msg.setText(f"The hotkey '{hotkey}' is already in use.")
        msg.setInformativeText("Please choose a different key combination.")
        msg.exec()

    def _stop_capture(self) -> None:
        """Stop listening for hotkey input."""
        self._state = self._state.stop_capturing()

        # Hide cancel button when capture stops
        self._cancel_button.setVisible(False)

        # Reset display to current hotkey
        self._update_hotkey_display()

        # Stop and cleanup listener
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
                self._logger.debug(f"Stopped keyboard listener for {self._input_id}")
            except Exception as e:
                self._logger.error(f"Error stopping keyboard listener: {e}")
            finally:
                self._keyboard_listener = None

    def _on_default_clicked(self) -> None:
        """Handle default button click - reset to default hotkey."""
        self._set_hotkey(self._default_hotkey)
        self._stop_capture()

    def _set_hotkey(self, hotkey: str) -> None:
        """Set the current hotkey value.

        Args:
            hotkey: Hotkey string or empty to clear.
        """
        self._current_hotkey = hotkey
        self._update_hotkey_display()
        self.hotkey_changed.emit(hotkey)
        self._logger.debug(f"Hotkey set to: {hotkey or 'None'}")

    def _update_hotkey_display(self) -> None:
        """Update display label with current hotkey."""
        if self._current_hotkey:
            self._hotkey_label.setText(self._current_hotkey)
            self._hotkey_label.setStyleSheet("font-weight: bold; padding: 5px;")
        else:
            self._hotkey_label.setText("No hotkey set")
            self._hotkey_label.setStyleSheet(
                "font-weight: bold; padding: 5px; color: #666;"
            )

    def get_hotkey(self) -> str:
        """Get current hotkey value.

        Returns:
            Current hotkey string or empty if not set.
        """
        return self._current_hotkey

    def set_hotkey(self, hotkey: str) -> None:
        """Set hotkey value programmatically.

        Args:
            hotkey: Hotkey string to set.

        Raises:
            ValueError: If hotkey format is invalid.
        """
        if hotkey is None:
            raise ValueError("Hotkey cannot be None")

        # Validate format (basic check)
        if hotkey and not self._is_valid_hotkey(hotkey):
            raise ValueError(f"Invalid hotkey format: {hotkey}")

        self._set_hotkey(hotkey)

    def _is_valid_hotkey(self, hotkey: str) -> bool:
        """Validate hotkey string format.

        Args:
            hotkey: Hotkey string to validate.

        Returns:
            True if valid format.
        """
        if not hotkey:
            return True

        parts = hotkey.lower().split("+")
        valid_parts = all(part.strip() for part in parts)
        return valid_parts and len(parts) > 0

    def is_capturing(self) -> bool:
        """Check if currently capturing input.

        Returns:
            True if capturing.
        """
        return self._state.is_capturing

    def stop_capture(self) -> None:
        """Public method to stop capture."""
        self._stop_capture()

    def get_input_id(self) -> str:
        """Get the unique input identifier.

        Returns:
            The input ID for conflict detection and debugging.
        """
        return self._input_id

    def cleanup(self) -> None:
        """Clean up resources before destruction."""
        self._stop_capture()
        self._cancel_button.setVisible(False)

    def hideEvent(self, event) -> None:
        """Handle hide event - stop capture."""
        self._stop_capture()
        self._cancel_button.setVisible(False)
        super().hideEvent(event)
