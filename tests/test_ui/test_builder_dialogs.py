"""
Tests for the screen-condition dialogs (wait / if / while) and the shared
ImageConditionWidget. Dialogs are driven headless: the condition widget's
condition() is stubbed with a canned ImageCondition, and QMessageBox.warning
is stubbed wherever a validation branch can fire (a real modal would hang the
offscreen suite).
"""

import pytest

import src.ui.pages.builder_dialogs as dialogs_module
from src.models.action import IfBlock, ImageCondition, WaitAction, WhileBlock
from src.ui.pages.builder_dialogs import (
    IfBlockDialog,
    WaitForImageDialog,
    WhileBlockDialog,
)
from src.ui.widgets.image_condition_widget import ImageConditionWidget


def _cond(**overrides) -> ImageCondition:
    fields = {
        "image_file": "ref_test.png",
        "x1": 100,
        "y1": 200,
        "x2": 300,
        "y2": 260,
        "color_variation": 15,
        "negate": True,
    }
    fields.update(overrides)
    return ImageCondition(**fields)


@pytest.fixture
def stub_condition(monkeypatch):
    """Make every ImageConditionWidget return a canned condition."""
    canned = _cond()
    monkeypatch.setattr(ImageConditionWidget, "condition", lambda self: canned)
    return canned


class TestWaitForImageDialog:
    def test_result_contents(self, qapp, stub_condition):
        dialog = WaitForImageDialog()
        dialog._poll_spin.setValue(150)
        dialog._timeout_spin.setValue(5000)
        dialog._on_timeout_combo.setCurrentIndex(1)  # continue

        dialog._on_accept()

        action = dialog.result_action()
        assert isinstance(action, WaitAction)
        assert action.condition is stub_condition
        assert action.poll_interval_ms == 150
        assert action.timeout_ms == 5000
        assert action.on_timeout == "continue"
        assert dialog.result_actions() == [action]

    def test_load_existing_round_trips(self, qapp, stub_condition):
        existing = WaitAction(
            condition=_cond(),
            poll_interval_ms=333,
            timeout_ms=9000,
            on_timeout="continue",
        )

        dialog = WaitForImageDialog(existing=existing)

        assert dialog._poll_spin.value() == 333
        assert dialog._timeout_spin.value() == 9000
        assert dialog._on_timeout_combo.currentData() == "continue"

    def test_accept_without_capture_warns_and_stays_open(self, qapp, monkeypatch):
        warnings = []
        monkeypatch.setattr(
            dialogs_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
        )
        dialog = WaitForImageDialog()  # condition widget NOT stubbed: no capture

        dialog._on_accept()

        assert warnings
        assert dialog.result_action() is None
        assert dialog.result_actions() == []


class TestIfBlockDialog:
    def test_result_is_empty_bodied_if_block(self, qapp, stub_condition):
        dialog = IfBlockDialog()

        dialog._on_accept()

        block = dialog.result_action()
        assert isinstance(block, IfBlock)
        assert block.condition is stub_condition
        assert block.then_actions == []
        assert block.else_actions == []

    def test_result_condition_for_in_place_edits(self, qapp, stub_condition):
        dialog = IfBlockDialog()

        dialog._on_accept()

        assert dialog.result_condition() is stub_condition

    def test_load_existing_populates_condition_widget(self, qapp, monkeypatch, tmp_path):
        import src.services.image_asset_service as asset_module
        monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path)
        existing = IfBlock(condition=_cond(color_variation=42))

        dialog = IfBlockDialog(existing=existing)

        widget = dialog._condition_widget
        assert widget._image_file == "ref_test.png"
        assert widget._tolerance_spin.value() == 42
        assert widget._match_combo.currentData() is True  # negate


class TestWhileBlockDialog:
    def test_result_contents(self, qapp, stub_condition):
        dialog = WhileBlockDialog()
        dialog._timeout_spin.setValue(30)
        dialog._max_iter_spin.setValue(7)
        dialog._interval_spin.setValue(250)

        dialog._on_accept()

        block = dialog.result_action()
        assert isinstance(block, WhileBlock)
        assert block.condition is stub_condition
        assert block.timeout_seconds == 30
        assert block.max_iterations == 7
        assert block.check_interval_ms == 250
        assert block.actions == []

    def test_load_existing_round_trips(self, qapp, stub_condition):
        existing = WhileBlock(
            condition=_cond(),
            timeout_seconds=60,
            max_iterations=3,
            check_interval_ms=500,
        )

        dialog = WhileBlockDialog(existing=existing)

        assert dialog._timeout_spin.value() == 60
        assert dialog._max_iter_spin.value() == 3
        assert dialog._interval_spin.value() == 500


class TestImageConditionWidget:
    def test_condition_before_capture_raises(self, qapp):
        widget = ImageConditionWidget()

        with pytest.raises(ValueError, match="[Cc]apture"):
            widget.condition()

    def test_load_then_condition_round_trips(self, qapp, monkeypatch, tmp_path):
        import src.services.image_asset_service as asset_module
        monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path)
        original = _cond()
        widget = ImageConditionWidget()

        widget.load(original)
        rebuilt = widget.condition()

        assert rebuilt == original

    def test_region_captured_updates_state(self, qapp, monkeypatch, tmp_path):
        import src.services.image_asset_service as asset_module
        monkeypatch.setattr(asset_module, "get_assets_dir", lambda: tmp_path)
        widget = ImageConditionWidget()

        widget._on_region_captured(10, 20, 30, 40, "ref_new.png")

        cond = widget.condition()
        assert (cond.x1, cond.y1, cond.x2, cond.y2) == (10, 20, 30, 40)
        assert cond.image_file == "ref_new.png"
