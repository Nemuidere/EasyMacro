"""
Position-capture panel.

A small, always-closeable always-on-top window for picking a screen coordinate.
It replaces the earlier full-screen overlay, which could trap the user (it grabbed
the keyboard and covered every monitor, and on some setups neither Esc nor the
mouse click reached it — the only way out was killing the process).

Safety-first design — it can ALWAYS be dismissed:
  * a normal window frame (native close button),
  * a visible Cancel button,
  * Esc,
  * a hard safety timeout that auto-cancels,
  * no keyboard grab, no full-screen, no mouse grab.

To capture an arbitrary point (including under other windows) without the panel
stealing the click, capture happens on a short **countdown**: the user moves the
cursor to the target, presses Capture, holds still, and the global cursor
position is read when the countdown reaches zero. A live readout helps aiming.

Signals:
    captured(int, int): the chosen global (x, y).
    cancelled():        dismissed without capturing.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor, QFont


_COUNTDOWN_SECONDS = 3
_SAFETY_TIMEOUT_MS = 120_000  # hard auto-cancel so the panel can never persist


class CapturePanel(QWidget):
    """Small always-on-top panel that captures a screen coordinate safely."""

    captured = Signal(int, int)
    cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        # No parent: an independent top-level window with its own title bar.
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Capture Position")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._finished = False
        self._count = 0

        self._build_ui()

        # Live cursor readout.
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._update_coord)
        self._poll.start(80)

        # Countdown ticks.
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)

        # Hard safety net: auto-cancel if left open.
        self._safety = QTimer(self)
        self._safety.setSingleShot(True)
        self._safety.timeout.connect(self._finish_cancel)
        self._safety.start(_SAFETY_TIMEOUT_MS)

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info = QLabel(
            "Move the mouse over the target, click “Capture”,\n"
            "then hold still during the countdown."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._coord = QLabel("Cursor: 0, 0")
        self._coord.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(self._coord)

        self._status = QLabel("")
        layout.addWidget(self._status)

        buttons = QHBoxLayout()
        self._capture_btn = QPushButton(f"Capture ({_COUNTDOWN_SECONDS}s)")
        self._capture_btn.setObjectName("primaryButton")
        self._capture_btn.clicked.connect(self._start_countdown)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._finish_cancel)
        buttons.addWidget(self._capture_btn)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)

        self.resize(340, 190)

    # -- capture flow -------------------------------------------------------

    def _update_coord(self) -> None:
        pos = QCursor.pos()
        self._coord.setText(f"Cursor: {pos.x()}, {pos.y()}")

    def _start_countdown(self) -> None:
        self._count = _COUNTDOWN_SECONDS
        self._capture_btn.setEnabled(False)
        self._status.setText(f"Capturing in {self._count}…")
        self._countdown.start()

    def _tick(self) -> None:
        self._count -= 1
        if self._count <= 0:
            self._countdown.stop()
            self._finish_capture()
        else:
            self._status.setText(f"Capturing in {self._count}…")

    def _finish_capture(self) -> None:
        if self._finished:
            return
        self._finished = True
        pos = QCursor.pos()
        self._stop_timers()
        self.captured.emit(pos.x(), pos.y())
        self.close()

    def _finish_cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._stop_timers()
        self.cancelled.emit()
        self.close()

    def _stop_timers(self) -> None:
        for timer in (self._poll, self._countdown, self._safety):
            timer.stop()

    # -- always-dismissable escape hatches ----------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.key() == Qt.Key.Key_Escape:
            self._finish_cancel()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        # Closing via the window's X button counts as a cancel.
        if not self._finished:
            self._finished = True
            self._stop_timers()
            self.cancelled.emit()
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
