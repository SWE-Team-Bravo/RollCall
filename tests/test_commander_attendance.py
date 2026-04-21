from services.commander_attendance import build_commander_roster, compute_upserts


# ── build_commander_roster ────────────────────────────────────────────────────


def test_roster_pairs_record_with_cadet():
    cadets = [{"_id": "c1", "first_name": "Alice", "last_name": "Smith"}]
    records = [{"cadet_id": "c1", "_id": "r1", "status": "present"}]

    roster = build_commander_roster(cadets, records)

    assert len(roster) == 1
    assert roster[0]["current_status"] == "present"
    assert roster[0]["record"]["_id"] == "r1"


def test_roster_cadet_with_no_record_has_none_status():
    cadets = [{"_id": "c1", "first_name": "Alice", "last_name": "Smith"}]

    roster = build_commander_roster(cadets, [])

    assert roster[0]["current_status"] is None
    assert roster[0]["record"] is None


def test_roster_sorted_by_last_then_first():
    cadets = [
        {"_id": "c1", "first_name": "Bob", "last_name": "Smith"},
        {"_id": "c2", "first_name": "Alice", "last_name": "Jones"},
        {"_id": "c3", "first_name": "Amy", "last_name": "Jones"},
    ]

    roster = build_commander_roster(cadets, [])

    assert [e["cadet"]["_id"] for e in roster] == ["c2", "c3", "c1"]


def test_roster_sorting_is_case_insensitive():
    cadets = [
        {"_id": "c1", "first_name": "alice", "last_name": "SMITH"},
        {"_id": "c2", "first_name": "Bob", "last_name": "jones"},
    ]

    roster = build_commander_roster(cadets, [])

    assert roster[0]["cadet"]["_id"] == "c2"
    assert roster[1]["cadet"]["_id"] == "c1"


def test_roster_record_from_other_cadet_not_matched():
    cadets = [{"_id": "c1", "first_name": "Alice", "last_name": "Smith"}]
    records = [{"cadet_id": "c999", "_id": "r1", "status": "present"}]

    roster = build_commander_roster(cadets, records)

    assert roster[0]["current_status"] is None


def test_roster_multiple_cadets_multiple_records():
    cadets = [
        {"_id": "c1", "first_name": "Alice", "last_name": "A"},
        {"_id": "c2", "first_name": "Bob", "last_name": "B"},
        {"_id": "c3", "first_name": "Carol", "last_name": "C"},
    ]
    records = [
        {"cadet_id": "c1", "_id": "r1", "status": "present"},
        {"cadet_id": "c3", "_id": "r3", "status": "absent"},
    ]

    roster = build_commander_roster(cadets, records)
    by_id = {e["cadet"]["_id"]: e for e in roster}

    assert by_id["c1"]["current_status"] == "present"
    assert by_id["c2"]["current_status"] is None
    assert by_id["c3"]["current_status"] == "absent"


# ── compute_upserts ───────────────────────────────────────────────────────────


def test_upsert_creates_record_when_none_exists():
    roster = [{"cadet": {"_id": "c1"}, "record": None, "current_status": None}]
    new_statuses = {"c1": "present"}

    upserts = compute_upserts(roster, new_statuses)

    assert len(upserts) == 1
    assert upserts[0]["action"] == "create"
    assert upserts[0]["cadet_id"] == "c1"
    assert upserts[0]["record_id"] is None
    assert upserts[0]["status"] == "present"


def test_upsert_updates_record_when_one_exists():
    roster = [
        {
            "cadet": {"_id": "c1"},
            "record": {"_id": "r1", "status": "present"},
            "current_status": "present",
        }
    ]
    new_statuses = {"c1": "absent"}

    upserts = compute_upserts(roster, new_statuses)

    assert upserts[0]["action"] == "update"
    assert upserts[0]["record_id"] == "r1"
    assert upserts[0]["status"] == "absent"


def test_upsert_skips_unchanged_existing_record():
    roster = [
        {
            "cadet": {"_id": "c1"},
            "record": {"_id": "r1", "status": "present"},
            "current_status": "present",
        }
    ]

    assert compute_upserts(roster, {"c1": "present"}) == []


def test_upsert_commander_wins_over_existing_status():
    roster = [
        {
            "cadet": {"_id": "c1"},
            "record": {"_id": "r1", "status": "present"},
            "current_status": "present",
        }
    ]
    new_statuses = {"c1": "absent"}

    upserts = compute_upserts(roster, new_statuses)

    assert upserts[0]["status"] == "absent"


def test_upsert_skips_cadet_missing_from_new_statuses():
    roster = [
        {"cadet": {"_id": "c1"}, "record": None, "current_status": None},
        {"cadet": {"_id": "c2"}, "record": None, "current_status": None},
    ]
    new_statuses = {"c1": "present"}  # c2 omitted

    upserts = compute_upserts(roster, new_statuses)

    assert len(upserts) == 1
    assert upserts[0]["cadet_id"] == "c1"


def test_upsert_all_three_statuses():
    roster = [
        {"cadet": {"_id": "c1"}, "record": None, "current_status": None},
        {"cadet": {"_id": "c2"}, "record": None, "current_status": None},
        {"cadet": {"_id": "c3"}, "record": None, "current_status": None},
    ]
    new_statuses = {"c1": "present", "c2": "absent", "c3": "excused"}

    upserts = compute_upserts(roster, new_statuses)
    by_id = {u["cadet_id"]: u for u in upserts}

    assert by_id["c1"]["status"] == "present"
    assert by_id["c2"]["status"] == "absent"
    assert by_id["c3"]["status"] == "excused"


def test_upsert_empty_roster_returns_empty():
    assert compute_upserts([], {}) == []
