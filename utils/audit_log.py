from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.results import InsertOneResult

from utils.checkin_codes import _sha256_hex, _utcnow
from utils.db import get_collection

_REDACTED_VALUE = "[REDACTED]"
_SENSITIVE_FIELD_NAMES = {
    "api_key",
    "attempted_code",
    "auth_cookie",
    "checkin_code",
    "code",
    "cookie",
    "event_code",
    "password",
    "password_hash",
    "secret",
    "temp_password",
    "temporary_password",
    "token",
}
_MISSING = object()


def _normalize_reference_id(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        try:
            return ObjectId(value)
        except Exception:
            return value
    return value


def _is_sensitive_field_name(field_name: str | None) -> bool:
    normalized = str(field_name or "").strip().lower()
    if not normalized:
        return False
    if normalized in _SENSITIVE_FIELD_NAMES:
        return True
    return any(
        token in normalized for token in ("password", "token", "secret", "cookie")
    )


def redact_audit_value(value: Any, *, field_name: str | None = None) -> Any:
    if _is_sensitive_field_name(field_name):
        return _REDACTED_VALUE

    if isinstance(value, dict):
        return {
            str(key): redact_audit_value(nested_value, field_name=str(key))
            for key, nested_value in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [redact_audit_value(item) for item in value]

    return value


def redact_audit_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {
        str(key): redact_audit_value(value, field_name=str(key))
        for key, value in document.items()
    }


def serialize_doc_for_audit(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Deep-copy a document and stringify its ``_id`` for audit snapshots."""
    if doc is None:
        return None
    serialized = dict(doc)
    if serialized.get("_id") is not None:
        serialized["_id"] = str(serialized["_id"])
    return serialized


def _collect_changes(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    prefix: str = "",
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    keys = {str(key) for key in before} | {str(key) for key in after}

    for key in sorted(keys):
        path = f"{prefix}.{key}" if prefix else key
        before_value = before.get(key, _MISSING)
        after_value = after.get(key, _MISSING)

        if isinstance(before_value, dict) and isinstance(after_value, dict):
            changes.update(_collect_changes(before_value, after_value, prefix=path))
            continue

        if before_value == after_value:
            continue

        changes[path] = {
            "from": None if before_value is _MISSING else before_value,
            "to": None if after_value is _MISSING else after_value,
        }

    return changes


def build_audit_changes(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    return _collect_changes(before or {}, after or {})


def log_data_change(
    *,
    source: str,
    action: str,
    target_collection: str,
    target_id: str | ObjectId | None,
    actor_user_id: str | ObjectId | None = None,
    actor_email: str | None = None,
    actor_roles: list[str] | None = None,
    target_label: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    now: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> InsertOneResult | None:
    """Write a generic data-change audit entry with redacted snapshots."""

    col = get_collection("audit_log")
    if col is None:
        return None

    redacted_before = redact_audit_document(before)
    redacted_after = redact_audit_document(after)

    doc: dict[str, Any] = {
        "created_at": now or _utcnow(),
        "source": str(source),
        "action": str(action),
        "target_collection": str(target_collection),
        "target_id": _normalize_reference_id(target_id),
        "actor_roles": list(actor_roles or []),
        "before": redacted_before,
        "after": redacted_after,
        "changes": build_audit_changes(redacted_before, redacted_after),
    }

    if actor_user_id is not None:
        try:
            doc["actor_user_id"] = ObjectId(actor_user_id)
        except Exception:
            doc["actor_user_id_raw"] = str(actor_user_id)

    if actor_email is not None:
        doc["actor_email"] = str(actor_email)

    if target_label is not None:
        doc["target_label"] = str(target_label)

    if metadata:
        doc["metadata"] = redact_audit_value(dict(metadata))

    return col.insert_one(doc)


def log_checkin_attempt(
    *,
    cadet_id: str | ObjectId,
    outcome: str,
    attempted_code: str | None = None,
    event_id: str | ObjectId | None = None,
    user_id: str | ObjectId | None = None,
    source: str = "checkin",
    now: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> InsertOneResult | None:
    """Write a check-in attempt audit entry.

    Required by spec:
    - timestamp (stored as ``created_at``)
    - cadet ID
    - outcome (e.g. success, duplicate, expired_code, invalid_code)

    Notes:
    - ``attempted_code`` is stored only as a SHA-256 hash for troubleshooting
      without retaining the raw code.
    - If MongoDB is unavailable, this returns None (best-effort logging).
    """

    col = get_collection("audit_log")
    if col is None:
        return None

    doc: dict[str, Any] = {
        "created_at": now or _utcnow(),
        "cadet_id": ObjectId(cadet_id),
        "outcome": str(outcome),
        "source": str(source),
    }

    if event_id is not None:
        doc["event_id"] = ObjectId(event_id)

    if user_id is not None:
        doc["user_id"] = ObjectId(user_id)

    if attempted_code is not None:
        attempted_code = str(attempted_code)
        if attempted_code:
            doc["attempted_code_sha256"] = _sha256_hex(attempted_code)

    if metadata:
        # Keep metadata shallow/JSON-ish; don't enforce schema here.
        doc["metadata"] = dict(metadata)

    return col.insert_one(doc)


def log_attendance_modification(
    *,
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
    user_id: str | ObjectId,
    outcome: str,
    old_status: str | None,
    new_status: str | None,
    source: str = "attendance_modification",
    now: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> InsertOneResult | None:
    """Write an attendance modification audit entry."""

    col = get_collection("audit_log")
    if col is None:
        return None

    doc: dict[str, Any] = {
        "created_at": now or _utcnow(),
        "event_id": ObjectId(event_id),
        "cadet_id": ObjectId(cadet_id),
        "user_id": ObjectId(user_id),
        "outcome": str(outcome),
        "source": str(source),
        "metadata": {
            "old_status": old_status,
            "new_status": new_status,
        },
    }

    if metadata:
        doc["metadata"].update(dict(metadata))

    return col.insert_one(doc)
