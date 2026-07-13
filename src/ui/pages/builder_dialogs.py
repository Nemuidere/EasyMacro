"""
Dialogs for the screen-condition steps (wait / if / while).

Split out of builder_page.py (which holds the older action dialogs) to keep
that module from growing further. All three follow the house dialog pattern:
``_on_accept`` builds the model inside try/except and pops a
``QMessageBox.warning`` on validation failure; results are exposed through
``result_actions()`` / ``result_action()``.

The If/While dialogs configure only the block's *condition and caps* — the
bodies are edited in the builder's step tree, not here.
"""

from typing import List, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.logger import get_logger
from src.models.action import IfBlock, ImageCondition, WaitAction, WhileBlock
from src.ui.widgets.image_condition_widget import ImageConditionWidget


class _ConditionDialogBase(QDialog):
    """Shared skeleton: a condition widget on top, extra fields below, OK/Cancel."""

    _TITLE = "Configure condition"

    def __init__(self, existing=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._logger = get_logger("builder_dialogs")
        self._existing = existing
        self._result = None

        self.setWindowTitle(self._TITLE)
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        self._condition_widget = ImageConditionWidget(self)
        layout.addWidget(self._condition_widget)

        form = QFormLayout()
        layout.addLayout(form)
        self._build_extra_fields(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing is not None:
            self._condition_widget.load(existing.condition)
            self._load_extra_fields(existing)

    def _build_extra_fields(self, form: QFormLayout) -> None:
        """Add the subclass's non-condition fields to the form."""

    def _load_extra_fields(self, existing) -> None:
        """Populate the subclass's fields from an existing model (edit mode)."""

    def _build_result(self):
        """Build and return the result model. Raises on invalid input."""
        raise NotImplementedError

    def _on_accept(self) -> None:
        try:
            self._result = self._build_result()
        except Exception as e:
            QMessageBox.warning(self, "Invalid condition", str(e))
            return
        self.accept()

    def result_action(self):
        return self._result

    def result_actions(self) -> List:
        return [self._result] if self._result is not None else []


class WaitForImageDialog(_ConditionDialogBase):
    """Create/edit a wait-for-image step."""

    _TITLE = "Wait for image"

    def _build_extra_fields(self, form: QFormLayout) -> None:
        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(20, 60000)
        self._poll_spin.setValue(200)
        self._poll_spin.setSuffix(" ms")
        form.addRow("Check every:", self._poll_spin)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(0, 3600000)
        self._timeout_spin.setValue(0)
        self._timeout_spin.setSuffix(" ms")
        self._timeout_spin.setSpecialValueText("No timeout")
        form.addRow("Timeout:", self._timeout_spin)

        self._on_timeout_combo = QComboBox()
        self._on_timeout_combo.addItem("Stop with error", "error")
        self._on_timeout_combo.addItem("Continue macro", "continue")
        form.addRow("On timeout:", self._on_timeout_combo)

    def _load_extra_fields(self, existing: WaitAction) -> None:
        self._poll_spin.setValue(existing.poll_interval_ms)
        self._timeout_spin.setValue(existing.timeout_ms)
        self._on_timeout_combo.setCurrentIndex(0 if existing.on_timeout == "error" else 1)

    def _build_result(self) -> WaitAction:
        return WaitAction(
            condition=self._condition_widget.condition(),
            poll_interval_ms=self._poll_spin.value(),
            timeout_ms=self._timeout_spin.value(),
            on_timeout=self._on_timeout_combo.currentData(),
        )


class IfBlockDialog(_ConditionDialogBase):
    """Create an If block, or edit an existing one's condition.

    On edit, callers must replace only ``entry.condition`` with
    ``result_condition()`` so the block's then/else bodies are preserved.
    """

    _TITLE = "If image condition"

    def _build_result(self) -> IfBlock:
        return IfBlock(condition=self._condition_widget.condition())

    def result_condition(self) -> Optional[ImageCondition]:
        """The configured condition alone (for in-place edits)."""
        return self._result.condition if self._result is not None else None


class WhileBlockDialog(_ConditionDialogBase):
    """Create a While block, or edit an existing one's condition and caps.

    On edit, callers must copy ``condition`` and the cap fields onto the
    existing block so its body is preserved.
    """

    _TITLE = "While image condition"

    def _build_extra_fields(self, form: QFormLayout) -> None:
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(0, 86400)
        self._timeout_spin.setValue(0)
        self._timeout_spin.setSuffix(" s")
        self._timeout_spin.setSpecialValueText("Unlimited")
        form.addRow("Stop after:", self._timeout_spin)

        self._max_iter_spin = QSpinBox()
        self._max_iter_spin.setRange(0, 1000000)
        self._max_iter_spin.setValue(0)
        self._max_iter_spin.setSpecialValueText("Unlimited")
        form.addRow("Max iterations:", self._max_iter_spin)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(20, 60000)
        self._interval_spin.setValue(100)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.setToolTip(
            "Minimum delay between condition re-checks, so a fast loop body\n"
            "can't re-run the screen search continuously."
        )
        form.addRow("Re-check every:", self._interval_spin)

    def _load_extra_fields(self, existing: WhileBlock) -> None:
        self._timeout_spin.setValue(existing.timeout_seconds)
        self._max_iter_spin.setValue(existing.max_iterations)
        self._interval_spin.setValue(max(existing.check_interval_ms, 20))

    def _build_result(self) -> WhileBlock:
        return WhileBlock(
            condition=self._condition_widget.condition(),
            timeout_seconds=self._timeout_spin.value(),
            max_iterations=self._max_iter_spin.value(),
            check_interval_ms=self._interval_spin.value(),
        )
