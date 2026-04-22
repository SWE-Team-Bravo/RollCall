from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from pymongo import DESCENDING

from utils.db import get_collection
from utils.datetime_utils import ensure_utc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_checkin_code(
    *,
    code: str,
    ttl_minutes: int,
    kind: str = "attendance_submission",
    now: datetime | None = None,
) -> dict | None:
    """Persist an issued check-in code (hashed) for later validation.

    Returns the inserted document (best-effort) or None if DB unavailable.
    """

    col = get_collection("checkin_codes")
    if col is None:
        return None

    now = ensure_utc(now or _utcnow())
    expires_at = now + timedelta(minutes=int(ttl_minutes))

    doc = {
        "kind": str(kind),
        "created_at": now,
        "expires_at": expires_at,
        "code_sha256": _sha256_hex(str(code)),
    }

    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def validate_checkin_code(
    *,
    code: str,
    kind: str = "attendance_submission",
    now: datetime | None = None,
) -> str:
    """Validate an attempted code against the most recently issued code.

    Returns one of:
    - success
    - expired_code (includes: was previously issued but replaced)
    - invalid_code

    Rationale: If a new code exists, older codes should be treated as expired
    (they were once valid but are no longer accepted).
    """

    col = get_collection("checkin_codes")
    if col is None:
        return "invalid_code"

    now = ensure_utc(now or _utcnow())
    attempted_hash = _sha256_hex(str(code))

    # Determine the most recently issued code for this kind.
    current = col.find_one({"kind": str(kind)}, sort=[("created_at", DESCENDING)])
    if not current:
        return "invalid_code"

    # If the attempted code was never issued, it's invalid.
    match = col.find_one(
        {"kind": str(kind), "code_sha256": attempted_hash},
        sort=[("created_at", DESCENDING)],
    )
    if not match:
        return "invalid_code"

    # If it's not the current code anymore, treat as expired.
    if match.get("_id") != current.get("_id"):
        return "expired_code"

    expires_at = current.get("expires_at")
    if isinstance(expires_at, datetime):
        expires_at = ensure_utc(expires_at)
        if now > expires_at:
            return "expired_code"

    return "success"
