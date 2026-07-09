"""
Full-screen position-capture overlay.

A pure-Qt replacement for the old pynput/AHK F2-capture flow, which proved
fragile (background threads, multiple listeners, window-minimize races). This
overlay is a single always-on-top translucent window spanning every monitor:
the user moves the mouse to the target and clicks to capture that screen
coordinate. Because the click lands on the overlay (not the app underneath), it
never triggers anything in the target window.

Signals:
    captured(int, int): emitted with the global (x, y) when the user clicks.
    cancelled():        emitted on Esc or right-click.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QCursor, QFont, QGuiApplication


class CaptureOverlay(QWidget):
    """Translucent, click-to-capture overlay covering the whole desktop."""

    captured = Signal(int, int)
    cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setWindowTitle("Capture Position")

        self._finished = False
        self.setGeometry(self._virtual_geometry())
        self._cursor_pos = QCursor.pos()

    @staticmethod
    def _virtual_geometry() -> QRect:
        """Union of every screen's geometry, so all monitors are covered."""
        rect = QRect()
        for screen in QGuiApplication.screens():
            rect = rect.united(screen.geometry())
        return rect

    # -- lifecycle ----------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.grabKeyboard()

    def _finish_capture(self) -> None:
        if self._finished:
            return
        self._finished = True
        pos = QCursor.pos()
        self.releaseKeyboard()
        self.captured.emit(pos.x(), pos.y())
        self.close()

    def _finish_cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.releaseKeyboard()
        self.cancelled.emit()
        self.close()

    # -- input --------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._cursor_pos = QCursor.pos()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._finish_capture()
        else:
            self._finish_cancel()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._finish_cancel()
        else:
            super().keyPressEvent(event)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Move the mouse to the target and CLICK to capture its position\n"
            "Right-click or press Esc to cancel",
        )

        # Live coordinate readout next to the cursor.
        local = self.mapFromGlobal(self._cursor_pos)
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(
            local.x() + 16,
            local.y() - 12,
            f"{self._cursor_pos.x()}, {self._cursor_pos.y()}",
        )
