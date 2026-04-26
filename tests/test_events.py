from datetime import date, datetime, time, timezone

from bson import ObjectId

import services.events as events_service
import utils.db_schema_crud as db_schema_crud
from services.events import (
    archive_event,
    build_event_bounds,
    create_event,
    get_event_time_bounds,
    get_all_events,
    has_event_ended,
    restore_event,
    update_event,
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


class _FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _FakeUpdateResult:
    def __init__(self, matched_count: int, modified_count: int):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def __iter__(self):
        return iter(self._docs)

    def __len__(self) -> int:
        return len(self._docs)

    def sort(self, field: str, direction: int) -> "_FakeCursor":
        reverse = direction == -1
        return _FakeCursor(
            sorted(self._docs, key=lambda doc: doc.get(field), reverse=reverse)
        )


def _matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class _FakeEventsCollection:
    def __init__(self, docs: list[dict]):
        self.docs = [dict(doc) for doc in docs]

    def find(self, query: dict):
        return _FakeCursor([dict(doc) for doc in self.docs if _matches(doc, query)])

    def find_one(self, query: dict):
        for doc in self.docs:
            if _matches(doc, query):
                return dict(doc)
        return None

    def insert_one(self, doc: dict):
        inserted_id = doc.get("_id", ObjectId())
        stored = dict(doc)
        stored["_id"] = inserted_id
        self.docs.append(stored)
        return _FakeInsertResult(inserted_id)

    def update_one(self, query: dict, update: dict):
        for index, doc in enumerate(self.docs):
            if not _matches(doc, query):
                continue
            updated = dict(doc)
            for key, value in update.get("$set", {}).items():
                updated[key] = value
            for key in update.get("$unset", {}):
                updated.pop(key, None)
            modified = updated != self.docs[index]
            self.docs[index] = updated
            return _FakeUpdateResult(
                matched_count=1, modified_count=1 if modified else 0
            )
        return _FakeUpdateResult(matched_count=0, modified_count=0)


class _FakeDb:
    def __init__(self, docs: list[dict]):
        self.events = _FakeEventsCollection(docs)


def test_get_all_events_excludes_archived_by_default(monkeypatch):
    active_id = ObjectId()
    archived_id = ObjectId()
    fake_db = _FakeDb(
        [
            {
                "_id": active_id,
                "event_name": "Active",
                "start_date": datetime(2026, 4, 26, tzinfo=timezone.utc),
                "archived": False,
            },
            {
                "_id": archived_id,
                "event_name": "Archived",
                "start_date": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "archived": True,
            },
        ]
    )
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)

    active_events = get_all_events()
    all_events = get_all_events(include_archived=True)

    assert [event["_id"] for event in active_events] == [str(active_id)]
    assert {event["_id"] for event in all_events} == {str(active_id), str(archived_id)}


def test_archive_event_sets_archive_fields_and_logs_audit(monkeypatch):
    event_id = ObjectId()
    actor_id = ObjectId()
    fake_db = _FakeDb(
        [
            {
                "_id": event_id,
                "event_name": "Week 3 PT",
                "event_type": "pt",
                "archived": False,
            }
        ]
    )
    logged: list[dict] = []
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(
        events_service, "log_data_change", lambda **kwargs: logged.append(kwargs)
    )

    assert archive_event(
        str(event_id), actor_user_id=str(actor_id), actor_email="admin@example.com"
    )

    updated = fake_db.events.find_one({"_id": event_id})
    assert updated is not None
    assert updated["archived"] is True
    assert updated["archived_by_user_id"] == actor_id
    assert isinstance(updated["archived_at"], datetime)
    assert logged[0]["action"] == "archive"


def test_restore_event_clears_archive_fields_and_logs_audit(monkeypatch):
    event_id = ObjectId()
    actor_id = ObjectId()
    fake_db = _FakeDb(
        [
            {
                "_id": event_id,
                "event_name": "Week 3 PT",
                "event_type": "pt",
                "archived": True,
                "archived_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
                "archived_by_user_id": actor_id,
            }
        ]
    )
    logged: list[dict] = []
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(
        events_service, "log_data_change", lambda **kwargs: logged.append(kwargs)
    )

    assert restore_event(
        str(event_id), actor_user_id=str(actor_id), actor_email="admin@example.com"
    )

    updated = fake_db.events.find_one({"_id": event_id})
    assert updated is not None
    assert updated["archived"] is False
    assert "archived_at" not in updated
    assert "archived_by_user_id" not in updated
    assert updated["restored_by_user_id"] == actor_id
    assert logged[0]["action"] == "restore"


