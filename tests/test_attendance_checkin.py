from services.attendance import is_already_checked_in


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
