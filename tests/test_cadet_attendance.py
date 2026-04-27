from datetime import datetime, timedelta, timezone

from services.cadet_attendance import (
    cadet_attendance,
    count_absences,
    filter_rows,
    get_cadet_flight_label,
)


def _dt(days_offset: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_offset)


# ---------------- test cadet_attendance ------------------


def test_cadet_attendance():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "present"}]
    events = [
        {
            "_id": "evt1",
            "event_name": "PT Session",
            "event_type": "pt",
            "start_date": _dt(1),
        }
    ]
    waivers = []

    rows = cadet_attendance(records, events, waivers)

    assert len(rows) == 1
    assert rows[0]["event_name"] == "PT Session"
    assert rows[0]["event_type"] == "PT"
    assert rows[0]["status"] == "present"
    assert rows[0]["waiver_status"] is None
    assert rows[0]["waiver_eligible"] is True


def test_cadet_attendance_no_matching_events():
    records = [{"_id": "rec1", "event_id": "evt999", "status": "absent"}]
    events = []
    waivers = []

    rows = cadet_attendance(records, events, waivers)

    assert rows == []


def test_cadet_attendance_waivers():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "LLAB", "event_type": "lab", "start_date": _dt(1)}
    ]
    waivers = [{"_id": "w1", "attendance_record_id": "rec1", "status": "pending"}]

    rows = cadet_attendance(records, events, waivers)

    assert rows[0]["waiver_status"] == "pending"


def test_cadet_attendance_approved_waiver_is_waived():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(1)}
    ]
    waivers = [{"_id": "w1", "attendance_record_id": "rec1", "status": "approved"}]

    rows = cadet_attendance(records, events, waivers)

    assert rows[0]["status"] == "waived"


def test_cadet_attendance_sort_newest():
    records = [
        {"_id": "rec1", "event_id": "evt1", "status": "present"},
        {"_id": "rec2", "event_id": "evt2", "status": "absent"},
    ]
    events = [
        {
            "_id": "evt1",
            "event_name": "Old PT",
            "event_type": "pt",
            "start_date": _dt(10),
        },
        {
            "_id": "evt2",
            "event_name": "New LLAB",
            "event_type": "lab",
            "start_date": _dt(1),
        },
    ]
    waivers = []

    rows = cadet_attendance(records, events, waivers)

    assert rows[0]["event_name"] == "New LLAB"
    assert rows[1]["event_name"] == "Old PT"


def test_cadet_attendance_only_waiver_eligible():
    records = [
        {"_id": "rec1", "event_id": "evt1", "status": "absent"},
        {"_id": "rec2", "event_id": "evt2", "status": "absent"},
    ]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(2)},
        {
            "_id": "evt2",
            "event_name": "Other",
            "event_type": "other",
            "start_date": _dt(1),
        },
    ]
    waivers = []

    rows = cadet_attendance(records, events, waivers)
    by_name = {r["event_name"]: r for r in rows}

    assert by_name["PT"]["waiver_eligible"] is True
    assert by_name["Other"]["waiver_eligible"] is False


def test_cadet_attendance_normalized_status():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "PRESENT"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(1)}
    ]
    waivers = []

    rows = cadet_attendance(records, events, waivers)

    assert rows[0]["status"] == "present"


def test_cadet_attendance_missing_defaults():
    records = [{"_id": "rec1", "event_id": "evt1"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(1)}
    ]
    waivers = []

    rows = cadet_attendance(records, events, waivers)

    assert rows[0]["status"] == "—"


# ---------------- test count_absences ------------------


def test_count_absences_only_absent():
    rows = [
        {"event_type": "PT", "status": "absent"},
        {"event_type": "PT", "status": "present"},
        {"event_type": "PT", "status": "absent"},
        {"event_type": "LAB", "status": "absent"},
    ]
    assert count_absences(rows, "pt") == 2


def test_count_absences_case_insensitive():
    rows = [
        {"event_type": "pt", "status": "absent"},
        {"event_type": "PT", "status": "absent"},
    ]
    assert count_absences(rows, "pt") == 2


def test_count_absences_zero():
    rows = [{"event_type": "PT", "status": "present"}]
    assert count_absences(rows, "pt") == 0


def test_count_absences_ignores_other_types():
    rows = [
        {"event_type": "LAB", "status": "absent"},
        {"event_type": "PT", "status": "absent"},
    ]
    assert count_absences(rows, "lab") == 1


def test_count_absences_ignores_approved_waivers():
    rows = [{"event_type": "PT", "status": "absent", "waiver_status": "approved"}]

    assert count_absences(rows, "pt") == 0


# ------------------ test filter_rows --------------------


def test_filter_rows_all():
    rows = [
        {"event_type": "PT", "status": "present"},
        {"event_type": "LAB", "status": "absent"},
    ]
    assert filter_rows(rows, "All", "All") == rows


def test_filter_rows_by_status():
    rows = [
        {"event_type": "PT", "status": "present"},
        {"event_type": "PT", "status": "absent"},
    ]
    result = filter_rows(rows, "Absent", "All")
    assert len(result) == 1
    assert result[0]["status"] == "absent"