def test_get_events_by_type_excludes_archived_by_default(monkeypatch):
    col = _FakeEventsCollection(
        [
            {"_id": ObjectId(), "event_type": "pt", "archived": False},
            {"_id": ObjectId(), "event_type": "pt", "archived": True},
            {"_id": ObjectId(), "event_type": "lab", "archived": False},
        ]
    )
    monkeypatch.setattr(
        db_schema_crud,
        "get_collection",
        lambda name: col if name == "events" else None,
    )

    pt_events = db_schema_crud.get_events_by_type("pt")
    all_pt_events = db_schema_crud.get_events_by_type("pt", include_archived=True)

    assert len(pt_events) == 1
    assert len(all_pt_events) == 2


# ── build_event_bounds: custom time params ────────────────────────────────────


def test_build_event_bounds_with_custom_start_time() -> None:
    start_at, _ = build_event_bounds(
        date(2026, 4, 25),
        date(2026, 4, 25),
        "America/New_York",
        start_time=time(6, 30),
    )
    # America/New_York is UTC-4 in April; 06:30 local = 10:30 UTC
    assert start_at == datetime(2026, 4, 25, 10, 30, tzinfo=timezone.utc)


def test_build_event_bounds_with_custom_end_time() -> None:
    _, end_at = build_event_bounds(
        date(2026, 4, 25),
        date(2026, 4, 25),
        "America/New_York",
        end_time=time(7, 30),
    )
    # 07:30 local EDT = 11:30 UTC
    assert end_at == datetime(2026, 4, 25, 11, 30, tzinfo=timezone.utc)


def test_build_event_bounds_default_is_midnight_to_2359() -> None:
    start_at, end_at = build_event_bounds(date(2026, 4, 25), date(2026, 4, 25), "UTC")
    assert start_at.hour == 0 and start_at.minute == 0 and start_at.second == 0
    assert end_at.hour == 23 and end_at.minute == 59 and end_at.second == 59


# ── create_event: geofence fields ────────────────────────────────────────────


def _make_fake_db(docs=None) -> _FakeDb:
    return _FakeDb(docs or [])


def test_create_event_stores_geofence_fields(monkeypatch) -> None:
    fake_db = _make_fake_db()
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    result = create_event(
        name="Geofence PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        created_by_user_id="000000000000000000000001",
        geofence_enabled=True,
        geofence_lat=41.1548,
        geofence_lon=-81.3414,
        geofence_radius_meters=200,
    )

    assert result is True
    stored = fake_db.events.docs[0]
    assert stored["geofence_enabled"] is True
    assert stored["geofence_lat"] == 41.1548
    assert stored["geofence_lon"] == -81.3414
    assert stored["geofence_radius_meters"] == 200


def test_create_event_clears_geofence_coords_when_disabled(monkeypatch) -> None:
    fake_db = _make_fake_db()
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    create_event(
        name="No Fence PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        created_by_user_id="000000000000000000000001",
        geofence_enabled=False,
        geofence_lat=41.1548,
        geofence_lon=-81.3414,
    )

    stored = fake_db.events.docs[0]
    assert stored["geofence_enabled"] is False
    assert stored["geofence_lat"] is None
    assert stored["geofence_lon"] is None


def test_create_event_stores_custom_times(monkeypatch) -> None:
    fake_db = _make_fake_db()
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    create_event(
        name="Morning PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        created_by_user_id="000000000000000000000001",
        tz_name="UTC",
        start_time=time(6, 0),
        end_time=time(7, 0),
    )

    stored = fake_db.events.docs[0]
    assert stored["start_date"] == datetime(2026, 5, 1, 6, 0, tzinfo=timezone.utc)
    assert stored["end_date"] == datetime(2026, 5, 1, 7, 0, tzinfo=timezone.utc)


# ── update_event: matched_count fix and new fields ───────────────────────────


def _event_doc(event_id: ObjectId) -> dict:
    return {
        "_id": event_id,
        "event_name": "Test PT",
        "event_type": "PT",
        "start_date": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        "end_date": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
        "timezone_name": "UTC",
        "archived": False,
        "geofence_enabled": False,
        "geofence_lat": None,
        "geofence_lon": None,
        "geofence_radius_meters": None,
    }


