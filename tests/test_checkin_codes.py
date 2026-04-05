from __future__ import annotations

from datetime import datetime, timedelta, timezone

import utils.checkin_codes as checkin_codes


class _FakeCollection:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def insert_one(self, doc: dict):
        # Not needed for these tests.
        raise NotImplementedError

    def find_one(self, filter: dict, sort=None):
        def matches(doc: dict) -> bool:
            for k, v in filter.items():
                if doc.get(k) != v:
                    return False
            return True

        candidates = [d for d in self._docs if matches(d)]
        if not candidates:
            return None

        if sort:
            # sort is list of (field, direction)
            field, direction = sort[0]
            reverse = direction < 0
            candidates.sort(key=lambda d: d.get(field), reverse=reverse)
        return candidates[0]


def test_validate_checkin_code_invalid_when_no_codes(monkeypatch):
    monkeypatch.setattr(
        checkin_codes, "get_collection", lambda name: _FakeCollection([])
    )
    assert (
        checkin_codes.validate_checkin_code(code="123456", kind="attendance_submission")
        == "invalid_code"
    )


def test_validate_checkin_code_success_for_current_unexpired(monkeypatch):
    now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
    code = "111111"
    code_hash = checkin_codes._sha256_hex(code)

    docs = [
        {
            "_id": "a",
            "kind": "attendance_submission",
            "created_at": now - timedelta(minutes=1),
            "expires_at": now + timedelta(minutes=10),
            "code_sha256": code_hash,
        }
    ]
    monkeypatch.setattr(
        checkin_codes, "get_collection", lambda name: _FakeCollection(docs)
    )
    assert (
        checkin_codes.validate_checkin_code(
            code=code,
            kind="attendance_submission",
            now=now,
        )
        == "success"
    )


def test_validate_checkin_code_expired_for_current_expired(monkeypatch):
    now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
    code = "222222"
    code_hash = checkin_codes._sha256_hex(code)

    docs = [
        {
            "_id": "a",
            "kind": "attendance_submission",
            "created_at": now - timedelta(minutes=30),
            "expires_at": now - timedelta(minutes=1),
            "code_sha256": code_hash,
        }
    ]
    monkeypatch.setattr(
        checkin_codes, "get_collection", lambda name: _FakeCollection(docs)
    )
    assert (
        checkin_codes.validate_checkin_code(
            code=code,
            kind="attendance_submission",
            now=now,
        )
        == "expired_code"
    )


def test_validate_checkin_code_handles_naive_expires_at(monkeypatch):
    now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
    code = "999999"
    code_hash = checkin_codes._sha256_hex(code)

    # Simulate PyMongo returning naive datetimes.
    docs = [
        {
            "_id": "a",
            "kind": "attendance_submission",
            "created_at": (now - timedelta(minutes=30)).replace(tzinfo=None),
            "expires_at": (now - timedelta(minutes=1)).replace(tzinfo=None),
            "code_sha256": code_hash,
        }
    ]

    monkeypatch.setattr(
        checkin_codes, "get_collection", lambda name: _FakeCollection(docs)
    )
    assert (
        checkin_codes.validate_checkin_code(
            code=code,
            kind="attendance_submission",
            now=now,
        )
        == "expired_code"
    )


def test_validate_checkin_code_expired_for_old_replaced_code(monkeypatch):
    now = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
    old_code = "333333"
    new_code = "444444"
    old_hash = checkin_codes._sha256_hex(old_code)
    new_hash = checkin_codes._sha256_hex(new_code)

    docs = [
        {
            "_id": "old",
            "kind": "attendance_submission",
            "created_at": now - timedelta(minutes=5),
            "expires_at": now + timedelta(minutes=10),
            "code_sha256": old_hash,
        },
        {
            "_id": "new",
            "kind": "attendance_submission",
            "created_at": now - timedelta(minutes=1),
            "expires_at": now + timedelta(minutes=10),
            "code_sha256": new_hash,
        },
    ]

    monkeypatch.setattr(
        checkin_codes, "get_collection", lambda name: _FakeCollection(docs)
    )

    # Old code was issued, but replaced by a newer current code.
    assert (
        checkin_codes.validate_checkin_code(
            code=old_code,
            kind="attendance_submission",
            now=now,
        )
        == "expired_code"
    )
