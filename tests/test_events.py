from datetime import date, datetime, timezone

from services.events import (
    build_event_bounds,
    create_event,
    get_event_time_bounds,
    has_event_ended,
)


def test_build_event_bounds_respects_selected_timezone() -> None:
    start_at, end_at = build_event_bounds(
        datetime(2026, 4, 23, tzinfo=timezone.utc).date(),
        datetime(2026, 4, 23, tzinfo=timezone.utc).date(),
        "America/New_York",
    )

    assert start_at == datetime(2026, 4, 23, 4, 0, tzinfo=timezone.utc)
    assert end_at == datetime(2026, 4, 24, 3, 59, 59, tzinfo=timezone.utc)


def test_get_event_time_bounds_reinterprets_legacy_all_day_event_with_fallback() -> (
    None
):
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


def test_create_event_rejects_start_date_after_end_date() -> None:
    result = create_event(
        name="Bad Event",
        event_type="PT",
        start_date=date(2026, 4, 25),
        end_date=date(2026, 4, 24),
        created_by_user_id="000000000000000000000001",
    )
    assert result is False


def test_create_event_date_check_happens_before_db_access() -> None:
    assert (
        create_event(
            name="Reversed",
            event_type="PT",
            start_date=date(2026, 4, 26),
            end_date=date(2026, 4, 25),
            created_by_user_id="000000000000000000000001",
        )
        is False
    )
    assert (
        create_event(
            name="Reversed by many days",
            event_type="PT",
            start_date=date(2026, 12, 31),
            end_date=date(2026, 1, 1),
            created_by_user_id="000000000000000000000001",
        )
        is False
    )
