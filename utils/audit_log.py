from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.results import InsertOneResult

from utils.checkin_codes import _sha256_hex, _utcnow
from utils.db import get_collection


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
