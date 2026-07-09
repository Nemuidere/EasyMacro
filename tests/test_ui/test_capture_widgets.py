"""
Tests for the capture widgets:
  * KeyCaptureButton — resolves a Qt key event into an engine/AHK key name.
  * CaptureOverlay   — emits captured/cancelled exactly once.
"""

import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from src.ui.pages.builder_page import KeyCaptureButton
from src.ui.widgets.capture_overlay import CaptureOverlay


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


def test_overlay_capture_emits_once(qapp):
    overlay = CaptureOverlay()
    got = []
    overlay.captured.connect(lambda x, y: got.append((x, y)))
    overlay._finish_capture()
    overlay._finish_capture()  # idempotent
    assert len(got) == 1


def test_overlay_cancel_emits(qapp):
    overlay = CaptureOverlay()
    cancelled = []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay._finish_cancel()
    assert cancelled == [True]
