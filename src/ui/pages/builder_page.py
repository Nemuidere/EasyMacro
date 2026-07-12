"""
Macro Builder page for EasyMacro.

A multi-action sequence editor: the user assembles an ordered list of actions
(clicks at different positions, mouse moves, key presses, key holds/releases and
delays) into a single macro. Replaces the old single-action editor as the way to
create and edit every macro.

The heavy lifting (executing each action type, randomization, safety) already
lives in the macro engine; this page is purely the authoring surface.
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QInputDialog,
    QAbstractItemView,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.logger import get_logger
from src.models.macro import Macro
from src.models.action import (
    Action,
    ActionType,
    ClickAction,
    DelayAction,
    KeyPressAction,
    MouseMoveAction,
    LoopBlock,
)
from src.services.macro_service import get_macro_service
from src.ui.widgets.hotkey_input import HotkeyInput


# Action kinds offered in the "Add action" dropdown. Each maps to how the config
# dialog is built and how the resulting Action is constructed.
ACTION_KINDS = [
    ("click", "Click"),
    ("move", "Move mouse"),
    ("key_press", "Key press"),
    ("key_hold", "Key hold"),
    ("key_release", "Key release"),
    ("delay", "Delay"),
]

_MODIFIERS = ("ctrl", "alt", "shift")


def _build_qt_key_map() -> dict:
    """Map Qt key codes (as ints) to engine/AHK-friendly key names."""
    mapping = {
        int(Qt.Key.Key_Return): "enter",
        int(Qt.Key.Key_Enter): "enter",
        int(Qt.Key.Key_Space): "space",
        int(Qt.Key.Key_Escape): "escape",
        int(Qt.Key.Key_Tab): "tab",
        int(Qt.Key.Key_Backspace): "backspace",
        int(Qt.Key.Key_Delete): "delete",
        int(Qt.Key.Key_Up): "up",
        int(Qt.Key.Key_Down): "down",
        int(Qt.Key.Key_Left): "left",
        int(Qt.Key.Key_Right): "right",
        int(Qt.Key.Key_Home): "home",
        int(Qt.Key.Key_End): "end",
        int(Qt.Key.Key_PageUp): "pageup",
        int(Qt.Key.Key_PageDown): "pagedown",
        int(Qt.Key.Key_Insert): "insert",
        int(Qt.Key.Key_Shift): "shift",
        int(Qt.Key.Key_Control): "ctrl",
        int(Qt.Key.Key_Alt): "alt",
    }
    for i in range(1, 25):
        mapping[int(getattr(Qt.Key, f"Key_F{i}"))] = f"f{i}"
    return mapping


_QT_KEY_MAP = _build_qt_key_map()


class KeyCaptureButton(QPushButton):
    """A button that captures the next physical key press instead of typing.

    Click it, then press any key; the resolved key name is stored and shown.
    Printable characters use the typed character; special keys (Enter, F5,
    arrows, modifiers, …) map to engine/AHK-friendly names.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._key = ""
        self._capturing = False
        self.setCheckable(True)
        self._refresh_text()
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._capturing = True
        self.setChecked(True)
        self.setText("Press any key…")
        self.setFocus()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._capturing:
            super().keyPressEvent(event)
            return
        name = self._resolve(event)
        if name is None:
            return  # ignore unresolvable keys; keep listening
        self._key = name
        self._capturing = False
        self.setChecked(False)
        self._refresh_text()

    @staticmethod
    def _resolve(event) -> Optional[str]:
        code = int(event.key())
        if code in _QT_KEY_MAP:
            return _QT_KEY_MAP[code]
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            return text.lower()
        return None

    def _refresh_text(self) -> None:
        self.setText(f"Key: {self._key}" if self._key else "Click, then press a key")

    def key(self) -> str:
        return self._key

    def set_key(self, key: str) -> None:
        self._key = key or ""
        self._capturing = False
        self.setChecked(False)
        self._refresh_text()


