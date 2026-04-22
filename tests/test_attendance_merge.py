from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

import services.cadet_attendance as cadet_attendance_svc
import services.commander_attendance as commander_attendance_svc
from services.attendance_merge import merge_attendance_records


def test_cadet_attendance_merges_duplicate_records_for_same_event() -> None:
    """When multiple submissions exist for the same (event, cadet),
    the UI-facing rows should merge to a single row.

    Expected merge rule (for now): prefer the record with the latest created_at.
    """

    event_id = ObjectId()
    cadet_id = ObjectId()

    cadet_record = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
        "recorded_by_user_id": ObjectId(),
        "recorded_by_roles": ["cadet"],
    }
    commander_record = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        "recorded_by_user_id": ObjectId(),
        "recorded_by_roles": ["flight_commander"],
    }

    events = [
        {
            "_id": event_id,
            "event_name": "Week 3 PT",
            "event_type": "pt",
            "start_date": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
            "end_date": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
        }
    ]

    # Order is intentionally adversarial: cadet record first.
    # Commander should still win even if older.
    rows = cadet_attendance_svc.cadet_attendance(
        records=[cadet_record, commander_record],
        events=events,
        waivers=[],
    )

    assert len(rows) == 1
    assert rows[0]["event_name"] == "Week 3 PT"
    assert rows[0]["status"] == "absent"


def test_build_commander_roster_prefers_latest_record_when_duplicates() -> None:
    """If duplicates exist in attendance_records (e.g., multiple flight commander submissions),
    commander roster should resolve them deterministically.

    Expected merge rule (for now): prefer the record with the latest created_at.
    """

    cadet_id = ObjectId()
    flight_cadets = [
        {
            "_id": cadet_id,
            "first_name": "Alex",
            "last_name": "Cadet",
        }
    ]

    older = {
        "_id": ObjectId(),
        "event_id": ObjectId(),
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        "recorded_by_user_id": ObjectId(),
        "recorded_by_roles": ["flight_commander"],
    }
    newer = {
        "_id": ObjectId(),
        "event_id": older["event_id"],
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
        "recorded_by_user_id": ObjectId(),
        "recorded_by_roles": ["flight_commander"],
    }

    # Adversarial order: older record comes last.
    roster = commander_attendance_svc.build_commander_roster(
        flight_cadets=flight_cadets,
        records=[newer, older],
    )

    assert len(roster) == 1
    assert roster[0]["cadet"]["_id"] == cadet_id
    assert roster[0]["current_status"] == "absent"


def test_merge_prefers_high_priority_roles_over_cadet_even_if_older() -> None:
    event_id = ObjectId()
    cadet_id = ObjectId()

    cadet_record = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["cadet"],
    }
    commander_record = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["flight_commander"],
    }

    merged = merge_attendance_records([cadet_record, commander_record])
    assert len(merged) == 1
    assert merged[0]["status"] == "absent"


def test_merge_tie_breaks_by_time_when_both_high_priority() -> None:
    event_id = ObjectId()
    cadet_id = ObjectId()

    older_cadre = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["cadre"],
    }
    newer_commander = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["flight_commander"],
    }

    merged = merge_attendance_records([older_cadre, newer_commander])
    assert len(merged) == 1
    assert merged[0]["status"] == "absent"


def test_merge_falls_back_to_newest_time_when_roles_missing() -> None:
    event_id = ObjectId()
    cadet_id = ObjectId()

    older = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
    }
    newer = {
        "_id": ObjectId(),
        "event_id": event_id,
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
    }

    merged = merge_attendance_records([older, newer])
    assert len(merged) == 1
    assert merged[0]["status"] == "absent"


def test_merge_does_not_merge_across_events() -> None:
    cadet_id = ObjectId()
    event_a = ObjectId()
    event_b = ObjectId()

    rec_a = {
        "_id": ObjectId(),
        "event_id": event_a,
        "cadet_id": cadet_id,
        "status": "present",
        "created_at": datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["cadet"],
    }
    rec_b = {
        "_id": ObjectId(),
        "event_id": event_b,
        "cadet_id": cadet_id,
        "status": "absent",
        "created_at": datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc),
        "recorded_by_roles": ["cadet"],
    }

    merged = merge_attendance_records([rec_a, rec_b])
    assert len(merged) == 2
    assert {r["event_id"] for r in merged} == {event_a, event_b}
