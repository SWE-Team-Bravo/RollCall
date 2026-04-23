from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId

import services.attendance_modifications as modifications


class _FakeAuditCollection:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs = [dict(doc) for doc in (docs or [])]
        self.inserted: list[dict] = []

    def find(self, query: dict) -> list[dict]:
        return [dict(doc) for doc in self.docs if _matches(doc, query)]

    def find_one(self, query: dict) -> dict | None:
        for doc in self.docs:
            if _matches(doc, query):
                return dict(doc)
        return None

    def insert_one(self, doc: dict):
        stored = dict(doc)
        stored.setdefault("_id", ObjectId())
        self.docs.append(stored)
        self.inserted.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])


def _matches(doc: dict, query: dict) -> bool:
    for key, value in query.items():
        if doc.get(key) != value:
            return False
    return True


def test_apply_bulk_attendance_changes_logs_saved_rows(monkeypatch):
    log_calls: list[dict] = []
    record_id = ObjectId()

    monkeypatch.setattr(
        modifications,
        "_set_attendance_state",
        lambda **kwargs: (
            {"_id": record_id, "status": "present"},
            {"_id": record_id, "status": kwargs["status"]},
        ),
    )
    monkeypatch.setattr(
        modifications,
        "log_attendance_modification",
        lambda **kwargs: log_calls.append(kwargs),
    )

    roster = [
        {
            "cadet": {"_id": "c1"},
            "record": {"_id": record_id, "status": "present"},
            "current_status": "present",
        }
    ]

    result = modifications.apply_bulk_attendance_changes(
        event_id=ObjectId(),
        roster=roster,
        new_statuses={"c1": "absent"},
        recorded_by_user_id=ObjectId(),
        recorded_by_roles=["cadre"],
    )

    assert result["changed_count"] == 1
    assert len(log_calls) == 1
    assert log_calls[0]["outcome"] == "applied"
    assert log_calls[0]["old_status"] == "present"
    assert log_calls[0]["new_status"] == "absent"
    assert log_calls[0]["metadata"]["record_operation"] == "update"
    assert log_calls[0]["metadata"]["batch_id"]


def test_get_event_change_history_paginates_results(monkeypatch):
    event_id = ObjectId()
    actor_id = ObjectId()
    now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    cadet_ids = [ObjectId(), ObjectId(), ObjectId()]
    cadet_user_ids = [ObjectId(), ObjectId(), ObjectId()]
    docs = [
        {
            "_id": ObjectId(),
            "source": "attendance_modification",
            "event_id": event_id,
            "cadet_id": cadet_ids[offset],
            "user_id": actor_id,
            "outcome": "applied",
            "created_at": now - timedelta(minutes=offset),
            "metadata": {"old_status": "present", "new_status": "absent"},
        }
        for offset in (0, 1, 2)
    ]
    fake = _FakeAuditCollection(docs)

    monkeypatch.setattr(
        modifications,
        "get_collection",
        lambda name: fake if name == "audit_log" else None,
    )
    monkeypatch.setattr(
        modifications,
        "get_cadets_by_ids",
        lambda ids: [
            {"_id": cadet_id, "user_id": cadet_user_id}
            for cadet_id, cadet_user_id in zip(cadet_ids, cadet_user_ids)
        ],
    )
    monkeypatch.setattr(
        modifications,
        "get_users_by_ids",
        lambda ids: (
            [
                {
                    "_id": cadet_user_ids[0],
                    "first_name": "Casey",
                    "last_name": "Cadet",
                },
                {
                    "_id": cadet_user_ids[1],
                    "first_name": "Morgan",
                    "last_name": "Cadet",
                },
                {
                    "_id": cadet_user_ids[2],
                    "first_name": "Jordan",
                    "last_name": "Cadet",
                },
                {"_id": actor_id, "first_name": "Chris", "last_name": "Cadre"},
            ]
        ),
    )

    history = modifications.get_event_change_history(event_id, page=2, page_size=2)

    assert history["page"] == 2
    assert history["total_pages"] == 2
    assert history["total_count"] == 3
    assert len(history["items"]) == 1
    assert history["items"][0]["cadet_name"] == "Jordan Cadet"
    assert history["items"][0]["changed_by"] == "Chris Cadre"


