"""
Tests for PositionCaptureService.start_capture_delayed return value.

Regression: the method used to return None, so the editor's
`if not start_capture_delayed(...)` always treated it as failure and the
Capture button never worked.
"""

import pytest

from src.services.position_capture_service import PositionCaptureService


@pytest.fixture
def service(qapp, initialized_event_bus):
    svc = PositionCaptureService()
    yield svc
    svc.stop_capture()


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