def summarize_action(action: Action) -> str:
    """Return a short, human-readable one-line summary of an action."""
    if isinstance(action, ClickAction):
        if action.action_type == ActionType.DOUBLE_CLICK:
            verb = "Double-click"
        elif action.action_type == ActionType.RIGHT_CLICK:
            verb = "Right-click"
        else:
            verb = f"{action.button.capitalize()}-click"
        where = "cursor pos" if action.use_cursor_position else f"({action.x}, {action.y})"
        base = f"{verb} @ {where}"
    elif isinstance(action, MouseMoveAction):
        base = f"Move to ({action.x}, {action.y}) · speed {action.speed}"
    elif isinstance(action, KeyPressAction):
        if action.action_type == ActionType.KEY_HOLD:
            base = f"Hold key '{action.key}'"
        elif action.action_type == ActionType.KEY_RELEASE:
            base = f"Release key '{action.key}'"
        else:
            combo = "+".join(list(action.modifiers) + [action.key]) if action.modifiers else action.key
            base = f"Press '{combo}'"
    elif isinstance(action, DelayAction):
        return f"Delay {action.duration_ms} ms"
    else:
        return "Unknown action"

    delay_after = getattr(action, "delay_after_ms", 0)
    if delay_after:
        base += f"  ·  +{delay_after}ms delay"
    return base


def summarize_item(item) -> str:
    """One-line summary of a macro item (a leaf action or a loop block)."""
    if isinstance(item, LoopBlock):
        inner = " · ".join(summarize_action(a) for a in item.actions) or "empty"
        return f"⟳ Loop ×{item.count}  [ {inner} ]"
    return summarize_action(item)


