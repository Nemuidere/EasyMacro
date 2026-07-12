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
    QTreeWidget,
    QTreeWidgetItem,
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
from PySide6.QtGui import QFont, QKeySequence, QShortcut

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


# Action kinds offered in the "Add action" dropdown. "input" covers keyboard
# keys AND mouse buttons (press/hold/release) in one unified dialog — those
# turned out to be the same underlying gesture with a different device.
# Move and Delay aren't a "press an input" gesture, so they stay separate.
ACTION_KINDS = [
    ("input", "Input (key / mouse click)"),
    ("move", "Move mouse"),
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
        if action.action_type == ActionType.CLICK_HOLD:
            where = "cursor pos" if action.use_cursor_position else f"({action.x}, {action.y})"
            base = f"Hold {action.button} button @ {where}"
        elif action.action_type == ActionType.CLICK_RELEASE:
            base = f"Release {action.button} button"
        else:
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


class _PositionCaptureMixin:
    """Mixin giving a dialog a "Capture position (F2)" button wired to the
    on-screen CapturePanel overlay. Host class must set self._x_spin /
    self._y_spin before calling _build_capture_button(), and must be a
    QWidget (used as the overlay's parent)."""

    def _build_capture_button(self) -> QPushButton:
        btn = QPushButton("Capture position (F2)")
        btn.clicked.connect(self._start_capture)
        return btn

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


class _DelayAfterFieldsMixin:
    """Mixin giving a dialog the shared "delay after this step" checkbox +
    ms/variance spinners, so a step can carry its own trailing delay instead
    of always needing a separate standalone Delay step after it."""

    def _build_delay_after_fields(self, form: QFormLayout) -> None:
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

    def _delay_after_kwargs(self) -> dict:
        ms = self._delay_after_ms.value() if self._delay_after_check.isChecked() else 0
        return dict(delay_after_ms=ms, delay_after_variance_percent=self._delay_after_variance.value())

    def _load_delay_after(self, action: Action) -> None:
        delay_after = getattr(action, "delay_after_ms", 0)
        if delay_after:
            self._delay_after_check.setChecked(True)
            self._delay_after_ms.setValue(delay_after)
            self._delay_after_variance.setValue(getattr(action, "delay_after_variance_percent", 5))


class ActionConfigDialog(QDialog, _PositionCaptureMixin, _DelayAfterFieldsMixin):
    """Modal dialog to create or edit a Move-mouse or Delay step.

    (Click/key/mouse-hold configuration lives in InputActionDialog — those
    turned out to be one "press an input" gesture, not four separate kinds.)
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

        if self._kind == "move":
            self._build_position_fields(form)
            self._build_move_fields(form)
        if self._kind == "delay":
            self._build_delay_fields(form)
        if self._kind != "delay":
            self._build_delay_after_fields(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_position_fields(self, form: QFormLayout) -> None:
        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, 100000)
        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, 100000)
        form.addRow("X:", self._x_spin)
        form.addRow("Y:", self._y_spin)
        form.addRow(self._build_capture_button())

    def _build_move_fields(self, form: QFormLayout) -> None:
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(1, 10)
        self._speed_spin.setValue(5)
        form.addRow("Speed (1-10):", self._speed_spin)

        self._smooth_check = QCheckBox("Smooth movement")
        self._smooth_check.setChecked(True)
        form.addRow(self._smooth_check)

    def _build_delay_fields(self, form: QFormLayout) -> None:
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(0, 3600000)
        self._duration_spin.setValue(500)
        self._duration_spin.setSuffix(" ms")
        form.addRow("Duration:", self._duration_spin)

    # -- load existing ------------------------------------------------------

    def _load_existing(self, action: Action) -> None:
        if isinstance(action, MouseMoveAction):
            self._x_spin.setValue(action.x)
            self._y_spin.setValue(action.y)
            self._speed_spin.setValue(action.speed)
            self._smooth_check.setChecked(action.smooth)
            self._load_delay_after(action)
        elif isinstance(action, DelayAction):
            self._duration_spin.setValue(action.duration_ms)

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
        if self._kind == "move":
            return MouseMoveAction(
                x=self._x_spin.value(),
                y=self._y_spin.value(),
                speed=self._speed_spin.value(),
                smooth=self._smooth_check.isChecked(),
                **self._delay_after_kwargs(),
            )
        raise ValueError(f"Unknown action kind: {self._kind}")

    def result_action(self) -> Optional[Action]:
        return self._result

    def result_actions(self) -> List[Action]:
        return [self._result] if self._result is not None else []


class InputActionDialog(QDialog, _PositionCaptureMixin, _DelayAfterFieldsMixin):
    """Unified dialog for a macro's "input" step: a keyboard key or a mouse
    button, pressed once, held (until released/stopped or for a fixed
    time), or released — with optional ctrl/alt/shift modifiers alongside
    it. Replaces the old separate Click / Key press / Key hold / Key
    release dialogs, which were the same underlying gesture (press an
    input, optionally hold it) with a different device.

    Only the fields relevant to the current Key-vs-Mouse and Press/Hold/
    Release choice are shown — the rest stay hidden via QFormLayout row
    visibility rather than cluttering the dialog with inactive fields.
    """

    def __init__(self, existing: Optional[Action] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._logger = get_logger("action_dialog")
        self._existing = existing
        self._result: Optional[Action] = None
        self._overlay = None

        self.setWindowTitle("Configure: Input")
        self.setModal(True)
        self.setMinimumWidth(380)

        self._build_ui()
        if existing is not None:
            self._load_existing(existing)
        self._update_visibility()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._form = QFormLayout()
        layout.addLayout(self._form)
        form = self._form

        # Source: keyboard key or mouse button.
        self._key_radio = QRadioButton("Keyboard key")
        self._mouse_radio = QRadioButton("Mouse button")
        self._key_radio.setChecked(True)
        source_group = QButtonGroup(self)
        source_group.addButton(self._key_radio)
        source_group.addButton(self._mouse_radio)
        source_row = QHBoxLayout()
        source_row.addWidget(self._key_radio)
        source_row.addWidget(self._mouse_radio)
        source_container = QWidget()
        source_container.setLayout(source_row)
        form.addRow("Input:", source_container)

        self._key_capture = KeyCaptureButton()
        form.addRow(self._key_capture)

        self._button_combo = QComboBox()
        self._button_combo.addItems(["left", "right", "middle"])
        form.addRow("Mouse button:", self._button_combo)

        # Position (mouse only — a keyboard key has no target).
        self._cursor_check = QCheckBox("Use current cursor position at run time")
        form.addRow(self._cursor_check)
        self._x_spin = QSpinBox()
        self._x_spin.setRange(0, 100000)
        self._y_spin = QSpinBox()
        self._y_spin.setRange(0, 100000)
        form.addRow("X:", self._x_spin)
        form.addRow("Y:", self._y_spin)
        self._capture_btn = self._build_capture_button()
        form.addRow(self._capture_btn)

        # Modifiers — apply to key or mouse input alike.
        self._mod_checks = {}
        mod_row = QHBoxLayout()
        for mod in _MODIFIERS:
            cb = QCheckBox(mod)
            self._mod_checks[mod] = cb
            mod_row.addWidget(cb)
        mod_container = QWidget()
        mod_container.setLayout(mod_row)
        form.addRow("Modifiers:", mod_container)

        # Double click (mouse + press-once only).
        self._double_check = QCheckBox("Double click")
        form.addRow(self._double_check)

        # Press / Hold / Release.
        self._press_radio = QRadioButton("Press once")
        self._hold_radio = QRadioButton("Hold")
        self._release_radio = QRadioButton("Release (a previously held key/button)")
        self._press_radio.setChecked(True)
        mode_group = QButtonGroup(self)
        for b in (self._press_radio, self._hold_radio, self._release_radio):
            mode_group.addButton(b)
            form.addRow(b)

        # Hold sub-mode: until released/stopped, or for a fixed time.
        self._hold_until_radio = QRadioButton("Hold until released / stopped")
        self._hold_for_radio = QRadioButton("Hold for a fixed time")
        self._hold_until_radio.setChecked(True)
        hold_mode_group = QButtonGroup(self)
        hold_mode_group.addButton(self._hold_until_radio)
        hold_mode_group.addButton(self._hold_for_radio)
        form.addRow(self._hold_until_radio)

        self._hold_ms = QSpinBox()
        self._hold_ms.setRange(1, 3_600_000)
        self._hold_ms.setValue(1000)
        self._hold_ms.setSuffix(" ms")
        self._hold_ms.setEnabled(False)
        self._hold_for_radio.toggled.connect(self._hold_ms.setEnabled)
        hold_for_row = QHBoxLayout()
        hold_for_row.addWidget(self._hold_for_radio)
        hold_for_row.addWidget(self._hold_ms)
        self._hold_for_container = QWidget()
        self._hold_for_container.setLayout(hold_for_row)
        form.addRow(self._hold_for_container)

        self._build_delay_after_fields(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for w in (self._key_radio, self._mouse_radio, self._press_radio, self._hold_radio, self._release_radio, self._cursor_check):
            w.toggled.connect(self._update_visibility)

    def _update_visibility(self) -> None:
        form = self._form
        is_mouse = self._mouse_radio.isChecked()
        is_hold = self._hold_radio.isChecked()
        is_release = self._release_radio.isChecked()
        use_cursor = self._cursor_check.isChecked()
        show_position = is_mouse and not is_release

        form.setRowVisible(self._key_capture, not is_mouse)
        form.setRowVisible(self._button_combo, is_mouse)

        form.setRowVisible(self._cursor_check, show_position)
        form.setRowVisible(self._x_spin, show_position and not use_cursor)
        form.setRowVisible(self._y_spin, show_position and not use_cursor)
        form.setRowVisible(self._capture_btn, show_position and not use_cursor)

        form.setRowVisible(self._double_check, is_mouse and not is_hold and not is_release)

        form.setRowVisible(self._hold_until_radio, is_hold)
        form.setRowVisible(self._hold_for_container, is_hold)

    # -- load existing ------------------------------------------------------

    def _load_existing(self, action: Action) -> None:
        if isinstance(action, KeyPressAction):
            self._key_radio.setChecked(True)
            self._key_capture.set_key(action.key)
            for mod, cb in self._mod_checks.items():
                cb.setChecked(mod in action.modifiers)
            if action.action_type == ActionType.KEY_HOLD:
                self._hold_radio.setChecked(True)
            elif action.action_type == ActionType.KEY_RELEASE:
                self._release_radio.setChecked(True)
            else:
                self._press_radio.setChecked(True)
        elif isinstance(action, ClickAction):
            self._mouse_radio.setChecked(True)
            self._cursor_check.setChecked(action.use_cursor_position)
            self._x_spin.setValue(action.x)
            self._y_spin.setValue(action.y)
            idx = self._button_combo.findText(action.button)
            if idx >= 0:
                self._button_combo.setCurrentIndex(idx)
            for mod, cb in self._mod_checks.items():
                cb.setChecked(mod in action.modifiers)
            self._double_check.setChecked(action.action_type == ActionType.DOUBLE_CLICK)
            if action.action_type == ActionType.CLICK_HOLD:
                self._hold_radio.setChecked(True)
            elif action.action_type == ActionType.CLICK_RELEASE:
                self._release_radio.setChecked(True)
            else:
                self._press_radio.setChecked(True)

        self._load_delay_after(action)

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
        mods = [m for m, cb in self._mod_checks.items() if cb.isChecked()]
        delay_kwargs = self._delay_after_kwargs()

        if self._key_radio.isChecked():
            key = self._key_capture.key().strip()
            if not key:
                raise ValueError("No key captured — click 'Key' and press a key")
            if self._release_radio.isChecked():
                action_type = ActionType.KEY_RELEASE
            elif self._hold_radio.isChecked():
                action_type = ActionType.KEY_HOLD
            else:
                action_type = ActionType.KEY_PRESS
            return KeyPressAction(key=key, modifiers=mods, action_type=action_type, **delay_kwargs)

        is_release = self._release_radio.isChecked()
        use_cursor = self._cursor_check.isChecked() and not is_release
        if is_release:
            action_type = ActionType.CLICK_RELEASE
        elif self._hold_radio.isChecked():
            action_type = ActionType.CLICK_HOLD
        else:
            action_type = ActionType.DOUBLE_CLICK if self._double_check.isChecked() else ActionType.CLICK
        return ClickAction(
            x=0 if (use_cursor or is_release) else self._x_spin.value(),
            y=0 if (use_cursor or is_release) else self._y_spin.value(),
            button=self._button_combo.currentText(),
            modifiers=mods,
            use_cursor_position=use_cursor,
            action_type=action_type,
            **delay_kwargs,
        )

    def result_action(self) -> Optional[Action]:
        return self._result

    def result_actions(self) -> List[Action]:
        """Return the action(s) this dialog produced.

        Usually a single action, but "hold for a fixed time" expands into
        three visible steps — hold, delay, release — so the timed hold is
        transparent and editable in the list, for both keys and mouse
        buttons.
        """
        if self._result is None:
            return []
        if self._hold_radio.isChecked() and self._hold_for_radio.isChecked():
            hold = self._result
            if isinstance(hold, KeyPressAction):
                release: Action = KeyPressAction(
                    key=hold.key, modifiers=list(hold.modifiers), action_type=ActionType.KEY_RELEASE,
                )
            else:
                release = ClickAction(
                    x=hold.x, y=hold.y, button=hold.button, modifiers=list(hold.modifiers),
                    use_cursor_position=hold.use_cursor_position, action_type=ActionType.CLICK_RELEASE,
                )
            return [hold, DelayAction(duration_ms=self._hold_ms.value()), release]
        return [self._result]


class RealisticMovementDialog(QDialog):
    """Prompt for the "Add realistic movement" transform.

    Asks for a move speed and whether to also connect each loop's (and the
    macro's) last step back to its first, so wrapping around on repeat
    doesn't teleport the cursor.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Realistic movement")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 10)
        self.speed_spin.setValue(5)
        form.addRow("Move speed (1-10):", self.speed_spin)

        self.loop_check = QCheckBox("Account for macro loops")
        self.loop_check.setToolTip(
            "A macro usually ends somewhere different from where it started. "
            "When checked, a move back to the start is added at the end of "
            "every loop (and the macro itself, if it repeats), instead of "
            "teleporting there on the next pass."
        )
        form.addRow(self.loop_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ActionTreeWidget(QTreeWidget):
    """QTreeWidget with internal drag-and-drop reordering/reparenting.

    Steps — including a whole loop block with everything inside it — can be
    dragged to reorder them, or dropped onto a loop row to move them inside
    it / dragged out to un-nest them. Qt performs the visual move itself;
    this just emits `dropped` afterward so the owning page can resync its
    model (self._actions) from the tree's new structure.
    """

    dropped = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().dropEvent(event)
        self.dropped.emit()


class MacroBuilderPage(QWidget):
    """Page for assembling a macro from an ordered list of actions."""

    save_requested = Signal()
    cancel_requested = Signal()

    _UNDO_LIMIT = 20
    # Second data role (alongside the path, at UserRole) storing a direct
    # reference to the underlying model object on each tree row — used to
    # rebuild self._actions after a drag-and-drop move, when the tree's
    # structure changes without going through any of our own mutation code.
    _OBJECT_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("builderPage")
        self._logger = get_logger("builder_page")

        self._actions: List[Action] = []
        self._macro_id: Optional[str] = None
        self._is_editing = False
        # Snapshots of self._actions taken before each mutating op, for Undo.
        # Covers the step list only (add/remove/move/duplicate/loop/ungroup/
        # edit/realistic-movement/drag-drop) — not name/hotkey/repeat/
        # randomization settings.
        self._undo_stack: List[List[Action]] = []

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

        self._action_list = ActionTreeWidget()
        self._action_list.setObjectName("actionList")
        self._action_list.setHeaderHidden(True)
        self._action_list.setIndentation(18)
        # Double-click always means "edit this step" (including opening the
        # loop-count dialog for a loop row) — don't also toggle expand/
        # collapse underneath it, which felt jarring together.
        self._action_list.setExpandsOnDoubleClick(False)
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

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setEnabled(False)
        self._undo_btn.setToolTip("Undo the last change to the step list (Ctrl+Z)")

        button_grid = QGridLayout()
        button_grid.setSpacing(8)
        button_grid.addWidget(self._up_btn, 0, 0)
        button_grid.addWidget(self._down_btn, 0, 1)
        button_grid.addWidget(self._dup_btn, 1, 0)
        button_grid.addWidget(self._remove_btn, 1, 1)
        button_grid.addWidget(self._loop_btn, 2, 0)
        button_grid.addWidget(self._ungroup_btn, 2, 1)
        button_grid.addWidget(self._undo_btn, 3, 0, 1, 2)
        side.addLayout(button_grid)
        side.addStretch()

        # Allow selecting a contiguous range of sibling rows (at any nesting
        # depth) to group into a loop.
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
        self._undo_btn.clicked.connect(self._on_undo)
        self._action_list.dropped.connect(self._on_tree_dropped)
        self._loop_check.toggled.connect(lambda looped: self._repeat_spin.setEnabled(not looped))
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit())

        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._on_undo)

    # -- tree helpers ---------------------------------------------------------
    #
    # Steps are addressed by "path": a list of indices from the macro root
    # down through nested LoopBlock bodies, e.g. [2, 1, 0] means "top-level
    # item 2's .actions[1]'s .actions[0]". This is what lets Move/Duplicate/
    # Remove/Loop/Ungroup work uniformly at any nesting depth. The tree is
    # always fully rebuilt from self._actions after a mutation (like the old
    # flat list was) — simplest way to keep it in sync.

    def _refresh_list(self, select_path: Optional[List[int]] = None) -> None:
        self._action_list.clear()
        self._populate_tree(self._action_list, self._actions, [])
        self._action_list.expandAll()
        if select_path:
            item = self._tree_item_at_path(select_path)
            if item is not None:
                self._action_list.setCurrentItem(item)

    def _populate_tree(self, parent, items: List, path_prefix: List[int]) -> None:
        """Recursively build tree rows for `items` under `parent` (either the
        QTreeWidget itself, for the top level, or a QTreeWidgetItem)."""
        for i, item in enumerate(items):
            path = path_prefix + [i]
            if isinstance(item, LoopBlock):
                node = QTreeWidgetItem([f"⟳  Loop  ×{item.count}"])
                bold = node.font(0)
                bold.setBold(True)
                node.setFont(0, bold)
                node.setData(0, Qt.ItemDataRole.UserRole, path)
                node.setData(0, self._OBJECT_ROLE, item)
                self._add_tree_node(parent, node)
                self._populate_tree(node, item.actions, path)
            else:
                leaf = QTreeWidgetItem([summarize_action(item)])
                leaf.setData(0, Qt.ItemDataRole.UserRole, path)
                leaf.setData(0, self._OBJECT_ROLE, item)
                # A leaf step can't contain other steps — only accept drops
                # that land beside it (as a sibling), not "into" it.
                leaf.setFlags(leaf.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
                self._add_tree_node(parent, leaf)

    @staticmethod
    def _add_tree_node(parent, node: QTreeWidgetItem) -> None:
        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(node)
        else:
            parent.addChild(node)

    def _tree_item_at_path(self, path: List[int]) -> Optional[QTreeWidgetItem]:
        if not path:
            return None
        node = self._action_list.topLevelItem(path[0])
        for idx in path[1:]:
            if node is None:
                return None
            node = node.child(idx)
        return node

    def _selected_path(self) -> Optional[List[int]]:
        item = self._action_list.currentItem()
        if item is None:
            return None
        return list(item.data(0, Qt.ItemDataRole.UserRole))

    def _selected_paths(self) -> List[List[int]]:
        return [list(i.data(0, Qt.ItemDataRole.UserRole)) for i in self._action_list.selectedItems()]

    def _container_for_path(self, path: List[int]) -> List:
        """The list that directly holds the item addressed by `path` — i.e.
        every index but the last, walked through nested LoopBlock.actions."""
        container = self._actions
        for idx in path[:-1]:
            container = container[idx].actions
        return container

    def _on_tree_dropped(self) -> None:
        """Resync self._actions after a drag-and-drop move.

        Qt's InternalMove drag-drop rearranges QTreeWidgetItems directly —
        self._actions is untouched at this point, so this is still the
        pre-drop state and the right moment to snapshot for Undo. Each item
        still carries a reference to its original model object (_OBJECT_ROLE
        survives the move), so rebuilding self._actions is just a matter of
        walking the tree's new shape and reading those references back.
        """
        self._push_undo()
        self._actions = self._read_tree_as_actions(self._action_list)
        self._refresh_list()

    def _read_tree_as_actions(self, parent) -> List:
        """Rebuild a MacroItem list from the current tree structure under
        `parent` (the QTreeWidget itself, or a QTreeWidgetItem), recursing
        into loop rows and replacing their .actions with their new children.
        """
        is_root = isinstance(parent, QTreeWidget)
        count = parent.topLevelItemCount() if is_root else parent.childCount()
        get_child = parent.topLevelItem if is_root else parent.child

        result: List = []
        for i in range(count):
            node = get_child(i)
            obj = node.data(0, self._OBJECT_ROLE)
            if isinstance(obj, LoopBlock):
                obj.actions = self._read_tree_as_actions(node)
            result.append(obj)
        return result

    # -- undo -----------------------------------------------------------------

    def _push_undo(self) -> None:
        """Snapshot the current step list before a mutation, so Undo can
        restore it. Capped at _UNDO_LIMIT entries (oldest dropped first)."""
        snapshot = [a.model_copy(deep=True) for a in self._actions]
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._undo_btn.setEnabled(True)

    def _on_undo(self) -> None:
        if not self._undo_stack:
            return
        self._actions = self._undo_stack.pop()
        self._refresh_list()
        self._undo_btn.setEnabled(bool(self._undo_stack))

    # -- action ops ---------------------------------------------------------

    def _on_add(self) -> None:
        kind = self._add_type_combo.currentData()
        if kind == "input":
            dialog = InputActionDialog(parent=self)
        else:
            dialog = ActionConfigDialog(kind, parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_actions = dialog.result_actions()
            if not new_actions:
                return
            self._push_undo()
            container, index, parent_path = self._add_insertion_point()
            container[index:index] = new_actions
            self._refresh_list(select_path=parent_path + [index + len(new_actions) - 1])

    def _add_insertion_point(self) -> tuple:
        """Where a new step from "Add" should land: (container, index,
        parent_path) — new items are inserted at container[index:index],
        with parent_path the path prefix to that container (empty for the
        top level).

        - Nothing selected → end of the top-level list (old behaviour).
        - A loop selected → end of *that loop's own body*, so you can select
          a loop and keep adding steps into it.
        - A step selected → right after it, in whatever list it's already
          in (top-level or inside a loop), so repeatedly selecting the step
          you just added and hitting Add builds a sequence in place.
        """
        path = self._selected_path()
        if path is None:
            return self._actions, len(self._actions), []

        container = self._container_for_path(path)
        idx = path[-1]
        entry = container[idx]
        if isinstance(entry, LoopBlock):
            return entry.actions, len(entry.actions), path
        return container, idx + 1, path[:-1]

    def _on_edit_item(self, item: QTreeWidgetItem, column: int = 0) -> None:
        path = list(item.data(0, Qt.ItemDataRole.UserRole))
        container = self._container_for_path(path)
        idx = path[-1]
        entry = container[idx]

        # Double-clicking a loop edits its repeat count.
        if isinstance(entry, LoopBlock):
            count, ok = QInputDialog.getInt(
                self, "Loop count", "Repeat this block how many times?",
                entry.count, 1, 1_000_000,
            )
            if ok:
                self._push_undo()
                entry.count = count
                self._refresh_list(select_path=path)
            return

        dialog = self._dialog_for_existing(entry)
        if dialog.exec() == QDialog.Accepted and dialog.result_action() is not None:
            self._push_undo()
            container[idx] = dialog.result_action()
            self._refresh_list(select_path=path)

    def _dialog_for_existing(self, action: Action) -> QDialog:
        if isinstance(action, (ClickAction, KeyPressAction)):
            return InputActionDialog(existing=action, parent=self)
        if isinstance(action, MouseMoveAction):
            return ActionConfigDialog("move", existing=action, parent=self)
        return ActionConfigDialog("delay", existing=action, parent=self)

    def _on_loop_selected(self) -> None:
        """Wrap the selected contiguous sibling rows into a loop block.

        Loops can nest: a selection may already contain loop blocks, which
        simply become part of the new outer loop's body.
        """
        paths = self._selected_paths()
        if not paths:
            QMessageBox.information(self, "Loop", "Select one or more steps to loop.")
            return
        parent_path = paths[0][:-1]
        if any(p[:-1] != parent_path for p in paths):
            QMessageBox.warning(self, "Loop", "Select steps that are all at the same level (siblings).")
            return
        indices = sorted(p[-1] for p in paths)
        if indices != list(range(indices[0], indices[-1] + 1)):
            QMessageBox.warning(self, "Loop", "Please select a contiguous range of steps.")
            return

        count, ok = QInputDialog.getInt(
            self, "Loop count", "Repeat the selected steps how many times?", 2, 1, 1_000_000
        )
        if not ok:
            return

        self._push_undo()
        container = self._container_for_path(parent_path + [indices[0]])
        start, end = indices[0], indices[-1]
        block = LoopBlock(count=count, actions=[a for a in container[start:end + 1]])
        container[start:end + 1] = [block]
        self._refresh_list(select_path=parent_path + [start])

    def _on_ungroup(self) -> None:
        """Expand the selected loop block back into its individual steps
        (one level — a loop nested inside it stays intact and can be
        ungrouped again separately)."""
        path = self._selected_path()
        if path is None:
            QMessageBox.information(self, "Ungroup", "Select a loop to ungroup.")
            return
        container = self._container_for_path(path)
        idx = path[-1]
        entry = container[idx]
        if not isinstance(entry, LoopBlock):
            QMessageBox.information(self, "Ungroup", "Select a loop to ungroup.")
            return
        self._push_undo()
        container[idx:idx + 1] = list(entry.actions)
        parent_path = path[:-1]
        select_path = (parent_path + [idx]) if entry.actions else (parent_path or None)
        self._refresh_list(select_path=select_path)

    def _move(self, delta: int) -> None:
        path = self._selected_path()
        if path is None:
            return
        container = self._container_for_path(path)
        idx = path[-1]
        new_idx = idx + delta
        if not (0 <= new_idx < len(container)):
            return
        self._push_undo()
        container[idx], container[new_idx] = container[new_idx], container[idx]
        self._refresh_list(select_path=path[:-1] + [new_idx])

    def _on_duplicate(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        container = self._container_for_path(path)
        idx = path[-1]
        # Deep-copy the item and give it (and any nested children, for a
        # loop block) a fresh id so the clone doesn't share identity with
        # its source.
        self._push_undo()
        clone = container[idx].model_copy(deep=True)
        self._reassign_ids(clone)
        container.insert(idx + 1, clone)
        self._refresh_list(select_path=path[:-1] + [idx + 1])

    def _reassign_ids(self, item) -> None:
        from src.models.base import generate_id
        object.__setattr__(item, "id", generate_id())
        if isinstance(item, LoopBlock):
            for child in item.actions:
                self._reassign_ids(child)

    def _on_remove(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        container = self._container_for_path(path)
        idx = path[-1]
        self._push_undo()
        container.pop(idx)
        parent_path = path[:-1]
        select_path = (parent_path + [min(idx, len(container) - 1)]) if container else (parent_path or None)
        self._refresh_list(select_path=select_path)

    def _on_realistic_movement(self) -> None:
        """Insert mouse-move steps before position changes.

        Prompts once for a move speed and whether to also connect loop ends
        back to their starts, then walks the action list (recursing into
        loop blocks at any depth) inserting a MouseMoveAction before any
        fixed-position Click/Move whose target differs from the last known
        cursor position — so the cursor visibly travels there instead of
        teleporting.
        """
        if not self._actions:
            QMessageBox.information(self, "Realistic movement", "Add some steps first.")
            return
        options = self._prompt_realistic_movement_options()
        if options is None:
            return
        speed, account_for_loop = options

        self._push_undo()
        self._actions, _ = self._insert_realistic_moves(self._actions, speed)
        if account_for_loop:
            self._connect_loop_ends(self._actions, speed)
        self._refresh_list()

    def _prompt_realistic_movement_options(self) -> Optional[tuple]:
        """Ask for move speed + "account for macro loops". Returns
        (speed, account_for_loop), or None if cancelled. Split out from
        _on_realistic_movement so tests can stub the prompt directly instead
        of driving a real modal dialog."""
        dialog = RealisticMovementDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.speed_spin.value(), dialog.loop_check.isChecked()

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

    def _connect_loop_ends(self, items: List, speed: int, top_level: bool = True) -> None:
        """Append a move back to the start at the end of every loop body that
        will actually repeat (count > 1), and — if the macro itself is set to
        loop/repeat — at the very end of the top-level list too. Recurses to
        any nesting depth; run after _insert_realistic_moves so it sees the
        already-inserted moves.
        """
        for item in items:
            if isinstance(item, LoopBlock):
                self._connect_loop_ends(item.actions, speed, top_level=False)
                if item.count > 1:
                    self._append_loop_connector(item.actions, speed)

        if top_level:
            macro_will_repeat = self._loop_check.isChecked() or self._repeat_spin.value() > 1
            if macro_will_repeat:
                self._append_loop_connector(items, speed)

    @staticmethod
    def _append_loop_connector(items: List, speed: int) -> None:
        """Append a MouseMoveAction back to `items`' own first known
        position, if its last known position differs from it. No-op if
        either end is unknowable or they already match — which is what
        keeps this idempotent on repeat runs.
        """
        if not items:
            return
        first_pos = MacroBuilderPage._first_known_position(items)
        last_pos = MacroBuilderPage._last_known_position(items)
        if first_pos is None or last_pos is None or first_pos == last_pos:
            return
        items.append(MouseMoveAction(x=first_pos[0], y=first_pos[1], speed=speed, smooth=True))

    @staticmethod
    def _first_known_position(items: List) -> Optional[tuple]:
        for item in items:
            if isinstance(item, LoopBlock):
                pos = MacroBuilderPage._first_known_position(item.actions)
                if pos is not None:
                    return pos
                continue
            pos = MacroBuilderPage._position_of(item)
            if pos is not None:
                return pos
        return None

    @staticmethod
    def _last_known_position(items: List) -> Optional[tuple]:
        for item in reversed(items):
            if isinstance(item, LoopBlock):
                pos = MacroBuilderPage._last_known_position(item.actions)
                if pos is not None:
                    return pos
                continue
            pos = MacroBuilderPage._position_of(item)
            if pos is not None:
                return pos
        return None

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
        self._undo_stack = []
        self._undo_btn.setEnabled(False)
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
        self._undo_stack = []
        self._undo_btn.setEnabled(False)
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
