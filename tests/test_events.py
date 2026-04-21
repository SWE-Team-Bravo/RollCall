from datetime import datetime, timezone

from services.events import has_event_ended


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