class ActionConfigDialog(QDialog):
    """Modal dialog to create or edit a single action of a given kind.

    On accept, :meth:`result_action` returns the configured Action instance.
    Click/move actions offer position capture (press F2) via the position
    capture service.
    """

    def __init__(
        self,
        kind: str,
        existing: Optional[Action] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._logger = get_logger("action_dialog")
        self._kind = kind
        self._existing = existing
        self._result: Optional[Action] = None
        self._overlay = None

        self.setWindowTitle(f"Configure: {dict(ACTION_KINDS).get(kind, kind)}")
        self.setModal(True)
        self.setMinimumWidth(360)

        self._build_ui()
        if existing is not None:
            self._load_existing(existing)

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        if self._kind in ("click", "move"):
            self._build_position_fields(form)
        if self._kind == "click":
            self._build_click_fields(form)
        if self._kind == "move":
            self._build_move_fields(form)
        if self._kind in ("key_press", "key_hold", "key_release"):
            self._build_key_fields(form)
        if self._kind == "delay":
            self._build_delay_fields(form)
        if self._kind != "delay":
            self._build_delay_after_fields(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_position_fields(self, form: QFormLayout) -> None:
        self._cursor_check = QCheckBox("Use current cursor position at run time")
        # Only clicks support cursor-position mode; moves need a target.
        if self._kind == "click":
            form.addRow(self._cursor_check)
            self._cursor_check.toggled.connect(self._on_cursor_toggled)
        else:
            self._cursor_check.setVisible(False)

        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, 100000)
        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, 100000)
        form.addRow("X:", self._x_spin)
        form.addRow("Y:", self._y_spin)

        self._capture_btn = QPushButton("Capture position (F2)")
        self._capture_btn.clicked.connect(self._start_capture)
        form.addRow(self._capture_btn)

    def _build_click_fields(self, form: QFormLayout) -> None:
        self._button_combo = QComboBox()
        self._button_combo.addItems(["left", "right", "middle"])
        form.addRow("Button:", self._button_combo)

        self._double_check = QCheckBox("Double click")
        form.addRow(self._double_check)

    def _build_move_fields(self, form: QFormLayout) -> None:
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(1, 10)
        self._speed_spin.setValue(5)
        form.addRow("Speed (1-10):", self._speed_spin)

        self._smooth_check = QCheckBox("Smooth movement")
        self._smooth_check.setChecked(True)
        form.addRow(self._smooth_check)

    def _build_key_fields(self, form: QFormLayout) -> None:
        self._key_capture = KeyCaptureButton()
        form.addRow("Key:", self._key_capture)

        # Modifier check-boxes for every key kind (press, hold and release).
        self._mod_checks = {}
        mod_row = QHBoxLayout()
        for mod in _MODIFIERS:
            cb = QCheckBox(mod)
            self._mod_checks[mod] = cb
            mod_row.addWidget(cb)
        container = QWidget()
        container.setLayout(mod_row)
        form.addRow("Modifiers:", container)

        # Key hold: choose to hold until released/stopped, or for a fixed time.
        if self._kind == "key_hold":
            self._hold_mode = QButtonGroup(self)
            self._hold_until_radio = QRadioButton("Hold until released / stopped")
            self._hold_until_radio.setChecked(True)
            self._hold_for_radio = QRadioButton("Hold for a fixed time")
            self._hold_mode.addButton(self._hold_until_radio)
            self._hold_mode.addButton(self._hold_for_radio)

            self._hold_ms = QSpinBox()
            self._hold_ms.setRange(1, 3_600_000)
            self._hold_ms.setValue(1000)
            self._hold_ms.setSuffix(" ms")
            self._hold_ms.setEnabled(False)
            self._hold_for_radio.toggled.connect(self._hold_ms.setEnabled)

            form.addRow(self._hold_until_radio)
            for_row = QHBoxLayout()
            for_row.addWidget(self._hold_for_radio)
            for_row.addWidget(self._hold_ms)
            for_container = QWidget()
            for_container.setLayout(for_row)
            form.addRow(for_container)

    def _build_delay_fields(self, form: QFormLayout) -> None:
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(0, 3600000)
        self._duration_spin.setValue(500)
        self._duration_spin.setSuffix(" ms")
        form.addRow("Duration:", self._duration_spin)

    def _build_delay_after_fields(self, form: QFormLayout) -> None:
        """Optional delay after this action completes, before the next step.

        Lets a step (click/move/key) carry its own trailing delay instead of
        always needing a separate standalone Delay step after it.
        """
        self._delay_after_check = QCheckBox("Add delay after this step")
        form.addRow(self._delay_after_check)

        self._delay_after_ms = QSpinBox()
        self._delay_after_ms.setRange(0, 3600000)
        self._delay_after_ms.setValue(0)
        self._delay_after_ms.setSuffix(" ms")
        self._delay_after_ms.setEnabled(False)
        form.addRow("Delay duration:", self._delay_after_ms)

        self._delay_after_variance = QSpinBox()
        self._delay_after_variance.setRange(0, 100)
        self._delay_after_variance.setValue(5)
        self._delay_after_variance.setSuffix(" %")
        self._delay_after_variance.setEnabled(False)
        form.addRow("Delay variance:", self._delay_after_variance)

        self._delay_after_check.toggled.connect(self._delay_after_ms.setEnabled)
        self._delay_after_check.toggled.connect(self._delay_after_variance.setEnabled)

    # -- load existing ------------------------------------------------------

    def _load_existing(self, action: Action) -> None:
        if isinstance(action, ClickAction):
            self._cursor_check.setChecked(action.use_cursor_position)
            self._x_spin.setValue(action.x)
            self._y_spin.setValue(action.y)
            idx = self._button_combo.findText(action.button)
            if idx >= 0:
                self._button_combo.setCurrentIndex(idx)
            self._double_check.setChecked(action.action_type == ActionType.DOUBLE_CLICK)
            self._on_cursor_toggled(action.use_cursor_position)
        elif isinstance(action, MouseMoveAction):
            self._x_spin.setValue(action.x)
            self._y_spin.setValue(action.y)
            self._speed_spin.setValue(action.speed)
            self._smooth_check.setChecked(action.smooth)
        elif isinstance(action, KeyPressAction):
            self._key_capture.set_key(action.key)
            for mod, cb in self._mod_checks.items():
                cb.setChecked(mod in action.modifiers)
        elif isinstance(action, DelayAction):
            self._duration_spin.setValue(action.duration_ms)

        if self._kind != "delay":
            delay_after = getattr(action, "delay_after_ms", 0)
            if delay_after:
                self._delay_after_check.setChecked(True)
                self._delay_after_ms.setValue(delay_after)
                self._delay_after_variance.setValue(getattr(action, "delay_after_variance_percent", 5))

    # -- position capture ---------------------------------------------------

    def _on_cursor_toggled(self, use_cursor: bool) -> None:
        for w in (self._x_spin, self._y_spin, self._capture_btn):
            w.setEnabled(not use_cursor)

    def _start_capture(self) -> None:
        """Capture a screen position with the full-screen overlay.

        Reliable, pure-Qt: the user clicks the target position on a translucent
        always-on-top overlay; the click never reaches the underlying window.
        """
        from src.ui.widgets.capture_overlay import CapturePanel

        self._overlay = CapturePanel(self)
        self._overlay.captured.connect(self._on_position_captured)
        self._overlay.cancelled.connect(self._on_position_cancelled)
        self._overlay.show()

    def _on_position_captured(self, x: int, y: int) -> None:
        # Spin-box minimum is 0, so any negative multi-monitor coord clamps.
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._overlay = None

    def _on_position_cancelled(self) -> None:
        self._overlay = None

    # -- result -------------------------------------------------------------

    def _on_accept(self) -> None:
        try:
            self._result = self._build_action()
        except Exception as e:
            QMessageBox.warning(self, "Invalid action", str(e))
            return
        self.accept()

    def reject(self) -> None:  # type: ignore[override]
        super().reject()

    def _build_action(self) -> Action:
        if self._kind == "delay":
            return DelayAction(duration_ms=self._duration_spin.value())

        delay_after_ms = self._delay_after_ms.value() if self._delay_after_check.isChecked() else 0
        delay_after_variance = self._delay_after_variance.value()

        if self._kind == "click":
            use_cursor = self._cursor_check.isChecked()
            action_type = ActionType.DOUBLE_CLICK if self._double_check.isChecked() else ActionType.CLICK
            return ClickAction(
                x=0 if use_cursor else self._x_spin.value(),
                y=0 if use_cursor else self._y_spin.value(),
                button=self._button_combo.currentText(),
                use_cursor_position=use_cursor,
                action_type=action_type,
                delay_after_ms=delay_after_ms,
                delay_after_variance_percent=delay_after_variance,
            )
        if self._kind == "move":
            return MouseMoveAction(
                x=self._x_spin.value(),
                y=self._y_spin.value(),
                speed=self._speed_spin.value(),
                smooth=self._smooth_check.isChecked(),
                delay_after_ms=delay_after_ms,
                delay_after_variance_percent=delay_after_variance,
            )
        if self._kind in ("key_press", "key_hold", "key_release"):
            key = self._key_capture.key().strip()
            if not key:
                raise ValueError("No key captured — click 'Key' and press a key")
            mods = [m for m, cb in self._mod_checks.items() if cb.isChecked()]
            if self._kind == "key_press":
                action_type = ActionType.KEY_PRESS
            elif self._kind == "key_hold":
                action_type = ActionType.KEY_HOLD
            else:
                action_type = ActionType.KEY_RELEASE
            return KeyPressAction(
                key=key,
                modifiers=mods,
                action_type=action_type,
                delay_after_ms=delay_after_ms,
                delay_after_variance_percent=delay_after_variance,
            )
        raise ValueError(f"Unknown action kind: {self._kind}")

    def result_action(self) -> Optional[Action]:
        return self._result

    def result_actions(self) -> List[Action]:
        """Return the action(s) this dialog produced.

        Usually a single action, but a "hold for a fixed time" key-hold expands
        into three visible steps — hold, delay, release — so the timed hold is
        transparent and editable in the list.
        """
        if self._result is None:
            return []
        if (
            self._kind == "key_hold"
            and getattr(self, "_hold_for_radio", None) is not None
            and self._hold_for_radio.isChecked()
        ):
            hold: KeyPressAction = self._result  # type: ignore[assignment]
            release = KeyPressAction(
                key=hold.key,
                modifiers=list(hold.modifiers),
                action_type=ActionType.KEY_RELEASE,
            )
            return [hold, DelayAction(duration_ms=self._hold_ms.value()), release]
        return [self._result]