def test_update_event_returns_true_when_no_fields_changed(monkeypatch) -> None:
    event_id = ObjectId()
    fake_db = _FakeDb([_event_doc(event_id)])
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    result = update_event(
        str(event_id),
        name="Test PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        tz_name="UTC",
        start_time=time(10, 0),
        end_time=time(11, 0),
    )

    assert result is True


def test_update_event_returns_false_for_unknown_id(monkeypatch) -> None:
    fake_db = _FakeDb([])
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    assert (
        update_event(
            str(ObjectId()),
            name="Ghost",
            event_type="PT",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
        )
        is False
    )


def test_update_event_stores_geofence_fields(monkeypatch) -> None:
    event_id = ObjectId()
    fake_db = _FakeDb([_event_doc(event_id)])
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    result = update_event(
        str(event_id),
        name="Test PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        tz_name="UTC",
        geofence_enabled=True,
        geofence_lat=41.1548,
        geofence_lon=-81.3414,
        geofence_radius_meters=150,
    )

    assert result is True
    stored = fake_db.events.find_one({"_id": event_id})
    assert stored["geofence_enabled"] is True
    assert stored["geofence_lat"] == 41.1548


def test_update_event_clears_geofence_when_disabled(monkeypatch) -> None:
    event_id = ObjectId()
    doc = _event_doc(event_id)
    doc.update(
        {
            "geofence_enabled": True,
            "geofence_lat": 41.0,
            "geofence_lon": -81.0,
            "geofence_radius_meters": 100,
        }
    )
    fake_db = _FakeDb([doc])
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    update_event(
        str(event_id),
        name="Test PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        geofence_enabled=False,
    )

    stored = fake_db.events.find_one({"_id": event_id})
    assert stored["geofence_enabled"] is False
    assert stored["geofence_lat"] is None
    assert stored["geofence_lon"] is None


def test_update_event_stores_custom_times(monkeypatch) -> None:
    event_id = ObjectId()
    fake_db = _FakeDb([_event_doc(event_id)])
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(events_service, "log_data_change", lambda **kw: None)

    update_event(
        str(event_id),
        name="Test PT",
        event_type="PT",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        tz_name="UTC",
        start_time=time(6, 30),
        end_time=time(7, 30),
    )

    stored = fake_db.events.find_one({"_id": event_id})
    assert stored["start_date"] == datetime(2026, 5, 1, 6, 30, tzinfo=timezone.utc)
    assert stored["end_date"] == datetime(2026, 5, 1, 7, 30, tzinfo=timezone.utc)


# ── get_all_events: _display_start and _display_end ──────────────────────────


def test_get_all_events_includes_display_start_and_end(monkeypatch) -> None:
    fake_db = _FakeDb(
        [
            {
                "_id": ObjectId(),
                "event_name": "Morning PT",
                "start_date": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                "end_date": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
                "timezone_name": "UTC",
                "archived": False,
            }
        ]
    )
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)

    events = get_all_events()

    assert len(events) == 1
    assert "_display_start" in events[0]
    assert "_display_end" in events[0]


def test_get_all_events_display_start_uses_event_timezone(monkeypatch) -> None:
    fake_db = _FakeDb(
        [
            {
                "_id": ObjectId(),
                "event_name": "Morning PT",
                # 10:00 UTC = 06:00 EDT (UTC-4)
                "start_date": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                "end_date": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
                "timezone_name": "America/New_York",
                "archived": False,
            }
        ]
    )
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)

    events = get_all_events()

    assert "06:00" in events[0]["_display_start"]


def test_get_all_events_display_end_reflects_end_date(monkeypatch) -> None:
    fake_db = _FakeDb(
        [
            {
                "_id": ObjectId(),
                "event_name": "Morning PT",
                "start_date": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                "end_date": datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc),
                "timezone_name": "UTC",
                "archived": False,
            }
        ]
    )
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)

    events = get_all_events()

    assert "11:00" in events[0]["_display_end"]
    assert "10:00" in events[0]["_display_start"]


def test_get_all_events_display_start_is_dash_for_missing_datetime(monkeypatch) -> None:
    fake_db = _FakeDb(
        [
            {
                "_id": ObjectId(),
                "event_name": "Bad Event",
                "start_date": "not-a-datetime",
                "archived": False,
            }
        ]
    )
    monkeypatch.setattr(events_service, "get_db", lambda: fake_db)

    events = get_all_events()

    assert events[0]["_display_start"] == "—"
    assert events[0]["_display_end"] == "—"
