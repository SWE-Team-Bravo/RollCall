from unittest.mock import patch

import pytest  # type: ignore

from services.attendance import (
    is_already_checked_in,
    is_within_checkin_window,
    is_within_geofence,
    _haversine_meters,
)
from services.event_config import get_checkin_window_minutes
from datetime import datetime, timedelta, timezone


def create_event(start_offset_minutes: int) -> dict:
    now = datetime.now(timezone.utc)
    return {"start_date": now + timedelta(minutes=start_offset_minutes)}


# ------------------ test is_already_checked_in -------------------------


def test_returns_true_when_cadet_has_record_for_event():
    records = [{"event_id": "event1", "cadet_id": "cadet1", "status": "present"}]
    assert is_already_checked_in("event1", "cadet1", records) is True


def test_returns_false_when_no_records_exist():
    assert is_already_checked_in("event1", "cadet1", []) is False


def test_returns_false_when_record_is_for_different_event():
    records = [{"event_id": "event2", "cadet_id": "cadet1", "status": "present"}]
    assert is_already_checked_in("event1", "cadet1", records) is False


def test_returns_false_when_record_is_for_different_cadet():
    records = [{"event_id": "event1", "cadet_id": "cadet2", "status": "present"}]
    assert is_already_checked_in("event1", "cadet1", records) is False


def test_returns_true_regardless_of_status():
    for status in ("present", "excused", "absent"):
        records = [{"event_id": "event1", "cadet_id": "cadet1", "status": status}]
        assert is_already_checked_in("event1", "cadet1", records) is True


def test_returns_true_when_among_multiple_records():
    records = [
        {"event_id": "event1", "cadet_id": "cadet2", "status": "present"},
        {"event_id": "event1", "cadet_id": "cadet1", "status": "present"},
        {"event_id": "event2", "cadet_id": "cadet1", "status": "absent"},
    ]
    assert is_already_checked_in("event1", "cadet1", records) is True


def test_returns_false_when_same_cadet_checked_into_different_event_only():
    records = [
        {"event_id": "event2", "cadet_id": "cadet1", "status": "present"},
        {"event_id": "event3", "cadet_id": "cadet1", "status": "present"},
    ]
    assert is_already_checked_in("event1", "cadet1", records) is False


# ------------------ test is_within_checkin_window -------------------------


@pytest.fixture(autouse=True)
def mock_checkin_window():
    with patch("services.attendance.CHECKIN_WINDOW_MINUTES", 10):
        yield


def test_returns_true_within_window():
    event = create_event(5)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is True


def test_returns_true_at_window_open():
    event = create_event(10)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is True


def test_returns_true_at_event_start():
    now = datetime.now(timezone.utc)
    event = create_event(0)
    assert is_within_checkin_window(event, now) is True


def test_returns_false_before_window():
    # 25 minutes before start is outside the default 20-minute pre-start window
    event = create_event(25)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is False


def test_returns_true_shortly_after_event_starts():
    # event started 5 minutes ago — still within the 10-minute post-start window
    event = create_event(-5)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is True


def test_returns_false_well_after_event_starts():
    # event started 30 minutes ago — outside the 10-minute post-start window
    event = create_event(-30)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is False


def test_returns_false_missing_start_date():
    assert is_within_checkin_window({}, datetime.now(timezone.utc)) is False


def test_returns_false_if_start_date_is_not_datetime():
    event = {"start_date": "2026-01-01"}
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is False


def test_no_timezone_info():
    event = {"start_date": datetime.now(timezone.utc) + timedelta(minutes=5)}
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is True


def test_custom_window_allows_cadet_inside_larger_window():
    now = datetime.now(timezone.utc)
    event = {"start_date": now + timedelta(minutes=12)}
    assert is_within_checkin_window(event, now, window_minutes=15) is True


def test_custom_window_rejects_cadet_outside_smaller_window():
    now = datetime.now(timezone.utc)
    event = {"start_date": now + timedelta(minutes=12)}
    assert is_within_checkin_window(event, now, window_minutes=10) is False


def test_get_checkin_window_minutes_returns_default_with_no_db():
    with patch("services.event_config.get_db", return_value=None):
        assert get_checkin_window_minutes() == 20


# ------------------ test _haversine_meters --------------------------------


def test_haversine_same_point_is_zero():
    assert _haversine_meters(39.0, -76.0, 39.0, -76.0) == 0.0


def test_haversine_known_distance():
    # ~111km per degree of latitude
    dist = _haversine_meters(39.0, -76.0, 40.0, -76.0)
    assert 110_000 < dist < 112_000


def test_haversine_is_symmetric():
    a = _haversine_meters(39.0, -76.0, 39.001, -76.0)
    b = _haversine_meters(39.001, -76.0, 39.0, -76.0)
    assert abs(a - b) < 0.01


# ------------------ test is_within_geofence --------------------------------


def _geo_event(lat, lon, radius, enabled=True):
    return {
        "geofence_enabled": enabled,
        "geofence_lat": lat,
        "geofence_lon": lon,
        "geofence_radius_meters": radius,
    }


def test_geofence_disabled_always_passes():
    event = _geo_event(39.0, -76.0, 10, enabled=False)
    within, msg = is_within_geofence(event, 90.0, 180.0)
    assert within is True
    assert msg == ""


def test_geofence_cadet_inside_fence():
    event = _geo_event(39.0, -76.0, 200)
    within, msg = is_within_geofence(event, 39.001, -76.0)  # ~111m away
    assert within is True
    assert msg == ""


def test_geofence_cadet_outside_fence():
    event = _geo_event(39.0, -76.0, 100)
    within, msg = is_within_geofence(event, 39.001, -76.0)  # ~111m away
    assert within is False
    assert "111m" in msg
    assert "100m" in msg


def test_geofence_cadet_exactly_on_boundary():
    # Place cadet exactly at the center — always inside
    event = _geo_event(39.0, -76.0, 1)
    within, _ = is_within_geofence(event, 39.0, -76.0)
    assert within is True


def test_geofence_missing_lat_passes():
    event = {
        "geofence_enabled": True,
        "geofence_lon": -76.0,
        "geofence_radius_meters": 100,
    }
    within, msg = is_within_geofence(event, 39.0, -76.0)
    assert within is True
    assert msg == ""


def test_geofence_missing_lon_passes():
    event = {
        "geofence_enabled": True,
        "geofence_lat": 39.0,
        "geofence_radius_meters": 100,
    }
    within, msg = is_within_geofence(event, 39.0, -76.0)
    assert within is True
    assert msg == ""


def test_geofence_missing_radius_uses_default_150m():
    event = {"geofence_enabled": True, "geofence_lat": 39.0, "geofence_lon": -76.0}
    # ~111m away — inside default 150m radius
    within, _ = is_within_geofence(event, 39.001, -76.0)
    assert within is True


def test_geofence_missing_radius_outside_default():
    event = {"geofence_enabled": True, "geofence_lat": 39.0, "geofence_lon": -76.0}
    # ~222m away — outside default 150m radius
    within, msg = is_within_geofence(event, 39.002, -76.0)
    assert within is False
    assert "150m" in msg


def test_geofence_warning_message_includes_distances():
    event = _geo_event(39.0, -76.0, 50)
    within, msg = is_within_geofence(event, 39.001, -76.0)
    assert within is False
    assert "m" in msg


def test_geofence_empty_event_passes():
    within, msg = is_within_geofence({}, 39.0, -76.0)
    assert within is True
    assert msg == ""
