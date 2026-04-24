from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from bson import ObjectId

import utils.audit_log as audit_log


class _FakeCollection:
    def __init__(self) -> None:
        self.inserted: list[dict] = []

    def insert_one(self, doc: dict):
        self.inserted.append(doc)
        return SimpleNamespace(inserted_id=ObjectId())


def test_log_checkin_attempt_returns_none_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(audit_log, "get_collection", lambda name: None)
    result = audit_log.log_checkin_attempt(cadet_id=ObjectId(), outcome="success")
    assert result is None


def test_log_checkin_attempt_writes_required_fields(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(audit_log, "get_collection", lambda name: fake)

    cadet_id = ObjectId()
    now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)

    audit_log.log_checkin_attempt(
        cadet_id=cadet_id,
        outcome="invalid_code",
        attempted_code="123456",
        source="attendance_submission",
        now=now,
        metadata={"x": 1},
    )

    assert len(fake.inserted) == 1
    doc = fake.inserted[0]

    assert doc["cadet_id"] == cadet_id
    assert doc["created_at"] == now
    assert doc["outcome"] == "invalid_code"
    assert doc["source"] == "attendance_submission"
    assert doc["metadata"] == {"x": 1}

    # Raw code should not be stored.
    assert "attempted_code" not in doc
    assert "attempted_code_sha256" in doc
    assert isinstance(doc["attempted_code_sha256"], str)
    assert len(doc["attempted_code_sha256"]) == 64


def test_log_checkin_attempt_converts_string_ids_to_object_ids(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(audit_log, "get_collection", lambda name: fake)

    cadet_id = ObjectId()
    event_id = ObjectId()
    user_id = ObjectId()

    audit_log.log_checkin_attempt(
        cadet_id=str(cadet_id),
        outcome="success",
        event_id=str(event_id),
        user_id=str(user_id),
    )

    doc = fake.inserted[0]
    assert doc["cadet_id"] == cadet_id
    assert doc["event_id"] == event_id
    assert doc["user_id"] == user_id


def test_log_attendance_modification_writes_expected_fields(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(audit_log, "get_collection", lambda name: fake)

    event_id = ObjectId()
    cadet_id = ObjectId()
    user_id = ObjectId()
    now = datetime(2026, 4, 22, 15, 30, 0, tzinfo=timezone.utc)

    audit_log.log_attendance_modification(
        event_id=event_id,
        cadet_id=cadet_id,
        user_id=user_id,
        outcome="undo",
        old_status="present",
        new_status=None,
        now=now,
        metadata={"reverts_audit_id": str(ObjectId())},
    )

    assert len(fake.inserted) == 1
    doc = fake.inserted[0]

    assert doc["created_at"] == now
    assert doc["event_id"] == event_id
    assert doc["cadet_id"] == cadet_id
    assert doc["user_id"] == user_id
    assert doc["outcome"] == "undo"
    assert doc["source"] == "attendance_modification"
    assert doc["metadata"]["old_status"] == "present"
    assert doc["metadata"]["new_status"] is None
    assert "reverts_audit_id" in doc["metadata"]


def test_redact_audit_document_redacts_sensitive_fields():
    redacted = audit_log.redact_audit_document(
        {
            "email": "cadet@example.com",
            "password_hash": "hash",
            "profile": {
                "token": "secret-token",
                "notes": "keep",
            },
            "codes": [
                {"checkin_code": "123456"},
                {"attempted_code_sha256": "abc123"},
            ],
        }
    )

    assert redacted == {
        "email": "cadet@example.com",
        "password_hash": "[REDACTED]",
        "profile": {
            "token": "[REDACTED]",
            "notes": "keep",
        },
        "codes": [
            {"checkin_code": "[REDACTED]"},
            {"attempted_code_sha256": "abc123"},
        ],
    }


def test_build_audit_changes_flattens_nested_dict_changes():
    before = {
        "email": "old@example.com",
        "roles": ["cadet"],
        "status": {"disabled": False, "reason": None},
    }
    after = {
        "email": "new@example.com",
        "roles": ["cadet", "flight_commander"],
        "status": {"disabled": True, "reason": "Admin action"},
    }

    assert audit_log.build_audit_changes(before, after) == {
        "email": {"from": "old@example.com", "to": "new@example.com"},
        "roles": {"from": ["cadet"], "to": ["cadet", "flight_commander"]},
        "status.disabled": {"from": False, "to": True},
        "status.reason": {"from": None, "to": "Admin action"},
    }


def test_log_data_change_writes_redacted_generic_entry(monkeypatch):
    fake = _FakeCollection()
    monkeypatch.setattr(audit_log, "get_collection", lambda name: fake)

    actor_user_id = ObjectId()
    target_id = ObjectId()
    now = datetime(2026, 4, 24, 18, 45, 0, tzinfo=timezone.utc)

    audit_log.log_data_change(
        source="user_management",
        action="disable",
        target_collection="users",
        target_id=str(target_id),
        actor_user_id=str(actor_user_id),
        actor_email="admin@example.com",
        actor_roles=["admin"],
        target_label="Cadet Example",
        before={
            "email": "cadet@example.com",
            "disabled": False,
            "password_hash": "stored-hash",
        },
        after={
            "email": "cadet@example.com",
            "disabled": True,
            "password_hash": "new-stored-hash",
        },
        metadata={"temporary_password": "top-secret"},
        now=now,
    )

    assert len(fake.inserted) == 1
    doc = fake.inserted[0]

    assert doc["created_at"] == now
    assert doc["source"] == "user_management"
    assert doc["action"] == "disable"
    assert doc["target_collection"] == "users"
    assert doc["target_id"] == target_id
    assert doc["actor_user_id"] == actor_user_id
    assert doc["actor_email"] == "admin@example.com"
    assert doc["actor_roles"] == ["admin"]
    assert doc["target_label"] == "Cadet Example"
    assert doc["before"]["password_hash"] == "[REDACTED]"
    assert doc["after"]["password_hash"] == "[REDACTED]"
    assert doc["changes"] == {
        "disabled": {"from": False, "to": True},
    }
    assert doc["metadata"] == {"temporary_password": "[REDACTED]"}


def test_log_data_change_returns_none_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(audit_log, "get_collection", lambda name: None)

    result = audit_log.log_data_change(
        source="event_management",
        action="archive",
        target_collection="events",
        target_id=ObjectId(),
    )

    assert result is None
