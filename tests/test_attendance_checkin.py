from services.attendance import is_already_checked_in, is_within_checkin_window
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
    event = create_event(20)
    assert is_within_checkin_window(event, datetime.now(timezone.utc)) is False


def test_returns_false_after_event_starts():
    event = create_event(-5)
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


def test_get_checkin_window_minutes_returns_10_with_no_db():
    assert get_checkin_window_minutes() == 10
