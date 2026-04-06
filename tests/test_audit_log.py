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
