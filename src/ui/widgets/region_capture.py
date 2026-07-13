"""
Region capture flow for screen-condition reference images.

Chains two point-captures with the proven-safe :class:`CapturePanel` (no
full-screen overlay — see that module's history note): first the region's
top-left corner, then its bottom-right. The rectangle is then screenshotted
via Qt and saved as a reference-image asset.

The owning top-level window is hidden for the duration of the flow so the
builder dialog can't end up inside the reference image; it is re-shown on
every exit path (success, cancel, or error).

DPI note: corner coordinates come from QCursor.pos() (logical pixels) while
grabWindow returns device pixels. At 100% Windows display scaling these
coincide; at 125/150% they don't, and a correction pass may be needed — the
devicePixelRatio is logged on every capture to diagnose exactly that.

Signals:
    captured(int, int, int, int, str): normalized region (x1, y1, x2, y2)
        plus the saved asset filename.
    cancelled(): the user backed out at either corner (or capture failed).
"""

from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from src.core.logger import get_logger
from src.services.image_asset_service import save_reference_pixmap
from src.ui.widgets.capture_overlay import CapturePanel

# Delay between the second panel's `captured` signal and the actual screen
# grab: the panel emits before it closes, so give the screen time to repaint
# without it.
_GRAB_SETTLE_MS = 250


class RegionCaptureFlow(QObject):
    """Two-point region capture that screenshots and saves the result."""

    captured = Signal(int, int, int, int, str)  # x1, y1, x2, y2, filename
    cancelled = Signal()

    def __init__(self, parent_widget: QWidget):
        """Initialize the flow.

        Args:
            parent_widget: Widget whose top-level window is hidden during
                capture; also parents the capture panels.
        """
        super().__init__(parent_widget)
        self._logger = get_logger("region_capture")
        self._parent_widget = parent_widget
        self._corner1: Optional[QPoint] = None
        self._finished = False

    def start(self) -> None:
        """Begin the flow: hide the owning window, capture corner one."""
        window = self._parent_widget.window()
        if window is not None:
            window.hide()
        self._show_panel(
            "Step 1/2: Move the mouse to the region's TOP-LEFT corner,\n"
            "click “Capture”, then hold still during the countdown.",
            "Capture Region — Top-Left",
            self._on_corner1,
        )

    # -- internal ------------------------------------------------------------

    def _show_panel(self, instruction: str, title: str, on_captured) -> None:
        panel = CapturePanel(self._parent_widget, instruction=instruction, title=title)
        panel.captured.connect(on_captured)
        panel.cancelled.connect(self._finish_cancel)
        panel.show()

    def _on_corner1(self, x: int, y: int) -> None:
        self._corner1 = QPoint(x, y)
        self._show_panel(
            "Step 2/2: Move the mouse to the region's BOTTOM-RIGHT corner,\n"
            "click “Capture”, then hold still during the countdown.",
            "Capture Region — Bottom-Right",
            self._on_corner2,
        )

    def _on_corner2(self, x: int, y: int) -> None:
        corner2 = QPoint(x, y)
        # Let the capture panel finish closing and the screen repaint before
        # grabbing, so the panel itself isn't in the reference image.
        QTimer.singleShot(_GRAB_SETTLE_MS, lambda: self._grab(self._corner1, corner2))

    def _grab(self, corner1: QPoint, corner2: QPoint) -> None:
        try:
            x1, x2 = sorted((corner1.x(), corner2.x()))
            y1, y2 = sorted((corner1.y(), corner2.y()))
            if x1 == x2 or y1 == y2:
                raise ValueError("The captured region has no area — the two corners must differ")

            screen1 = QGuiApplication.screenAt(corner1)
            screen2 = QGuiApplication.screenAt(corner2)
            screen = screen1 or QGuiApplication.primaryScreen()
            if screen1 is not None and screen2 is not None and screen1 is not screen2:
                raise ValueError("Both corners must be on the same monitor")

            geo = screen.geometry()
            self._logger.info(
                f"Grabbing region ({x1}, {y1})-({x2}, {y2}) on screen '{screen.name()}' "
                f"(devicePixelRatio={screen.devicePixelRatio()})"
            )
            pixmap = screen.grabWindow(
                0, x1 - geo.x(), y1 - geo.y(), x2 - x1 + 1, y2 - y1 + 1
            )
            filename = save_reference_pixmap(pixmap)
        except Exception as e:
            self._logger.error(f"Region capture failed: {e}")
            self._restore_window()
            QMessageBox.warning(self._parent_widget, "Capture failed", str(e))
            self._finish_cancel()
            return

        self._restore_window()
        if not self._finished:
            self._finished = True
            self.captured.emit(x1, y1, x2, y2, filename)

    def _finish_cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._restore_window()
        self.cancelled.emit()

    def _restore_window(self) -> None:
        window = self._parent_widget.window()
        if window is not None and not window.isVisible():
            window.show()
            window.raise_()
            window.activateWindow()
