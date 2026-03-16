from datetime import datetime, timedelta, timezone

from utils.flight_commander_view import (
    build_checkin_view,
    get_active_events,
)


def _dt(hours_offset: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours_offset)


def test_returns_active_event_and_splits_checked_in_vs_missing():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "event_name": "PT Session",
            "start_date": now - timedelta(minutes=30),
            "end_date": now + timedelta(minutes=30),
        }
    ]

    cadets = [
        {"_id": "cadet1", "first_name": "Tyler", "last_name": "Brooks"},
        {"_id": "cadet2", "first_name": "Emily", "last_name": "Chen"},
        {"_id": "cadet3", "first_name": "Marcus", "last_name": "Davis"},
    ]

    attendance_records = [
        {
            "event_id": "event1",
            "cadet_id": "cadet1",
            "status": "present",
        },
        {
            "event_id": "event1",
            "cadet_id": "cadet2",
            "status": "excused",
        },
    ]

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert result["event"]["_id"] == "event1"
    assert [c["_id"] for c in result["checked_in"]] == ["cadet1", "cadet2"]
    assert [c["_id"] for c in result["missing"]] == ["cadet3"]


def test_returns_none_when_no_active_event():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "event_name": "Old Event",
            "start_date": now - timedelta(days=2),
            "end_date": now - timedelta(days=1),
        }
    ]

    cadets = [{"_id": "cadet1", "first_name": "Tyler", "last_name": "Brooks"}]
    attendance_records = []

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is None


def test_only_present_and_excused_count_as_checked_in():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "event_name": "PT Session",
            "start_date": now - timedelta(minutes=15),
            "end_date": now + timedelta(minutes=15),
        }
    ]

    cadets = [
        {"_id": "cadet1", "first_name": "Tyler", "last_name": "Brooks"},
        {"_id": "cadet2", "first_name": "Emily", "last_name": "Chen"},
        {"_id": "cadet3", "first_name": "Marcus", "last_name": "Davis"},
    ]

    attendance_records = [
        {"event_id": "event1", "cadet_id": "cadet1", "status": "present"},
        {"event_id": "event1", "cadet_id": "cadet2", "status": "excused"},
        {"event_id": "event1", "cadet_id": "cadet3", "status": "absent"},
    ]

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert [c["_id"] for c in result["checked_in"]] == ["cadet1", "cadet2"]
    assert [c["_id"] for c in result["missing"]] == ["cadet3"]


def test_other_flight_cadets_are_not_included():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        }
    ]

    flight_cadets = [
        {"_id": "cadet1"},
        {"_id": "cadet2"},
    ]

    attendance_records = [
        {"event_id": "event1", "cadet_id": "cadet1", "status": "present"},
        {
            "event_id": "event1",
            "cadet_id": "cadet999",
            "status": "present",
        },  # other flight
    ]

    result = build_checkin_view(
        flight_cadets=flight_cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert [c["_id"] for c in result["checked_in"]] == ["cadet1"]


def test_absent_status_counts_as_missing():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        }
    ]

    cadets = [{"_id": "cadet1"}]

    attendance_records = [
        {"event_id": "event1", "cadet_id": "cadet1", "status": "absent"},
    ]

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert result["missing"][0]["_id"] == "cadet1"


def test_cadets_without_record_are_missing():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        }
    ]

    cadets = [
        {"_id": "cadet1"},
        {"_id": "cadet2"},
    ]

    attendance_records = []

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert len(result["missing"]) == 2


def test_event_not_active_returns_none():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now + timedelta(hours=1),
            "end_date": now + timedelta(hours=2),
        }
    ]

    result = build_checkin_view(
        flight_cadets=[],
        events=events,
        attendance_records=[],
        now=now,
    )

    assert result is None


def test_first_active_event_selected():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=30),
            "end_date": now + timedelta(minutes=30),
        },
        {
            "_id": "event2",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        },
    ]

    result = build_checkin_view(
        flight_cadets=[],
        events=events,
        attendance_records=[],
        now=now,
    )

    assert result is not None
    assert result["event"]["_id"] == "event1"


def test_attendance_from_other_events_ignored():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        }
    ]

    cadets = [{"_id": "cadet1"}]

    attendance_records = [
        {"event_id": "event999", "cadet_id": "cadet1", "status": "present"},
    ]

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert result["missing"][0]["_id"] == "cadet1"


def test_status_case_insensitive():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=10),
        }
    ]

    cadets = [{"_id": "cadet1"}]

    attendance_records = [
        {"event_id": "event1", "cadet_id": "cadet1", "status": "PRESENT"},
    ]

    result = build_checkin_view(
        flight_cadets=cadets,
        events=events,
        attendance_records=attendance_records,
        now=now,
    )

    assert result is not None
    assert result["checked_in"][0]["_id"] == "cadet1"


def test_get_active_events_returns_only_active_events():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "event_name": "Active PT",
            "start_date": now - timedelta(minutes=20),
            "end_date": now + timedelta(minutes=20),
        },
        {
            "_id": "event2",
            "event_name": "Active LAB",
            "start_date": now - timedelta(minutes=10),
            "end_date": now + timedelta(minutes=30),
        },
        {
            "_id": "event3",
            "event_name": "Old Event",
            "start_date": now - timedelta(days=2),
            "end_date": now - timedelta(days=1),
        },
        {
            "_id": "event4",
            "event_name": "Future Event",
            "start_date": now + timedelta(hours=1),
            "end_date": now + timedelta(hours=2),
        },
    ]

    active = get_active_events(events, now)

    assert [event["_id"] for event in active] == ["event1", "event2"]


def test_get_active_events_handles_naive_datetimes():
    now = datetime.now(timezone.utc)

    events = [
        {
            "_id": "event1",
            "event_name": "Naive Active Event",
            "start_date": (now - timedelta(minutes=10)).replace(tzinfo=None),
            "end_date": (now + timedelta(minutes=10)).replace(tzinfo=None),
        }
    ]

    active = get_active_events(events, now)

    assert [event["_id"] for event in active] == ["event1"]


def test_selected_event_changes_output():
    flight_cadets = [
        {"_id": "cadet1", "first_name": "Tyler", "last_name": "Brooks"},
        {"_id": "cadet2", "first_name": "Emily", "last_name": "Chen"},
    ]

    event1 = {"_id": "event1", "event_name": "PT Session"}
    event2 = {"_id": "event2", "event_name": "LAB Session"}

    attendance_records = [
        {"event_id": "event1", "cadet_id": "cadet1", "status": "present"},
        {"event_id": "event2", "cadet_id": "cadet2", "status": "present"},
    ]

    result1 = build_checkin_view(
        flight_cadets=flight_cadets,
        event=event1,
        attendance_records=attendance_records,
    )
    result2 = build_checkin_view(
        flight_cadets=flight_cadets,
        event=event2,
        attendance_records=attendance_records,
    )

    assert result1 is not None
    assert result2 is not None
    assert [c["_id"] for c in result1["checked_in"]] == ["cadet1"]
    assert [c["_id"] for c in result1["missing"]] == ["cadet2"]

    assert [c["_id"] for c in result2["checked_in"]] == ["cadet2"]
    assert [c["_id"] for c in result2["missing"]] == ["cadet1"]
