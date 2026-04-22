from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from bson import ObjectId

import services.event_codes as event_codes_svc
import utils.db_schema_crud as crud
from services.event_codes import build_expires_at, is_expiry_valid, latest_allowed_expiry


class _FakeInsertResult:
    def __init__(self):
        self.inserted_id = ObjectId()


class _FakeCollection:
    def __init__(self):
        self._docs: list[dict] = []
        self.update_many_calls: list[dict] = []

    def update_many(self, filter: dict, update: dict):
        self.update_many_calls.append({"filter": filter, "update": update})
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in filter.items()):
                for field, val in update.get("$set", {}).items():
                    doc[field] = val

    def insert_one(self, doc: dict):
        self._docs.append(doc)
        return _FakeInsertResult()

    def find_one(self, filter: dict):
        now_check = filter.get("expires_at", {})
        gt_val = now_check.get("$gt") if isinstance(now_check, dict) else None

        for doc in self._docs:
            match = True
            for k, v in filter.items():
                if k == "expires_at":
                    continue
                if doc.get(k) != v:
                    match = False
                    break
            if match and gt_val is not None:
                exp = doc.get("expires_at")
                if exp is None or exp <= gt_val:
                    match = False
            if match:
                return doc
        return None


def test_create_event_code_inserts_doc(monkeypatch):
    col = _FakeCollection()
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    event_id = ObjectId()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    crud.create_event_code(
        code="123456",
        event_id=event_id,
        event_type="pt",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=expires_at,
    )

    assert len(col._docs) == 1
    doc = col._docs[0]
    assert doc["code"] == "123456"
    assert doc["event_id"] == ObjectId(event_id)
    assert doc["active"] is True


