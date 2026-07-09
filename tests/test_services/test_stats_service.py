"""
Tests for StatsService: accumulation, the stats_updated signal, persistence
round-trip and corrupt-file tolerance.
"""

import pytest

from src.services.stats_service import StatsService


@pytest.fixture
def stats_path(tmp_path):
    return tmp_path / "stats.json"


@pytest.fixture
def service(qapp, initialized_event_bus, stats_path):
    return StatsService(stats_path)


def test_update_clicks_accumulates(service):
    service.update_clicks("m1", 3)
    service.update_clicks("m1", 2)

    assert service.get_macro_stats("m1").total_clicks == 5
    assert service.get_global_stats().total_clicks == 5


def test_update_clicks_tracks_multiple_macros(service):
    service.update_clicks("m1", 1)
    service.update_clicks("m2", 4)

    g = service.get_global_stats()
    assert g.total_clicks == 5
    assert g.total_macros == 2
    assert g.last_used_macro_id == "m2"


def test_update_time_accumulates(service):
    service.update_time("m1", 1.5)
    service.update_time("m1", 2.5)
    assert service.get_macro_stats("m1").total_time_seconds == pytest.approx(4.0)


def test_stats_updated_signal_emitted(service):
    seen = []
    service._event_bus.stats_updated.connect(
        lambda mid, clicks, secs: seen.append((mid, clicks))
    )
    service.update_clicks("m1", 2)
    assert seen == [("m1", 2)]


def test_zero_count_is_noop(service):
    service.update_clicks("m1", 0)
    assert service.get_macro_stats("m1") is None


def test_negative_values_raise(service):
    with pytest.raises(ValueError):
        service.update_clicks("m1", -1)
    with pytest.raises(ValueError):
        service.update_time("m1", -1.0)
    with pytest.raises(ValueError):
        service.update_clicks("", 1)


def test_persistence_round_trip(qapp, initialized_event_bus, stats_path):
    first = StatsService(stats_path)
    first.update_clicks("m1", 7)
    first.update_time("m1", 12.0)

    # A fresh service on the same path loads the persisted numbers.
    second = StatsService(stats_path)
    assert second.get_global_stats().total_clicks == 7
    assert second.get_macro_stats("m1").total_time_seconds == pytest.approx(12.0)


def test_corrupt_stats_file_resets_to_defaults(qapp, initialized_event_bus, stats_path):
    stats_path.write_text("{ not valid json ")
    service = StatsService(stats_path)
    assert service.get_global_stats().total_clicks == 0


def test_reset_all_clears(service):
    service.update_clicks("m1", 5)
    service.reset_all_stats()
    assert service.get_global_stats().total_clicks == 0
    assert service.get_macro_stats("m1") is None