def test_get_event_change_history_hides_superseded_actions(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    actor_id = ObjectId()
    cadet_user_id = ObjectId()
    now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    fake = _FakeAuditCollection(
        [
            {
                "_id": ObjectId(),
                "source": "attendance_modification",
                "event_id": event_id,
                "cadet_id": cadet_id,
                "user_id": actor_id,
                "outcome": "undo",
                "created_at": now,
                "metadata": {"old_status": "present", "new_status": "absent"},
            },
            {
                "_id": ObjectId(),
                "source": "attendance_modification",
                "event_id": event_id,
                "cadet_id": cadet_id,
                "user_id": actor_id,
                "outcome": "applied",
                "created_at": now - timedelta(minutes=1),
                "metadata": {"old_status": "absent", "new_status": "present"},
            },
        ]
    )

    monkeypatch.setattr(
        modifications,
        "get_collection",
        lambda name: fake if name == "audit_log" else None,
    )
    monkeypatch.setattr(
        modifications,
        "get_cadets_by_ids",
        lambda ids: [{"_id": cadet_id, "user_id": cadet_user_id}],
    )
    monkeypatch.setattr(
        modifications,
        "get_users_by_ids",
        lambda ids: [
            {"_id": cadet_user_id, "first_name": "Taylor", "last_name": "Cadet"},
            {"_id": actor_id, "first_name": "Jordan", "last_name": "Cadre"},
        ],
    )
    monkeypatch.setattr(
        modifications,
        "get_attendance_record_by_event_cadet",
        lambda event, cadet: {"_id": ObjectId(), "status": "absent"},
    )

    history = modifications.get_event_change_history(event_id, page=1, page_size=10)

    assert history["total_count"] == 1
    assert len(history["items"]) == 1
    assert history["items"][0]["action"] == "Undo"
    assert history["items"][0]["can_redo"] is True


def test_get_event_change_history_marks_latest_saved_change_undoable(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    actor_id = ObjectId()
    cadet_user_id = ObjectId()
    change_id = ObjectId()
    now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    fake = _FakeAuditCollection(
        [
            {
                "_id": change_id,
                "source": "attendance_modification",
                "event_id": event_id,
                "cadet_id": cadet_id,
                "user_id": actor_id,
                "outcome": "applied",
                "created_at": now,
                "metadata": {"old_status": "present", "new_status": "absent"},
            }
        ]
    )

    monkeypatch.setattr(
        modifications,
        "get_collection",
        lambda name: fake if name == "audit_log" else None,
    )
    monkeypatch.setattr(
        modifications,
        "get_cadets_by_ids",
        lambda ids: [{"_id": cadet_id, "user_id": cadet_user_id}],
    )
    monkeypatch.setattr(
        modifications,
        "get_users_by_ids",
        lambda ids: [
            {"_id": cadet_user_id, "first_name": "Taylor", "last_name": "Cadet"},
            {"_id": actor_id, "first_name": "Jordan", "last_name": "Cadre"},
        ],
    )
    monkeypatch.setattr(
        modifications,
        "get_attendance_record_by_event_cadet",
        lambda event, cadet: {"_id": ObjectId(), "status": "absent"},
    )
    monkeypatch.setattr(
        modifications,
        "get_waiver_by_attendance_record",
        lambda record_id: None,
    )

    history = modifications.get_event_change_history(event_id, page=1, page_size=10)

    assert len(history["items"]) == 1
    item = history["items"][0]
    assert item["change_id"] == str(change_id)
    assert item["can_undo"] is True
    assert item["can_redo"] is False
    assert item["undo_target_label"] == "Present"


def test_undo_change_blocks_when_reverting_to_no_record_with_waiver(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    change_id = ObjectId()
    current_record_id = ObjectId()
    fake = _FakeAuditCollection(
        [
            {
                "_id": change_id,
                "source": "attendance_modification",
                "event_id": event_id,
                "cadet_id": cadet_id,
                "user_id": ObjectId(),
                "outcome": "applied",
                "created_at": datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
                "metadata": {"old_status": None, "new_status": "absent"},
            }
        ]
    )

    monkeypatch.setattr(
        modifications,
        "get_collection",
        lambda name: fake if name == "audit_log" else None,
    )
    monkeypatch.setattr(
        modifications,
        "get_attendance_record_by_event_cadet",
        lambda event, cadet: {"_id": current_record_id, "status": "absent"},
    )
    monkeypatch.setattr(
        modifications,
        "get_waiver_by_attendance_record",
        lambda record_id: {"_id": ObjectId()},
    )

    ok, message = modifications.undo_change(
        change_id,
        recorded_by_user_id=ObjectId(),
        recorded_by_roles=["cadre"],
    )

    assert ok is False
    assert "waiver attached" in message


def test_redo_change_reapplies_latest_undo(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    change_id = ObjectId()
    captured_statuses: list[str | None] = []
    logged: list[dict] = []
    fake = _FakeAuditCollection(
        [
            {
                "_id": change_id,
                "source": "attendance_modification",
                "event_id": event_id,
                "cadet_id": cadet_id,
                "user_id": ObjectId(),
                "outcome": "undo",
                "created_at": datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
                "metadata": {"old_status": "present", "new_status": "absent"},
            }
        ]
    )

    monkeypatch.setattr(
        modifications,
        "get_collection",
        lambda name: fake if name == "audit_log" else None,
    )
    monkeypatch.setattr(
        modifications,
        "get_attendance_record_by_event_cadet",
        lambda event, cadet: {"_id": ObjectId(), "status": "absent"},
    )

    def _fake_set_attendance_state(**kwargs):
        captured_statuses.append(kwargs["status"])
        return (
            {"_id": ObjectId(), "status": "absent"},
            {"_id": ObjectId(), "status": kwargs["status"]},
        )

    monkeypatch.setattr(
        modifications,
        "_set_attendance_state",
        _fake_set_attendance_state,
    )
    monkeypatch.setattr(
        modifications,
        "log_attendance_modification",
        lambda **kwargs: logged.append(kwargs),
    )

    ok, message = modifications.redo_change(
        change_id,
        recorded_by_user_id=ObjectId(),
        recorded_by_roles=["cadre"],
    )

    assert ok is True
    assert message == "Attendance change redone."
    assert captured_statuses == ["present"]
    assert logged[0]["outcome"] == "redo"
    assert logged[0]["old_status"] == "absent"
    assert logged[0]["new_status"] == "present"
    assert logged[0]["metadata"]["redoes_audit_id"] == str(change_id)
