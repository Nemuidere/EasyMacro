"""
Shared "screen condition" form section.

Used by the If / While / Wait dialogs: a capture button that runs the
two-point :class:`RegionCaptureFlow`, a thumbnail preview of the captured
reference image, the region readout, a found/not-found selector (negate),
and a color-tolerance spinner.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from src.models.action import ImageCondition
from src.services.image_asset_service import asset_path
from src.ui.widgets.region_capture import RegionCaptureFlow

_THUMB_MAX_W = 200
_THUMB_MAX_H = 120


class ImageConditionWidget(QWidget):
    """Form section for building/editing an ImageCondition."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._region: Optional[tuple[int, int, int, int]] = None
        self._image_file: Optional[str] = None

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)

        self._capture_btn = QPushButton("Capture region…")
        self._capture_btn.clicked.connect(self._on_capture_clicked)
        form.addRow(self._capture_btn)

        self._thumbnail = QLabel("No region captured yet")
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setMinimumHeight(60)
        form.addRow(self._thumbnail)

        self._region_label = QLabel("Region: —")
        form.addRow(self._region_label)

        self._match_combo = QComboBox()
        self._match_combo.addItem("Image is found", False)
        self._match_combo.addItem("Image is NOT found", True)
        form.addRow("Match when:", self._match_combo)

        self._tolerance_spin = QSpinBox()
        self._tolerance_spin.setRange(0, 255)
        self._tolerance_spin.setValue(20)
        self._tolerance_spin.setToolTip(
            "Allowed per-channel color difference when matching pixels.\n"
            "0 = exact match only; higher tolerates shading/anti-aliasing drift."
        )
        form.addRow("Color tolerance:", self._tolerance_spin)

    # -- public API -----------------------------------------------------------

    def load(self, condition: ImageCondition) -> None:
        """Populate the widget from an existing condition (edit mode)."""
        self._image_file = condition.image_file
        self._region = (condition.x1, condition.y1, condition.x2, condition.y2)
        self._match_combo.setCurrentIndex(1 if condition.negate else 0)
        self._tolerance_spin.setValue(condition.color_variation)
        self._refresh_preview()

    def condition(self) -> ImageCondition:
        """Build the ImageCondition from the current widget state.

        Raises:
            ValueError: If no region has been captured yet.
        """
        if self._region is None or self._image_file is None:
            raise ValueError("Capture a screen region first")
        x1, y1, x2, y2 = self._region
        return ImageCondition(
            image_file=self._image_file,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            color_variation=self._tolerance_spin.value(),
            negate=bool(self._match_combo.currentData()),
        )

    # -- internal ---------------------------------------------------------------

    def _on_capture_clicked(self) -> None:
        flow = RegionCaptureFlow(self)
        flow.captured.connect(self._on_region_captured)
        flow.start()

    def _on_region_captured(self, x1: int, y1: int, x2: int, y2: int, filename: str) -> None:
        # A recapture just points at the new asset file; the old one stays on
        # disk (write-once lifecycle, see image_asset_service).
        self._region = (x1, y1, x2, y2)
        self._image_file = filename
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self._region is None or self._image_file is None:
            return
        x1, y1, x2, y2 = self._region
        self._region_label.setText(f"Region: ({x1}, {y1}) – ({x2}, {y2})")
        pixmap = QPixmap(str(asset_path(self._image_file)))
        if pixmap.isNull():
            self._thumbnail.setText(f"(preview unavailable: {self._image_file})")
            return
        self._thumbnail.setPixmap(
            pixmap.scaled(
                _THUMB_MAX_W,
                _THUMB_MAX_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