def test_filter_rows_excused_waived():
    rows = [
        {"event_type": "PT", "status": "excused"},
        {"event_type": "PT", "status": "waived"},
        {"event_type": "PT", "status": "absent"},
    ]
    result = filter_rows(rows, "Excused", "All")
    assert len(result) == 2
    assert all(r["status"] in ("excused", "waived") for r in result)


def test_filter_rows_excused_includes_approved_waiver_absence():
    rows = [
        {"event_type": "PT", "status": "absent", "waiver_status": "approved"},
        {"event_type": "PT", "status": "absent"},
    ]

    result = filter_rows(rows, "Excused", "All")

    assert result == [rows[0]]


def test_filter_rows_absent_excludes_approved_waiver_absence():
    rows = [
        {"event_type": "PT", "status": "absent", "waiver_status": "approved"},
        {"event_type": "PT", "status": "absent"},
    ]

    result = filter_rows(rows, "Absent", "All")

    assert result == [rows[1]]


def test_filter_rows_pt():
    rows = [
        {"event_type": "PT", "status": "absent"},
        {"event_type": "LAB", "status": "absent"},
    ]
    result = filter_rows(rows, "All", "PT")
    assert len(result) == 1
    assert result[0]["event_type"] == "PT"


def test_filter_rows_llab_is_lab():
    rows = [
        {"event_type": "LAB", "status": "present"},
        {"event_type": "PT", "status": "present"},
    ]
    result = filter_rows(rows, "All", "LLAB")
    assert len(result) == 1
    assert result[0]["event_type"] == "LAB"


def test_filter_rows_status_and_type():
    rows = [
        {"event_type": "PT", "status": "absent"},
        {"event_type": "LAB", "status": "absent"},
        {"event_type": "PT", "status": "present"},
    ]
    result = filter_rows(rows, "Absent", "PT")
    assert len(result) == 1
    assert result[0]["event_type"] == "PT"
    assert result[0]["status"] == "absent"


def test_filter_rows_no_match():
    rows = [{"event_type": "PT", "status": "present"}]
    result = filter_rows(rows, "Absent", "All")
    assert result == []


# ------------- test get_cadet_flight_label ----------------


def test_get_cadet_flight_label_flight_name():
    cadet = {"flight_id": "flight1"}
    flights = [{"_id": "flight1", "name": "Alpha"}]
    assert get_cadet_flight_label(cadet, flights) == "Alpha"


def test_get_cadet_flight_label_no_flight_id():
    cadet = {}
    flights = [{"_id": "flight1", "name": "Alpha"}]
    assert get_cadet_flight_label(cadet, flights) == "—"


def test_get_cadet_flight_label_flight_not_found():
    cadet = {"flight_id": "flight999"}
    flights = [{"_id": "flight1", "name": "Alpha"}]
    assert get_cadet_flight_label(cadet, flights) == "—"


def test_get_cadet_flight_label_flights_empty():
    cadet = {"flight_id": "flight1"}
    flights = []
    assert get_cadet_flight_label(cadet, flights) == "—"


# ---------------- standing waiver coverage ------------------


def _standing_waiver(start_offset: int, end_offset: int, event_types=None, status="approved"):
    return {
        "_id": "ws1",
        "is_standing": True,
        "status": status,
        "start_date": _dt(start_offset),
        "end_date": _dt(end_offset),
        "event_types": event_types or ["pt", "lab"],
    }


def test_standing_waiver_marks_record_as_excused():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "LLAB Week 2", "event_type": "lab", "start_date": _dt(2)}
    ]
    standing = [_standing_waiver(start_offset=5, end_offset=0)]

    rows = cadet_attendance(records, events, [], standing_waivers=standing)

    assert rows[0]["waiver_status"] == "approved"
    assert rows[0]["status"] == "waived"


def test_standing_waiver_outside_range_does_not_apply():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(20)}
    ]
    standing = [_standing_waiver(start_offset=5, end_offset=0)]

    rows = cadet_attendance(records, events, [], standing_waivers=standing)

    assert rows[0]["waiver_status"] is None


def test_standing_waiver_event_type_mismatch_does_not_apply():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(2)}
    ]
    standing = [_standing_waiver(start_offset=5, end_offset=0, event_types=["lab"])]

    rows = cadet_attendance(records, events, [], standing_waivers=standing)

    assert rows[0]["waiver_status"] is None


def test_pending_standing_waiver_does_not_excuse():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(2)}
    ]
    standing = [_standing_waiver(start_offset=5, end_offset=0, status="pending")]

    rows = cadet_attendance(records, events, [], standing_waivers=standing)

    assert rows[0]["waiver_status"] is None


def test_singular_waiver_takes_precedence_over_standing():
    records = [{"_id": "rec1", "event_id": "evt1", "status": "absent"}]
    events = [
        {"_id": "evt1", "event_name": "PT", "event_type": "pt", "start_date": _dt(2)}
    ]
    waivers = [{"_id": "w1", "attendance_record_id": "rec1", "status": "denied"}]
    standing = [_standing_waiver(start_offset=5, end_offset=0)]

    rows = cadet_attendance(records, events, waivers, standing_waivers=standing)

    assert rows[0]["waiver_status"] == "denied"
