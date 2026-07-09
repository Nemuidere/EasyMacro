"""
Tests for PositionCaptureService.

Covers the start/stop return contract plus the three ways a capture resolves
(capture-key press, Esc cancel, timeout). The handler-level tests drive the
service's internal slots directly with a mocked AHK service and a real Qt event
loop, proving the service logic is sound independent of the GUI wiring.
"""

from unittest.mock import MagicMock

import pytest
from pynput.keyboard import Key
from PySide6.QtTest import QTest

from src.services.position_capture_service import PositionCaptureService, CaptureState


@pytest.fixture
def service(qapp, initialized_event_bus):
    svc = PositionCaptureService()
    yield svc
    svc.stop_capture()


def _capturing(service, ahk_pos=(7, 9)):
    """Put the service into the CAPTURING state with a mocked AHK service.

    Uses a long listener delay so no real pynput listener starts during the
    test; we invoke the handlers directly instead.
    """
    service.start_capture_delayed(timeout_ms=60000, delay_ms=60000)
    mock_ahk = MagicMock()
    mock_ahk.get_mouse_position.return_value = ahk_pos
    service._ahk_service = mock_ahk
    return mock_ahk


def test_start_capture_delayed_returns_true_then_false(service):
    # First call schedules a capture and reports success.
    started = service.start_capture_delayed(timeout_ms=30000, delay_ms=10000)
    assert started is True
    assert service.is_capturing() is True

    # Second call while already capturing is rejected without disturbing state.
    again = service.start_capture_delayed(timeout_ms=30000, delay_ms=10000)
    assert again is False
    assert service.is_capturing() is True


def test_stop_capture_returns_to_idle(service):
    service.start_capture_delayed(timeout_ms=30000, delay_ms=10000)
    service.stop_capture()
    assert service.is_capturing() is False


def test_capture_key_press_emits_position_and_captures(service):
    captured = []
    service._event_bus.position_captured.connect(lambda x, y: captured.append((x, y)))
    _capturing(service, ahk_pos=(42, 99))

    # Simulate the capture key (F2) arriving on the listener thread.
    service._on_key_press(Key.f2)
    QTest.qWait(50)

    assert captured == [(42, 99)]
    assert service.get_state() == CaptureState.CAPTURED.value
    assert service.is_capturing() is False


def test_escape_press_cancels(service):
    cancelled = []
    service._event_bus.position_capture_cancelled.connect(lambda: cancelled.append(True))
    _capturing(service)

    service._on_key_press(Key.esc)
    QTest.qWait(50)

    assert cancelled == [True]
    assert service.get_state() == CaptureState.CANCELLED.value
    assert service.is_capturing() is False


def test_timeout_cancels(service):
    cancelled = []
    service._event_bus.position_capture_cancelled.connect(lambda: cancelled.append(True))
    _capturing(service)

    # Fire the timeout slot directly (equivalent to the QTimer expiring).
    service._on_timeout_triggered()
    QTest.qWait(50)

    assert cancelled == [True]
    assert service.get_state() == CaptureState.CANCELLED.value
    assert service.is_capturing() is False
