"""
Tests for MouseMovementService helpers that don't require a real listener.

Focus: update_reference_position, which the macro engine uses to keep the
macro's own cursor moves from tripping the "stop on mouse movement" safety.
"""

import pytest

from src.services.mouse_movement_service import MouseMovementService


@pytest.fixture
def service(qapp):
    return MouseMovementService()


def test_update_reference_position_resets_distance(service):
    # Simulate an active monitoring session.
    service._set_monitoring_state(True)
    with service._position_lock:
        service._initial_position = (0, 0)
        service._current_position = (100, 100)

    assert service.get_distance_moved() > 0

    # Rebasing to the current point makes the measured distance zero again.
    service.update_reference_position(100, 100)
    assert service.get_distance_moved() == 0.0
    assert service.get_initial_position() == (100, 100)


def test_update_reference_position_noop_without_baseline(service):
    # No baseline captured yet (never started monitoring).
    assert service.get_initial_position() is None

    service.update_reference_position(50, 50)

    # Still no baseline; the call was a no-op.
    assert service.get_initial_position() is None
