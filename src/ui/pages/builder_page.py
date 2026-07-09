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
    QGroupBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.logger import get_logger
from src.core.event_bus import get_event_bus
from src.models.macro import Macro
from src.models.action import (
    Action,
    ActionType,
    ClickAction,
    DelayAction,
    KeyPressAction,
    MouseMoveAction,
)
from src.services.macro_service import get_macro_service
from src.services.position_capture_service import get_position_capture_service
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
        return f"{verb} @ {where}"
    if isinstance(action, MouseMoveAction):
        return f"Move to ({action.x}, {action.y}) · speed {action.speed}"
    if isinstance(action, KeyPressAction):
        if action.action_type == ActionType.KEY_HOLD:
            return f"Hold key '{action.key}'"
        if action.action_type == ActionType.KEY_RELEASE:
            return f"Release key '{action.key}'"
        combo = "+".join(list(action.modifiers) + [action.key]) if action.modifiers else action.key
        return f"Press '{combo}'"
    if isinstance(action, DelayAction):
        return f"Delay {action.duration_ms} ms"
    return "Unknown action"


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
        self._eventbus_connected = False

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
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("e.g. a, enter, space, f5")
        form.addRow("Key:", self._key_edit)

        if self._kind == "key_press":
            self._mod_checks = {}
            mod_row = QHBoxLayout()
            for mod in _MODIFIERS:
                cb = QCheckBox(mod)
                self._mod_checks[mod] = cb
                mod_row.addWidget(cb)
            container = QWidget()
            container.setLayout(mod_row)
            form.addRow("Modifiers:", container)

    def _build_delay_fields(self, form: QFormLayout) -> None:
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(0, 3600000)
        self._duration_spin.setValue(500)
        self._duration_spin.setSuffix(" ms")
        form.addRow("Duration:", self._duration_spin)

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
            self._key_edit.setText(action.key)
            if self._kind == "key_press":
                for mod, cb in self._mod_checks.items():
                    cb.setChecked(mod in action.modifiers)
        elif isinstance(action, DelayAction):
            self._duration_spin.setValue(action.duration_ms)

    # -- position capture ---------------------------------------------------

    def _on_cursor_toggled(self, use_cursor: bool) -> None:
        for w in (self._x_spin, self._y_spin, self._capture_btn):
            w.setEnabled(not use_cursor)

    def _start_capture(self) -> None:
        """Capture a screen position via F2 using the position capture service.

        Shows an always-on-top prompt; the dialog's own (modal) event loop keeps
        processing the queued position_captured / cancelled events, so no window
        needs to be minimised here.
        """
        try:
            service = get_position_capture_service()
        except RuntimeError as e:
            QMessageBox.warning(self, "Capture unavailable", str(e))
            return

        event_bus = get_event_bus()
        if not self._eventbus_connected:
            event_bus.position_captured.connect(self._on_position_captured)
            event_bus.position_capture_cancelled.connect(self._on_position_cancelled)
            self._eventbus_connected = True

        if not service.start_capture_delayed(capture_key="f2", timeout_ms=30000, delay_ms=100):
            return

        self._capture_prompt = QMessageBox(self)
        self._capture_prompt.setWindowTitle("Capture Position")
        self._capture_prompt.setText(
            "Move the mouse to the target and press F2.\nPress Esc to cancel."
        )
        self._capture_prompt.setStandardButtons(QMessageBox.NoButton)
        self._capture_prompt.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._capture_prompt.show()
        self._capture_prompt.raise_()

    def _close_capture_prompt(self) -> None:
        prompt = getattr(self, "_capture_prompt", None)
        if prompt is not None:
            prompt.close()
            self._capture_prompt = None

    def _on_position_captured(self, x: int, y: int) -> None:
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._close_capture_prompt()

    def _on_position_cancelled(self) -> None:
        self._close_capture_prompt()

    def _disconnect_eventbus(self) -> None:
        if not self._eventbus_connected:
            return
        self._eventbus_connected = False
        try:
            event_bus = get_event_bus()
            event_bus.position_captured.disconnect(self._on_position_captured)
            event_bus.position_capture_cancelled.disconnect(self._on_position_cancelled)
        except (RuntimeError, TypeError):
            pass

    # -- result -------------------------------------------------------------

    def _on_accept(self) -> None:
        try:
            self._result = self._build_action()
        except Exception as e:
            QMessageBox.warning(self, "Invalid action", str(e))
            return
        self._close_capture_prompt()
        self._disconnect_eventbus()
        self.accept()

    def reject(self) -> None:  # type: ignore[override]
        self._close_capture_prompt()
        self._disconnect_eventbus()
        super().reject()

    def _build_action(self) -> Action:
        if self._kind == "click":
            use_cursor = self._cursor_check.isChecked()
            action_type = ActionType.DOUBLE_CLICK if self._double_check.isChecked() else ActionType.CLICK
            return ClickAction(
                x=0 if use_cursor else self._x_spin.value(),
                y=0 if use_cursor else self._y_spin.value(),
                button=self._button_combo.currentText(),
                use_cursor_position=use_cursor,
                action_type=action_type,
            )
        if self._kind == "move":
            return MouseMoveAction(
                x=self._x_spin.value(),
                y=self._y_spin.value(),
                speed=self._speed_spin.value(),
                smooth=self._smooth_check.isChecked(),
            )
        if self._kind in ("key_press", "key_hold", "key_release"):
            key = self._key_edit.text().strip()
            if not key:
                raise ValueError("Key cannot be empty")
            if self._kind == "key_press":
                mods = [m for m, cb in self._mod_checks.items() if cb.isChecked()]
                return KeyPressAction(key=key, modifiers=mods, action_type=ActionType.KEY_PRESS)
            action_type = ActionType.KEY_HOLD if self._kind == "key_hold" else ActionType.KEY_RELEASE
            return KeyPressAction(key=key, action_type=action_type)
        if self._kind == "delay":
            return DelayAction(duration_ms=self._duration_spin.value())
        raise ValueError(f"Unknown action kind: {self._kind}")

    def result_action(self) -> Optional[Action]:
        return self._result


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
        layout = QVBoxLayout(self)
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
        for b in (self._up_btn, self._down_btn, self._dup_btn, self._remove_btn):
            side.addWidget(b)
        side.addStretch()
        list_row.addLayout(side)
        layout.addLayout(list_row, 1)

        # Auto-delay between steps
        autodelay_row = QHBoxLayout()
        autodelay_row.addWidget(QLabel("Insert delay between all steps:"))
        self._auto_delay_spin = QSpinBox()
        self._auto_delay_spin.setRange(0, 3600000)
        self._auto_delay_spin.setValue(0)
        self._auto_delay_spin.setSuffix(" ms")
        autodelay_row.addWidget(self._auto_delay_spin)
        self._insert_delays_btn = QPushButton("Insert")
        autodelay_row.addWidget(self._insert_delays_btn)
        autodelay_row.addStretch()
        layout.addLayout(autodelay_row)

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

        # Save / cancel
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("primaryButton")
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self._add_btn.clicked.connect(self._on_add)
        self._action_list.itemDoubleClicked.connect(self._on_edit_item)
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn.clicked.connect(lambda: self._move(1))
        self._dup_btn.clicked.connect(self._on_duplicate)
        self._remove_btn.clicked.connect(self._on_remove)
        self._insert_delays_btn.clicked.connect(self._on_insert_delays)
        self._loop_check.toggled.connect(lambda looped: self._repeat_spin.setEnabled(not looped))
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit())

    # -- list helpers -------------------------------------------------------

    def _refresh_list(self, select_index: Optional[int] = None) -> None:
        self._action_list.clear()
        for i, action in enumerate(self._actions):
            self._action_list.addItem(QListWidgetItem(f"{i + 1}.  {summarize_action(action)}"))
        if select_index is not None and 0 <= select_index < self._action_list.count():
            self._action_list.setCurrentRow(select_index)

    def _selected_index(self) -> int:
        return self._action_list.currentRow()

    # -- action ops ---------------------------------------------------------

    def _on_add(self) -> None:
        kind = self._add_type_combo.currentData()
        dialog = ActionConfigDialog(kind, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.result_action() is not None:
            self._actions.append(dialog.result_action())
            self._refresh_list(select_index=len(self._actions) - 1)

    def _on_edit_item(self, item: QListWidgetItem) -> None:
        idx = self._action_list.row(item)
        if idx < 0:
            return
        action = self._actions[idx]
        kind = self._kind_for_action(action)
        dialog = ActionConfigDialog(kind, existing=action, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.result_action() is not None:
            self._actions[idx] = dialog.result_action()
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

    def _on_insert_delays(self) -> None:
        """Interleave a delay of the configured duration between every step."""
        duration = self._auto_delay_spin.value()
        if duration <= 0 or len(self._actions) < 2:
            return
        interleaved: List[Action] = []
        for i, action in enumerate(self._actions):
            interleaved.append(action)
            if i < len(self._actions) - 1:
                interleaved.append(DelayAction(duration_ms=duration))
        self._actions = interleaved
        self._refresh_list()

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
        self._auto_delay_spin.setValue(0)
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
