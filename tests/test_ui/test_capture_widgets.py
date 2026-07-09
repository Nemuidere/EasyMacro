"""
Tests for the capture widgets:
  * KeyCaptureButton — resolves a Qt key event into an engine/AHK key name.
  * CaptureOverlay   — emits captured/cancelled exactly once.
"""

import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from src.ui.pages.builder_page import KeyCaptureButton
from src.ui.widgets.capture_overlay import CapturePanel


def _key_event(qt_key, text=""):
    return QKeyEvent(QEvent.Type.KeyPress, int(qt_key), Qt.KeyboardModifier.NoModifier, text)


@pytest.mark.parametrize(
    "qt_key,text,expected",
    [
        (Qt.Key.Key_A, "a", "a"),
        (Qt.Key.Key_5, "5", "5"),
        (Qt.Key.Key_F5, "", "f5"),
        (Qt.Key.Key_Return, "", "enter"),
        (Qt.Key.Key_Space, " ", "space"),
        (Qt.Key.Key_Escape, "", "escape"),
        (Qt.Key.Key_Shift, "", "shift"),
        (Qt.Key.Key_Up, "", "up"),
    ],
)
def test_key_resolution(qapp, qt_key, text, expected):
    assert KeyCaptureButton._resolve(_key_event(qt_key, text)) == expected


def test_key_capture_button_captures_on_press(qapp):
    btn = KeyCaptureButton()
    btn._on_clicked()  # enter capture mode
    btn.keyPressEvent(_key_event(Qt.Key.Key_F5))
    assert btn.key() == "f5"
    assert not btn._capturing


def test_key_capture_button_ignores_when_not_capturing(qapp):
    btn = KeyCaptureButton()
    btn.set_key("a")
    btn.keyPressEvent(_key_event(Qt.Key.Key_B, "b"))
    assert btn.key() == "a"  # unchanged; not in capture mode


def test_set_and_get_key(qapp):
    btn = KeyCaptureButton()
    btn.set_key("enter")
    assert btn.key() == "enter"


def test_panel_capture_emits_once(qapp):
    panel = CapturePanel()
    got = []
    panel.captured.connect(lambda x, y: got.append((x, y)))
    panel._finish_capture()
    panel._finish_capture()  # idempotent
    assert len(got) == 1


def test_panel_cancel_emits(qapp):
    panel = CapturePanel()
    cancelled = []
    panel.cancelled.connect(lambda: cancelled.append(True))
    panel._finish_cancel()
    assert cancelled == [True]


def test_panel_countdown_captures(qapp):
    panel = CapturePanel()
    got = []
    panel.captured.connect(lambda x, y: got.append((x, y)))
    panel._start_countdown()
    # Drive the countdown ticks to zero without waiting real seconds.
    for _ in range(5):
        panel._tick()
    assert len(got) == 1


def test_panel_close_counts_as_cancel(qapp):
    panel = CapturePanel()
    cancelled = []
    panel.cancelled.connect(lambda: cancelled.append(True))
    panel.close()
    assert cancelled == [True]
