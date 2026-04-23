from datetime import datetime, timezone

from services.events import build_event_bounds, get_event_time_bounds, has_event_ended


def test_build_event_bounds_respects_selected_timezone() -> None:
    start_at, end_at = build_event_bounds(
        datetime(2026, 4, 23, tzinfo=timezone.utc).date(),
        datetime(2026, 4, 23, tzinfo=timezone.utc).date(),
        "America/New_York",
    )

    assert start_at == datetime(2026, 4, 23, 4, 0, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 4, 24, 3, 59, 59, tzinfo=timezone.utc)


def test_get_event_time_bounds_reinterprets_legacy_all_day_event_with_fallback() -> None:
    event = {
        "start_date": datetime(2026, 4, 23, 0, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 4, 23, 23, 59, 59, tzinfo=timezone.utc),
    }

    start_at, end_at = get_event_time_bounds(
        event,
        fallback_tz_name="America/New_York",
    )

    assert start_at == datetime(2026, 4, 23, 4, 0, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 4, 24, 3, 59, 59, tzinfo=timezone.utc)


def test_get_event_time_bounds_keeps_explicit_timezone_events_unchanged() -> None:
    event = {
        "start_date": datetime(2026, 4, 23, 4, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 4, 24, 3, 59, 59, tzinfo=timezone.utc),
        "timezone_name": "America/New_York",
    }

    start_at, end_at = get_event_time_bounds(
        event,
        fallback_tz_name="UTC",
    )

    assert start_at == datetime(2026, 4, 23, 4, 0, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 4, 24, 3, 59, 59, tzinfo=timezone.utc)


def test_has_event_ended_uses_end_date_when_present() -> None:
    event = {
        "start_date": datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
    }

    assert has_event_ended(
        event,
        now=datetime(2026, 4, 21, 11, 1, tzinfo=timezone.utc),
    )


def test_has_event_ended_falls_back_to_start_date() -> None:
    event = {
        "start_date": datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
    }

    assert has_event_ended(
        event,
        now=datetime(2026, 4, 21, 10, 1, tzinfo=timezone.utc),
    )


def test_has_event_ended_is_false_before_end_time() -> None:
    event = {
        "start_date": datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc),
    }

    assert not has_event_ended(
        event,
        now=datetime(2026, 4, 21, 10, 59, tzinfo=timezone.utc),
    )
