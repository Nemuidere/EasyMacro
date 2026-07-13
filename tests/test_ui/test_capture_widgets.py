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


class TestRegionCaptureFlow:
    """Region capture chains two point captures, grabs, and saves the asset."""

    @pytest.fixture
    def flow_env(self, qapp, monkeypatch, tmp_path):
        """A RegionCaptureFlow whose CapturePanels auto-emit on show().

        Returns (parent_widget, make_flow, emitted_corners) where
        emitted_corners is a mutable list the stub panels consume from.
        """
        import src.ui.widgets.region_capture as rc_module
        import src.services.image_asset_service as asset_module
        from PySide6.QtCore import Signal, QObject
        from PySide6.QtWidgets import QWidget

        monkeypatch.setattr(
            "src.core.constants.get_data_dir", lambda: tmp_path, raising=True
        )
        # image_asset_service imported get_assets_dir directly; patch there too.
        monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path / "assets")
        # No settle delay in tests.
        monkeypatch.setattr(rc_module, "_GRAB_SETTLE_MS", 0)
        monkeypatch.setattr(
            rc_module.QTimer, "singleShot", staticmethod(lambda ms, fn: fn())
        )

        corners = []

        class StubPanel(QWidget):
            captured = Signal(int, int)
            cancelled = Signal()

            def __init__(self, parent=None, instruction=None, title=None):
                super().__init__(parent)
                self._instruction = instruction

            def show(self):
                if corners:
                    x, y = corners.pop(0)
                    self.captured.emit(x, y)
                else:
                    self.cancelled.emit()

        monkeypatch.setattr(rc_module, "CapturePanel", StubPanel)

        parent = QWidget()
        parent.show()

        def make_flow():
            return rc_module.RegionCaptureFlow(parent)

        return parent, make_flow, corners

    def test_two_corners_captured_normalized_and_saved(self, flow_env, tmp_path):
        parent, make_flow, corners = flow_env
        # Fed in "wrong" order: bottom-right first.
        corners.extend([(300, 260), (100, 200)])
        results = []

        flow = make_flow()
        flow.captured.connect(lambda *args: results.append(args))
        flow.start()

        assert len(results) == 1
        x1, y1, x2, y2, filename = results[0]
        assert (x1, y1, x2, y2) == (100, 200, 300, 260)
        assert filename.startswith("ref_") and filename.endswith(".png")
        assert (tmp_path / "assets" / filename).exists()
        assert parent.isVisible()  # window restored

    def test_cancel_at_first_corner_restores_window(self, flow_env):
        parent, make_flow, corners = flow_env
        # corners empty -> stub cancels immediately
        cancels = []

        flow = make_flow()
        flow.cancelled.connect(lambda: cancels.append(True))
        flow.start()

        assert cancels == [True]
        assert parent.isVisible()

    def test_cancel_at_second_corner_restores_window(self, flow_env):
        parent, make_flow, corners = flow_env
        corners.append((100, 200))  # first corner ok, second cancels
        cancels = []

        flow = make_flow()
        flow.cancelled.connect(lambda: cancels.append(True))
        flow.start()

        assert cancels == [True]
        assert parent.isVisible()

    def test_zero_area_region_cancels_with_warning(self, flow_env, monkeypatch):
        import src.ui.widgets.region_capture as rc_module
        parent, make_flow, corners = flow_env
        corners.extend([(100, 200), (100, 260)])  # same x -> zero width
        warnings = []
        monkeypatch.setattr(
            rc_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
        )
        cancels = []

        flow = make_flow()
        flow.cancelled.connect(lambda: cancels.append(True))
        flow.start()

        assert warnings and cancels == [True]
        assert parent.isVisible()


def test_save_reference_pixmap_rejects_null(qapp, monkeypatch, tmp_path):
    import src.services.image_asset_service as asset_module
    from PySide6.QtGui import QPixmap

    monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path / "assets")

    with pytest.raises(ValueError):
        asset_module.save_reference_pixmap(QPixmap())


def test_save_reference_pixmap_creates_file(qapp, monkeypatch, tmp_path):
    import src.services.image_asset_service as asset_module
    from PySide6.QtGui import QPixmap

    monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path / "assets")
    pm = QPixmap(10, 10)
    pm.fill()

    filename = asset_module.save_reference_pixmap(pm)

    assert (tmp_path / "assets" / filename).exists()


def test_capture_panel_custom_instruction_and_title(qapp):
    panel = CapturePanel(instruction="Aim at the TOP-LEFT corner", title="Corner 1")
    try:
        assert panel.windowTitle() == "Corner 1"
        assert panel._instruction == "Aim at the TOP-LEFT corner"
    finally:
        panel._finish_cancel()