class MacroBuilderPage(QWidget):
    """Page for assembling a macro from an ordered list of actions."""

    save_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("builderPage")
        self._logger = get_logger("builder_page")

        self._actions: List[Action] = []
        self._macro_id: Optional[str] = None
        self._is_editing = False

        self._setup_ui()
        self._connect_signals()

    # -- UI -----------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Outer layout just hosts a scroll area (so the content never gets
        # squeezed/overlapped on a short window) plus the save/cancel row
        # pinned below it, always visible without scrolling.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("builderContent")

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        self._title_label = QLabel("New Macro")
        self._title_label.setObjectName("pageTitle")
        self._title_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
        layout.addWidget(self._title_label)

        # Name
        name_row = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("My macro")
        name_row.addRow("Name:", self._name_input)
        layout.addLayout(name_row)

        # Action list + side controls
        list_row = QHBoxLayout()

        self._action_list = QListWidget()
        self._action_list.setObjectName("actionList")
        list_row.addWidget(self._action_list, 1)

        # Side controls: a compact 2-column grid instead of one tall stack of
        # buttons, so the panel needs roughly half the vertical space (the
        # scroll area above is the safety net for whatever's left over).
        side = QVBoxLayout()
        self._add_type_combo = QComboBox()
        for kind, label in ACTION_KINDS:
            self._add_type_combo.addItem(label, kind)
        side.addWidget(self._add_type_combo)

        self._add_btn = QPushButton("Add")
        self._add_btn.setObjectName("primaryButton")
        side.addWidget(self._add_btn)

        side.addSpacing(10)
        self._up_btn = QPushButton("Move up")
        self._down_btn = QPushButton("Move down")
        self._dup_btn = QPushButton("Duplicate")
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName("dangerButton")
        # Loop controls: select one or more contiguous rows, then "Loop …" wraps
        # them into a repeat block; "Ungroup" expands a loop back to its steps.
        self._loop_btn = QPushButton("Loop selected…")
        self._ungroup_btn = QPushButton("Ungroup loop")

        button_grid = QGridLayout()
        button_grid.setSpacing(8)
        button_grid.addWidget(self._up_btn, 0, 0)
        button_grid.addWidget(self._down_btn, 0, 1)
        button_grid.addWidget(self._dup_btn, 1, 0)
        button_grid.addWidget(self._remove_btn, 1, 1)
        button_grid.addWidget(self._loop_btn, 2, 0)
        button_grid.addWidget(self._ungroup_btn, 2, 1)
        side.addLayout(button_grid)
        side.addStretch()

        # Allow selecting a contiguous range to group into a loop.
        self._action_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_row.addLayout(side)
        layout.addLayout(list_row, 1)

        # Realistic movement: one-shot transform that inserts mouse-move steps
        # before position changes, so the cursor travels instead of teleporting.
        realistic_row = QHBoxLayout()
        self._realistic_btn = QPushButton("Add realistic movement")
        realistic_row.addWidget(self._realistic_btn)
        realistic_row.addStretch()
        layout.addLayout(realistic_row)

        # Options: repeat, randomization, hotkey
        options_group = QGroupBox("Options")
        options_form = QFormLayout(options_group)

        self._loop_check = QCheckBox("Loop until stopped")
        self._loop_check.setChecked(True)
        options_form.addRow(self._loop_check)

        self._repeat_spin = QSpinBox()
        self._repeat_spin.setRange(1, 1000000)
        self._repeat_spin.setValue(1)
        self._repeat_spin.setEnabled(False)
        options_form.addRow("Repeat count:", self._repeat_spin)

        self._repeat_delay_spin = QSpinBox()
        self._repeat_delay_spin.setRange(0, 3600000)
        self._repeat_delay_spin.setValue(0)
        self._repeat_delay_spin.setSuffix(" ms")
        options_form.addRow("Delay between repeats:", self._repeat_delay_spin)

        self._random_check = QCheckBox("Enable randomization")
        self._random_check.setChecked(True)
        options_form.addRow(self._random_check)

        self._hotkey_input = HotkeyInput(label="Trigger hotkey", input_id="macro_hotkey", parent=self)
        options_form.addRow(self._hotkey_input)

        layout.addWidget(options_group)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)

        # Save / cancel — pinned outside the scroll area so it's always
        # visible without needing to scroll down to it.
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(30, 12, 30, 20)
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("primaryButton")
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._save_btn)
        outer_layout.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self._add_btn.clicked.connect(self._on_add)
        self._action_list.itemDoubleClicked.connect(self._on_edit_item)
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn.clicked.connect(lambda: self._move(1))
        self._dup_btn.clicked.connect(self._on_duplicate)
        self._remove_btn.clicked.connect(self._on_remove)
        self._realistic_btn.clicked.connect(self._on_realistic_movement)
        self._loop_btn.clicked.connect(self._on_loop_selected)
        self._ungroup_btn.clicked.connect(self._on_ungroup)
        self._loop_check.toggled.connect(lambda looped: self._repeat_spin.setEnabled(not looped))
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit())

    # -- list helpers -------------------------------------------------------

    def _refresh_list(self, select_index: Optional[int] = None) -> None:
        self._action_list.clear()
        for i, item in enumerate(self._actions):
            self._action_list.addItem(QListWidgetItem(f"{i + 1}.  {summarize_item(item)}"))
        if select_index is not None and 0 <= select_index < self._action_list.count():
            self._action_list.setCurrentRow(select_index)

    def _selected_index(self) -> int:
        return self._action_list.currentRow()

    # -- action ops ---------------------------------------------------------

    def _on_add(self) -> None:
        kind = self._add_type_combo.currentData()
        dialog = ActionConfigDialog(kind, parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_actions = dialog.result_actions()
            if new_actions:
                self._actions.extend(new_actions)
                self._refresh_list(select_index=len(self._actions) - 1)

    def _on_edit_item(self, item: QListWidgetItem) -> None:
        idx = self._action_list.row(item)
        if idx < 0:
            return
        entry = self._actions[idx]

        # Double-clicking a loop edits its repeat count.
        if isinstance(entry, LoopBlock):
            count, ok = QInputDialog.getInt(
                self, "Loop count", "Repeat this block how many times?",
                entry.count, 1, 1_000_000,
            )
            if ok:
                entry.count = count
                self._refresh_list(select_index=idx)
            return

        kind = self._kind_for_action(entry)
        dialog = ActionConfigDialog(kind, existing=entry, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.result_action() is not None:
            self._actions[idx] = dialog.result_action()
            self._refresh_list(select_index=idx)

    def _selected_rows(self) -> List[int]:
        """Return the currently selected row indices, sorted ascending."""
        return sorted(i.row() for i in self._action_list.selectedIndexes())

    def _on_loop_selected(self) -> None:
        """Wrap the selected contiguous rows into a loop block."""
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Loop", "Select one or more steps to loop.")
            return
        if rows != list(range(rows[0], rows[-1] + 1)):
            QMessageBox.warning(self, "Loop", "Please select a contiguous range of steps.")
            return
        # Loops don't nest in the builder (keep it simple/legible).
        if any(isinstance(self._actions[r], LoopBlock) for r in rows):
            QMessageBox.warning(self, "Loop", "A selection that already contains a loop can't be looped again. Ungroup it first.")
            return

        count, ok = QInputDialog.getInt(
            self, "Loop count", "Repeat the selected steps how many times?", 2, 1, 1_000_000
        )
        if not ok:
            return

        start, end = rows[0], rows[-1]
        block = LoopBlock(count=count, actions=[a for a in self._actions[start:end + 1]])
        self._actions[start:end + 1] = [block]
        self._refresh_list(select_index=start)

    def _on_ungroup(self) -> None:
        """Expand the selected loop block back into its individual steps."""
        idx = self._selected_index()
        if idx < 0 or not isinstance(self._actions[idx], LoopBlock):
            QMessageBox.information(self, "Ungroup", "Select a loop to ungroup.")
            return
        block: LoopBlock = self._actions[idx]
        self._actions[idx:idx + 1] = list(block.actions)
        self._refresh_list(select_index=idx)

    def _kind_for_action(self, action: Action) -> str:
        if isinstance(action, ClickAction):
            return "click"
        if isinstance(action, MouseMoveAction):
            return "move"
        if isinstance(action, KeyPressAction):
            if action.action_type == ActionType.KEY_HOLD:
                return "key_hold"
            if action.action_type == ActionType.KEY_RELEASE:
                return "key_release"
            return "key_press"
        return "delay"

    def _move(self, delta: int) -> None:
        idx = self._selected_index()
        new_idx = idx + delta
        if idx < 0 or not (0 <= new_idx < len(self._actions)):
            return
        self._actions[idx], self._actions[new_idx] = self._actions[new_idx], self._actions[idx]
        self._refresh_list(select_index=new_idx)

    def _on_duplicate(self) -> None:
        idx = self._selected_index()
        if idx < 0:
            return
        # Deep-copy the action and give the clone a fresh id so the two remain
        # distinct entries.
        from src.models.base import generate_id
        clone = self._actions[idx].model_copy(deep=True)
        object.__setattr__(clone, "id", generate_id())
        self._actions.insert(idx + 1, clone)
        self._refresh_list(select_index=idx + 1)

    def _on_remove(self) -> None:
        idx = self._selected_index()
        if idx < 0:
            return
        self._actions.pop(idx)
        self._refresh_list(select_index=min(idx, len(self._actions) - 1))

    def _on_realistic_movement(self) -> None:
        """Insert mouse-move steps before position changes.

        Prompts once for a move speed, then walks the action list (recursing
        into loop blocks) inserting a MouseMoveAction before any fixed-position
        Click/Move whose target differs from the last known cursor position —
        so the cursor visibly travels there instead of teleporting.
        """
        if not self._actions:
            QMessageBox.information(self, "Realistic movement", "Add some steps first.")
            return
        speed, ok = QInputDialog.getInt(
            self, "Realistic movement", "Move speed for inserted steps (1-10):", 5, 1, 10
        )
        if not ok:
            return
        self._actions, _ = self._insert_realistic_moves(self._actions, speed)
        self._refresh_list()

    @staticmethod
    def _position_of(item) -> Optional[tuple]:
        """The static (x, y) an action targets, or None if it can't be known
        ahead of time (e.g. a cursor-position click, a key press, a delay)."""
        if isinstance(item, MouseMoveAction):
            return (item.x, item.y)
        if isinstance(item, ClickAction) and not item.use_cursor_position:
            return (item.x, item.y)
        return None

    def _insert_realistic_moves(
        self, items: List, speed: int, last_pos: Optional[tuple] = None
    ) -> tuple:
        """Return (new_items, last_pos) with realistic moves inserted.

        ``last_pos`` tracks the cursor's last known static position as the
        list is walked, so a second run (or a loop body) doesn't insert
        duplicate/no-op moves.
        """
        result: List = []
        for item in items:
            if isinstance(item, LoopBlock):
                item.actions, last_pos = self._insert_realistic_moves(item.actions, speed, last_pos)
                result.append(item)
                continue

            target = self._position_of(item)
            # Never insert a move immediately before an item that's already a
            # MouseMoveAction — it already *is* the travel step, so a second
            # move to the same spot ahead of it is always redundant. This is
            # what makes the transform idempotent on repeat runs.
            if target is not None and target != last_pos and not isinstance(item, MouseMoveAction):
                result.append(MouseMoveAction(x=target[0], y=target[1], speed=speed, smooth=True))
            result.append(item)

            if isinstance(item, ClickAction) and item.use_cursor_position:
                # Cursor-position clicks don't move the mouse, but we can't
                # know at build time where it'll actually be at run time.
                last_pos = None
            elif target is not None:
                last_pos = target
            # Key press/hold/release and delay actions don't change position.

        return result, last_pos

    # -- load / save --------------------------------------------------------

    def reset(self) -> None:
        self._macro_id = None
        self._is_editing = False
        self._actions = []
        self._title_label.setText("New Macro")
        self._name_input.clear()
        self._loop_check.setChecked(True)
        self._repeat_spin.setValue(1)
        self._repeat_delay_spin.setValue(0)
        self._random_check.setChecked(True)
        self._hotkey_input.set_hotkey("")
        self._refresh_list()

    def set_macro_id(self, macro_id: Optional[str]) -> None:
        if macro_id is None:
            self.reset()
            return
        try:
            macro = get_macro_service().get(macro_id)
        except Exception as e:
            self._logger.error(f"Failed to load macro {macro_id}: {e}")
            self.reset()
            return

        self._macro_id = macro_id
        self._is_editing = True
        self._title_label.setText("Edit Macro")
        self._name_input.setText(macro.name)
        self._actions = [a.model_copy(deep=True) for a in macro.actions]
        looped = macro.repeat_count == 0
        self._loop_check.setChecked(looped)
        self._repeat_spin.setEnabled(not looped)
        self._repeat_spin.setValue(macro.repeat_count if macro.repeat_count > 0 else 1)
        self._repeat_delay_spin.setValue(macro.repeat_delay_ms)
        self._random_check.setChecked(macro.randomization_enabled)
        self._hotkey_input.set_hotkey(macro.hotkey or "")
        self._refresh_list()

    def _on_save(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a macro name.")
            return
        if not self._actions:
            QMessageBox.warning(self, "No actions", "Add at least one action.")
            return

        repeat_count = 0 if self._loop_check.isChecked() else self._repeat_spin.value()
        hotkey = self._hotkey_input.get_hotkey() or None

        try:
            service = get_macro_service()
            if self._is_editing and self._macro_id:
                macro = service.get(self._macro_id)
                macro.name = name
                macro.actions = list(self._actions)
                macro.repeat_count = repeat_count
                macro.repeat_delay_ms = self._repeat_delay_spin.value()
                macro.randomization_enabled = self._random_check.isChecked()
                macro.hotkey = hotkey
                macro.touch()
            else:
                macro = Macro(
                    name=name,
                    actions=list(self._actions),
                    repeat_count=repeat_count,
                    repeat_delay_ms=self._repeat_delay_spin.value(),
                    randomization_enabled=self._random_check.isChecked(),
                    hotkey=hotkey,
                )
            service.save(macro)
        except Exception as e:
            self._logger.error(f"Failed to save macro: {e}")
            QMessageBox.critical(self, "Save failed", str(e))
            return

        self.save_requested.emit()