def test_create_event_code_no_flight_id_in_doc(monkeypatch):
    col = _FakeCollection()
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    crud.create_event_code(
        code="654321",
        event_id=ObjectId(),
        event_type="lab",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert "flight_id" not in col._docs[0]


def test_create_event_code_deactivates_all_existing_active_codes(monkeypatch):
    col = _FakeCollection()
    event_id = ObjectId()

    col._docs.extend(
        [
            {"event_id": ObjectId(event_id), "active": True, "code": "000001"},
            {"event_id": ObjectId(event_id), "active": True, "code": "000002"},
        ]
    )

    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    crud.create_event_code(
        code="111111",
        event_id=event_id,
        event_type="pt",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert col._docs[0]["active"] is False
    assert col._docs[1]["active"] is False
    assert col._docs[2]["active"] is True
    assert col._docs[2]["code"] == "111111"


def test_create_event_code_update_many_targets_event_id(monkeypatch):
    col = _FakeCollection()
    event_id = ObjectId()
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    crud.create_event_code(
        code="999999",
        event_id=event_id,
        event_type="pt",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert len(col.update_many_calls) == 1
    f = col.update_many_calls[0]["filter"]
    assert f["event_id"] == ObjectId(event_id)
    assert f["active"] is True
    assert "flight_id" not in f


def test_get_active_event_code_returns_active_unexpired(monkeypatch):
    col = _FakeCollection()
    event_id = ObjectId()
    now = datetime.now(timezone.utc)

    col._docs.append(
        {
            "event_id": ObjectId(event_id),
            "active": True,
            "expires_at": now + timedelta(hours=1),
            "code": "123456",
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    result = crud.get_active_event_code(event_id)
    assert result is not None
    assert result["code"] == "123456"


def test_get_active_event_code_returns_none_when_expired(monkeypatch):
    col = _FakeCollection()
    event_id = ObjectId()
    now = datetime.now(timezone.utc)

    col._docs.append(
        {
            "event_id": ObjectId(event_id),
            "active": True,
            "expires_at": now - timedelta(minutes=1),
            "code": "111111",
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    result = crud.get_active_event_code(event_id)
    assert result is None


def test_get_active_event_code_returns_none_when_inactive(monkeypatch):
    col = _FakeCollection()
    event_id = ObjectId()
    now = datetime.now(timezone.utc)

    col._docs.append(
        {
            "event_id": ObjectId(event_id),
            "active": False,
            "expires_at": now + timedelta(hours=1),
            "code": "222222",
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    result = crud.get_active_event_code(event_id)
    assert result is None


def test_get_active_event_code_returns_none_for_different_event(monkeypatch):
    col = _FakeCollection()
    event_a = ObjectId()
    event_b = ObjectId()
    now = datetime.now(timezone.utc)

    col._docs.append(
        {
            "event_id": ObjectId(event_a),
            "active": True,
            "expires_at": now + timedelta(hours=1),
            "code": "333333",
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    result = crud.get_active_event_code(event_b)
    assert result is None


def test_service_create_code_returns_code_and_expiry(monkeypatch):
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    monkeypatch.setattr(
        event_codes_svc, "create_event_code", lambda **kw: _FakeInsertResult()
    )

    result = event_codes_svc.create_code(
        event_id=ObjectId(),
        event_type="pt",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=expires_at,
    )

    assert result is not None
    assert len(result["code"]) == 6
    assert result["code"].isdigit()
    assert result["expires_at"] == expires_at


def test_service_create_code_returns_none_on_db_failure(monkeypatch):
    monkeypatch.setattr(event_codes_svc, "create_event_code", lambda **kw: None)

    result = event_codes_svc.create_code(
        event_id=ObjectId(),
        event_type="pt",
        event_date="2026-04-12",
        created_by_user_id=ObjectId(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert result is None


def test_service_get_active_code_delegates_to_db(monkeypatch):
    expected = {"code": "777777", "active": True}
    monkeypatch.setattr(event_codes_svc, "get_active_event_code", lambda eid: expected)

    result = event_codes_svc.get_active_code(ObjectId())
    assert result == expected


def test_service_get_active_code_returns_none_when_no_active(monkeypatch):
    monkeypatch.setattr(event_codes_svc, "get_active_event_code", lambda eid: None)

    result = event_codes_svc.get_active_code(ObjectId())
    assert result is None


def test_build_expires_at_returns_utc():
    result = build_expires_at(date(2026, 4, 12), time(16, 0), "America/New_York")
    assert result.tzinfo == timezone.utc


def test_build_expires_at_converts_eastern_to_utc():
    result = build_expires_at(date(2026, 4, 12), time(16, 0), "America/New_York")
    assert result.hour == 20
    assert result.minute == 0


def test_build_expires_at_utc_passthrough():
    result = build_expires_at(date(2026, 4, 12), time(20, 0), "UTC")
    assert result.hour == 20
    assert result.minute == 0


def test_build_expires_at_preserves_date():
    result = build_expires_at(date(2026, 6, 15), time(9, 30), "UTC")
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 15


def test_is_expiry_valid_future_returns_true():
    assert is_expiry_valid(datetime.now(timezone.utc) + timedelta(minutes=5)) is True


def test_is_expiry_valid_past_returns_false():
    assert is_expiry_valid(datetime.now(timezone.utc) - timedelta(seconds=1)) is False


def test_is_expiry_valid_now_returns_false():
    assert is_expiry_valid(datetime.now(timezone.utc)) is False


def test_is_expiry_valid_rejects_expiry_after_event_start():
    event_start = datetime.now(timezone.utc) + timedelta(minutes=10)
    expires_at = event_start + timedelta(seconds=1)
    assert is_expiry_valid(expires_at, event_start) is False


def test_is_expiry_valid_allows_expiry_at_event_start():
    event_start = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert is_expiry_valid(event_start, event_start) is True


def test_latest_allowed_expiry_returns_none_without_start():
    assert latest_allowed_expiry(None) is None


def test_latest_allowed_expiry_normalizes_naive_datetime():
    naive_start = datetime(2026, 4, 21, 12, 0, 0)
    result = latest_allowed_expiry(naive_start)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_validate_code_returns_doc_for_valid_code(monkeypatch):
    now = datetime.now(timezone.utc)
    expected = {
        "code": "123456",
        "active": True,
        "expires_at": now + timedelta(hours=1),
        "event_id": ObjectId(),
    }

    monkeypatch.setattr(
        event_codes_svc,
        "find_active_event_code_by_value",
        lambda code: expected if code == "123456" else None,
    )

    assert event_codes_svc.validate_code("123456") == expected


def test_validate_code_returns_none_for_wrong_code(monkeypatch):
    monkeypatch.setattr(
        event_codes_svc, "find_active_event_code_by_value", lambda code: None
    )

    assert event_codes_svc.validate_code("000000") is None


def test_find_active_event_code_by_value_matches(monkeypatch):
    col = _FakeCollection()
    now = datetime.now(timezone.utc)
    col._docs.append(
        {
            "code": "555555",
            "active": True,
            "expires_at": now + timedelta(hours=1),
            "event_id": ObjectId(),
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    result = crud.find_active_event_code_by_value("555555")
    assert result is not None
    assert result["code"] == "555555"


def test_find_active_event_code_by_value_no_match(monkeypatch):
    col = _FakeCollection()
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    assert crud.find_active_event_code_by_value("999999") is None


def test_find_active_event_code_by_value_expired_returns_none(monkeypatch):
    col = _FakeCollection()
    now = datetime.now(timezone.utc)
    col._docs.append(
        {
            "code": "111111",
            "active": True,
            "expires_at": now - timedelta(minutes=1),
            "event_id": ObjectId(),
        }
    )
    monkeypatch.setattr(crud, "get_collection", lambda name: col)

    assert crud.find_active_event_code_by_value("111111") is None
