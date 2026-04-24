from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId

from utils.attendance_status import (
    NO_RECORD_STATUS_LABEL,
    get_attendance_status_label,
)
from utils.db import get_collection
from utils.db_schema_crud import get_users_by_ids, get_cadets_by_ids
from utils.pagination import build_pagination_metadata


_AUDIT_SOURCE_LABELS: dict[str, str] = {
    "user_management": "User Management",
    "event_management": "Event Management",
    "attendance_modification": "Attendance",
    "checkin": "Check-in",
    "waiver_review": "Waiver Review",
    "event_config": "Event Config",
    "flight_management": "Flight Management",
    "cadet_management": "Cadet Management",
    "event_codes": "Event Codes",
    "attendance_submission": "Attendance Submission",
}

_ACTION_LABELS: dict[str, str] = {
    "create": "Created",
    "update": "Updated",
    "disable": "Disabled",
    "enable": "Enabled",
    "archive": "Archived",
    "restore": "Restored",
    "delete": "Deleted",
    "approve": "Approved",
    "deny": "Denied",
    "assign": "Assigned",
    "unassign": "Unassigned",
    "applied": "Saved",
    "undo": "Undo",
    "redo": "Redo",
    "reset_password": "Reset Password",
    "generate_code": "Generated Code",
    "deactivate_code": "Deactivated Code",
    "submit_decision": "Decision Submitted",
}

_AUDIT_ACTIVITY_FILTERS: dict[str, dict[str, Any]] = {
    "Attendance changes": {"source": "attendance_modification"},
    "Attendance check-ins": {"source": {"$in": ["checkin", "attendance_submission"]}},
    "Events created or updated": {
        "source": "event_management",
        "action": {"$in": ["create", "update"]},
    },
    "Events archived or restored": {
        "source": "event_management",
        "action": {"$in": ["archive", "restore"]},
    },
    "Users created or updated": {
        "source": "user_management",
        "action": {"$in": ["create", "update"]},
    },
    "Users enabled or disabled": {
        "source": "user_management",
        "action": {"$in": ["enable", "disable"]},
    },
    "Password resets": {"source": "user_management", "action": "reset_password"},
    "Cadets updated": {"source": "cadet_management", "action": "update"},
    "Waivers approved or denied": {
        "source": "waiver_review",
        "action": {"$in": ["approve", "deny"]},
    },
    "Flight assignments": {
        "source": "flight_management",
        "action": {"$in": ["assign", "unassign"]},
    },
    "Event codes generated or deactivated": {
        "source": "event_codes",
        "action": {"$in": ["generate_code", "deactivate_code"]},
    },
    "Event schedule updated": {"source": "event_config", "action": "update"},
}

_DETAIL_METADATA_SKIP_KEYS = {
    "batch_id",
    "event_id",
    "new_record_id",
    "old_record_id",
    "old_status",
    "new_status",
    "recorded_by_roles",
    "redoes_audit_id",
    "reverts_audit_id",
    "temp_password",
    "waiver_id",
}

_ACTIVITY_LABELS: dict[tuple[str, str], str] = {
    ("attendance_modification", "applied"): "Saved Attendance",
    ("attendance_modification", "undo"): "Undid Attendance Change",
    ("attendance_modification", "redo"): "Redid Attendance Change",
    ("attendance_submission", "success"): "Submitted Attendance",
    ("checkin", "success"): "Successful Check-in",
    ("event_management", "create"): "Created Event",
    ("event_management", "update"): "Updated Event",
    ("event_management", "archive"): "Archived Event",
    ("event_management", "restore"): "Restored Event",
    ("event_config", "update"): "Updated Event Schedule",
    ("event_codes", "generate_code"): "Generated Event Code",
    ("event_codes", "deactivate_code"): "Deactivated Event Code",
    ("user_management", "create"): "Created User",
    ("user_management", "update"): "Updated User",
    ("user_management", "enable"): "Enabled User",
    ("user_management", "disable"): "Disabled User",
    ("user_management", "reset_password"): "Reset User Password",
    ("cadet_management", "update"): "Updated Cadet",
    ("waiver_review", "approve"): "Approved Waiver",
    ("waiver_review", "deny"): "Denied Waiver",
    ("flight_management", "assign"): "Assigned Flight",
    ("flight_management", "unassign"): "Unassigned Flight",
}

_SOURCE_NOUNS: dict[str, str] = {
    "attendance_modification": "Attendance",
    "attendance_submission": "Attendance",
    "cadet_management": "Cadet",
    "checkin": "Check-in",
    "event_codes": "Event Code",
    "event_config": "Event Schedule",
    "event_management": "Event",
    "flight_management": "Flight",
    "user_management": "User",
    "waiver_review": "Waiver",
}


def _normalize_status(status: Any) -> str | None:
    normalized = str(status or "").strip().lower()
    return normalized or None


def _status_label(status: Any) -> str:
    return get_attendance_status_label(
        _normalize_status(status),
        default=NO_RECORD_STATUS_LABEL,
    )


def _humanize_key(key: Any) -> str:
    return str(key).replace("_", " ").strip().title()


def _format_detail_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return "; ".join(
            formatted for item in value if (formatted := _format_detail_value(item))
        )
    if isinstance(value, dict):
        name = value.get("cadet_name") or value.get("name") or value.get("email")
        if name:
            return str(name)

        parts = []
        for key, nested_value in value.items():
            key_text = str(key)
            if key_text.endswith("_id") or nested_value in (None, "", [], {}):
                continue
            formatted = _format_detail_value(nested_value)
            if formatted:
                parts.append(f"{_humanize_key(key_text)}: {formatted}")
        return "; ".join(parts)
    return str(value)


def _full_name(person: dict[str, Any] | None, *, fallback: str = "") -> str:
    if not person:
        return fallback
    first = str(person.get("first_name", "") or "").strip()
    last = str(person.get("last_name", "") or "").strip()
    return f"{first} {last}".strip() or str(person.get("email", fallback) or fallback)


def _detail_row(
    detail: str,
    *,
    value: Any = "",
    before: Any = "",
    after: Any = "",
) -> dict[str, str]:
    return {
        "Detail": detail,
        "Before": _format_detail_value(before),
        "After": _format_detail_value(after),
        "Value": _format_detail_value(value),
    }


def _metadata_detail_rows(metadata: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for key, value in metadata.items():
        key_text = str(key)
        if (
            key_text in _DETAIL_METADATA_SKIP_KEYS
            or key_text.endswith("_id")
            or value in (None, "", [], {})
        ):
            continue

        formatted = _format_detail_value(value)
        if formatted:
            rows.append(_detail_row(_humanize_key(key_text), value=formatted))
    return rows


def _attendance_summary(action: str, metadata: dict[str, Any]) -> str:
    if "old_status" not in metadata and "new_status" not in metadata:
        action_label = _ACTION_LABELS.get(action, action.title() or "Unknown")
        return action_label

    old_status = _status_label(metadata.get("old_status"))
    new_status = _status_label(metadata.get("new_status"))

    if action == "undo":
        return f"Undo from {old_status} back to {new_status}"
    if action == "redo":
        return f"Redo from {old_status} to {new_status}"
    return f"From {old_status} to {new_status}"


def _audit_activity_label(
    source: str,
    action: str,
    action_label: str,
    source_label: str,
) -> str:
    mapped = _ACTIVITY_LABELS.get((source, action))
    if mapped:
        return mapped
    return f"{action_label} {_SOURCE_NOUNS.get(source, source_label)}"


def get_audit_activity_options() -> list[str]:
    """Return human-readable audit activity filter options."""
    return list(_AUDIT_ACTIVITY_FILTERS)


def _activity_filter_query(activities: list[str] | None) -> dict[str, Any]:
    if not activities:
        return {}

    predicates = [
        dict(_AUDIT_ACTIVITY_FILTERS[activity])
        for activity in activities
        if activity in _AUDIT_ACTIVITY_FILTERS
    ]
    if not predicates:
        return {}
    if len(predicates) == 1:
        return predicates[0]
    return {"$or": predicates}


def _combine_query_clauses(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    clauses = [clause for clause in clauses if clause]
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _safe_object_id(value: Any) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def _person_search_query(search: str) -> dict[str, Any]:
    escaped = re.escape(search.strip())
    if not escaped:
        return {}

    predicates = [
        {"email": {"$regex": escaped, "$options": "i"}},
        {"first_name": {"$regex": escaped, "$options": "i"}},
        {"last_name": {"$regex": escaped, "$options": "i"}},
        {"name": {"$regex": escaped, "$options": "i"}},
    ]
    tokens = search.split(maxsplit=1)
    if len(tokens) == 2:
        predicates.append(
            {
                "$and": [
                    {"first_name": {"$regex": re.escape(tokens[0]), "$options": "i"}},
                    {"last_name": {"$regex": re.escape(tokens[1]), "$options": "i"}},
                ]
            }
        )
    return {"$or": predicates}


def _ids_for_person_search(collection_name: str, search: str) -> list[ObjectId]:
    col = get_collection(collection_name)
    query = _person_search_query(search)
    if col is None or not query:
        return []

    try:
        return [doc["_id"] for doc in col.find(query, {"_id": 1}) if doc.get("_id")]
    except Exception:
        return []


def _actor_user_ids_for_search(search: str) -> list[ObjectId]:
    return _ids_for_person_search("users", search)


def _actor_search_query(actor_search: str | None) -> dict[str, Any]:
    if not actor_search:
        return {}

    search = actor_search.strip()
    if not search:
        return {}

    escaped = re.escape(search)
    predicates: list[dict[str, Any]] = [
        {"actor_email": {"$regex": escaped, "$options": "i"}},
        {"actor_user_id_raw": {"$regex": escaped, "$options": "i"}},
        {"user_id_raw": {"$regex": escaped, "$options": "i"}},
    ]

    actor_ids = _actor_user_ids_for_search(search)
    exact_id = _safe_object_id(search)
    if exact_id is not None:
        actor_ids.append(exact_id)

    if actor_ids:
        predicates.extend(
            [
                {"actor_user_id": {"$in": actor_ids}},
                {"user_id": {"$in": actor_ids}},
            ]
        )

    return {"$or": predicates}


def _cadet_ids_for_search(search: str) -> list[ObjectId]:
    return _ids_for_person_search("cadets", search)


def _event_ids_for_search(search: str) -> list[ObjectId]:
    events_col = get_collection("events")
    if events_col is None:
        return []

    escaped = re.escape(search.strip())
    if not escaped:
        return []

    try:
        return [
            event["_id"]
            for event in events_col.find(
                {"event_name": {"$regex": escaped, "$options": "i"}},
                {"_id": 1},
            )
            if event.get("_id")
        ]
    except Exception:
        return []


def _target_search_query(target_search: str | None) -> dict[str, Any]:
    if not target_search:
        return {}

    search = target_search.strip()
    if not search:
        return {}

    escaped = re.escape(search)
    predicates: list[dict[str, Any]] = [
        {"target_label": {"$regex": escaped, "$options": "i"}},
        {"target_id": {"$regex": escaped, "$options": "i"}},
    ]

    cadet_ids = _cadet_ids_for_search(search)
    event_ids = _event_ids_for_search(search)
    exact_id = _safe_object_id(search)
    if exact_id is not None:
        cadet_ids.append(exact_id)
        event_ids.append(exact_id)

    if cadet_ids:
        predicates.extend(
            [
                {"cadet_id": {"$in": cadet_ids}},
                {"target_collection": "cadets", "target_id": {"$in": cadet_ids}},
            ]
        )
    if event_ids:
        predicates.extend(
            [
                {"event_id": {"$in": event_ids}},
                {"target_collection": "events", "target_id": {"$in": event_ids}},
            ]
        )

    return {"$or": predicates}


def build_audit_overview_row(row: dict[str, Any]) -> dict[str, str]:
    """Build the selected-entry overview using the same shape as the log table."""
    overview = {
        "Timestamp": _format_detail_value(row.get("timestamp")) or "Unknown",
        "Actor": _format_detail_value(row.get("actor_name")),
    }
    if row.get("actor_email"):
        overview["Actor Email"] = _format_detail_value(row["actor_email"])

    overview.update(
        {
            "Activity": _format_detail_value(row.get("activity_label")),
            "Target": _format_detail_value(row.get("target_label")),
        }
    )
    if row.get("cadet_label"):
        overview["Cadet"] = _format_detail_value(row["cadet_label"])
    overview["Summary"] = _format_detail_value(row.get("summary"))
    return overview


def build_audit_table_row(
    row: dict[str, Any],
    *,
    include_audit_id: bool = False,
    formatted_timestamp: bool = True,
) -> dict[str, Any]:
    """Build a row for the audit table/export surfaces."""
    table_row = {
        "Timestamp": (
            _format_detail_value(row.get("timestamp")) or "Unknown"
            if formatted_timestamp
            else row.get("timestamp")
        ),
        "Actor": row["actor_name"],
        "Activity": row["activity_label"],
        "Target": row["target_label"],
        "Cadet": row["cadet_label"],
        "Summary": row["summary"],
    }
    if include_audit_id:
        table_row["_audit_id"] = row["audit_id"]
    return table_row


def build_audit_detail_rows(row: dict[str, Any]) -> list[dict[str, str]]:
    """Build user-facing before/after and extra detail rows for any audit row."""
    raw = row.get("raw_doc") or {}
    metadata = raw.get("metadata") or {}
    rows = []

    if row.get("source") == "attendance_modification" and (
        "old_status" in metadata or "new_status" in metadata
    ):
        rows.append(
            _detail_row(
                "Attendance Status",
                before=_status_label(metadata.get("old_status")),
                after=_status_label(metadata.get("new_status")),
            )
        )

    changes = raw.get("changes") or {}
    for field, values in changes.items():
        if not isinstance(values, dict):
            continue
        rows.append(
            _detail_row(
                _humanize_key(field),
                before=values.get("from"),
                after=values.get("to"),
            )
        )

    rows.extend(_metadata_detail_rows(metadata))
    return [row for row in rows if row["Value"] or row["Before"] or row["After"]]


def get_audit_detail_columns(detail_rows: list[dict[str, str]]) -> list[str]:
    columns = ["Detail"]
    columns.extend(
        column
        for column in ("Before", "After", "Value")
        if any(row.get(column) for row in detail_rows)
    )
    return columns


def _normalize_audit_entry(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert any audit doc shape into a common normalized row."""
    source = str(doc.get("source", "unknown")).strip().lower()

    # Action resolution
    if "action" in doc:
        action = str(doc["action"]).strip().lower()
    elif "outcome" in doc:
        action = str(doc["outcome"]).strip().lower()
    else:
        action = "unknown"

    # Actor resolution
    actor_id = doc.get("actor_user_id") or doc.get("user_id")
    actor_email = str(doc.get("actor_email", "") or "").strip()

    # Target resolution
    if "target_collection" in doc and "target_id" in doc:
        target_type = str(doc["target_collection"])
        target_id = doc["target_id"]
        target_label = str(doc.get("target_label", "Unknown"))
    elif source == "attendance_modification":
        target_type = "attendance"
        target_id = doc.get("event_id")
        event_id = doc.get("event_id")
        target_label = f"Event {event_id}" if event_id else "Attendance"
    elif source in ("checkin", "attendance_submission"):
        target_type = "checkin"
        target_id = doc.get("event_id")
        event_id = doc.get("event_id")
        target_label = f"Event {event_id}" if event_id else "Check-in"
    else:
        target_type = "unknown"
        target_id = None
        target_label = "Unknown"

    # Summary
    action_label = _ACTION_LABELS.get(action, action.title() or "Unknown")
    source_label = _AUDIT_SOURCE_LABELS.get(source, source.title() or "Unknown")
    activity_label = _audit_activity_label(source, action, action_label, source_label)
    summary = activity_label

    return {
        "audit_id": str(doc.get("_id", "")),
        "timestamp": doc.get("created_at"),
        "source": source,
        "source_label": source_label,
        "action": action,
        "action_label": action_label,
        "activity_label": activity_label,
        "actor_id": actor_id,
        "actor_email": actor_email,
        "target_type": target_type,
        "target_id": target_id,
        "target_label": target_label,
        "cadet_label": "",
        "summary": summary,
        "has_details": bool(
            doc.get("changes")
            or doc.get("before")
            or doc.get("after")
            or doc.get("metadata")
        ),
        "raw_doc": doc,
    }


def _collect_ids_for_hydration(rows: list[dict[str, Any]]) -> dict[str, set[Any]]:
    user_ids: set[Any] = set()
    event_ids: set[Any] = set()
    cadet_ids: set[Any] = set()

    for row in rows:
        raw = row["raw_doc"]
        # Actor IDs
        actor_id = raw.get("actor_user_id") or raw.get("user_id")
        if actor_id is not None:
            user_ids.add(actor_id)
        # Target user IDs
        if raw.get("target_collection") == "users" and raw.get("target_id") is not None:
            user_ids.add(raw["target_id"])
        # Event IDs (legacy and generic)
        event_id = raw.get("event_id")
        if event_id is not None:
            event_ids.add(event_id)
        # Cadet IDs (legacy)
        cadet_id = raw.get("cadet_id")
        if cadet_id is not None:
            cadet_ids.add(cadet_id)

    return {"user_ids": user_ids, "event_ids": event_ids, "cadet_ids": cadet_ids}


def _hydrate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch-fetch names and enrich rows in-place."""
    if not rows:
        return rows

    ids = _collect_ids_for_hydration(rows)

    # Fetch users
    user_by_id: dict[Any, dict[str, Any]] = {}
    if ids["user_ids"]:
        for user in get_users_by_ids(list(ids["user_ids"])):
            if user.get("_id") is not None:
                user_by_id[user["_id"]] = user

    # Fetch events
    event_by_id: dict[Any, dict[str, Any]] = {}
    if ids["event_ids"]:
        events_col = get_collection("events")
        if events_col is not None:
            object_ids = []
            for eid in ids["event_ids"]:
                try:
                    object_ids.append(ObjectId(eid))
                except Exception:
                    object_ids.append(eid)
            cursor = events_col.find({"_id": {"$in": object_ids}}, {"event_name": 1})
            for event in cursor:
                if event.get("_id") is not None:
                    event_by_id[event["_id"]] = event

    # Fetch cadets
    cadet_by_id: dict[Any, dict[str, Any]] = {}
    if ids["cadet_ids"]:
        for cadet in get_cadets_by_ids(list(ids["cadet_ids"])):
            if cadet.get("_id") is not None:
                cadet_by_id[cadet["_id"]] = cadet

    # Enrich rows
    for row in rows:
        raw = row["raw_doc"]
        actor_id = raw.get("actor_user_id") or raw.get("user_id")
        row["actor_name"] = _full_name(
            user_by_id.get(actor_id),
            fallback=row["actor_email"] or "System",
        )

        # Enhance target label for legacy entries
        if row["source"] in (
            "attendance_modification",
            "checkin",
            "attendance_submission",
        ):
            event_id = raw.get("event_id")
            event = event_by_id.get(event_id) if event_id else None
            cadet_id = raw.get("cadet_id")
            cadet = cadet_by_id.get(cadet_id) if cadet_id else None

            event_name = (
                event.get("event_name", "Unknown Event") if event else "Unknown Event"
            )
            cadet_name = _full_name(cadet, fallback="Unknown Cadet")

            if row["source"] == "attendance_modification":
                row["target_label"] = event_name
                row["cadet_label"] = cadet_name
                row["summary"] = _attendance_summary(
                    row["action"],
                    raw.get("metadata") or {},
                )
            else:
                row["target_label"] = event_name
                row["summary"] = row["activity_label"]
        elif row["target_type"] == "users" and row["target_id"] is not None:
            name = _full_name(user_by_id.get(row["target_id"]), fallback="")
            if name:
                row["target_label"] = name
                row["summary"] = row["activity_label"]

    return rows


def _build_mongo_query(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    activities: list[str] | None = None,
    actor_search: str | None = None,
    target_search: str | None = None,
) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []

    if start_date is not None or end_date is not None:
        date_range: dict[str, Any] = {}
        if start_date is not None:
            date_range["$gte"] = start_date
        if end_date is not None:
            date_range["$lte"] = end_date
        clauses.append({"created_at": date_range})

    clauses.append(_activity_filter_query(activities))

    clauses.append(_actor_search_query(actor_search))

    clauses.append(_target_search_query(target_search))

    return _combine_query_clauses(clauses)


def query_audit_log(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    activities: list[str] | None = None,
    actor_search: str | None = None,
    target_search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Query and paginate audit log entries with hydrated names."""
    col = get_collection("audit_log")
    if col is None:
        return {
            "items": [],
            **build_pagination_metadata(page=page, page_size=page_size, total_count=0),
        }

    query = _build_mongo_query(
        start_date=start_date,
        end_date=end_date,
        activities=activities,
        actor_search=actor_search,
        target_search=target_search,
    )

    # Count
    try:
        total_count = int(col.count_documents(query))
    except Exception:
        total_count = 0

    pagination = build_pagination_metadata(
        page=page,
        page_size=page_size,
        total_count=total_count,
    )

    # Fetch page
    cursor = col.find(query).sort("created_at", -1)
    if pagination["skip"] > 0:
        cursor = cursor.skip(pagination["skip"])
    if pagination["page_size"] > 0:
        cursor = cursor.limit(pagination["page_size"])

    docs = list(cursor)
    rows = [_normalize_audit_entry(doc) for doc in docs]
    rows = _hydrate_rows(rows)

    return {
        "items": rows,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_count": pagination["total_count"],
        "total_pages": pagination["total_pages"],
        "skip": pagination["skip"],
    }


def export_audit_log_to_df(
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    activities: list[str] | None = None,
    actor_search: str | None = None,
    target_search: str | None = None,
) -> Any:
    """Return all matching audit rows as a pandas DataFrame (no pagination)."""
    try:
        import pandas as pd
    except ImportError:
        return None

    col = get_collection("audit_log")
    if col is None:
        return pd.DataFrame()

    query = _build_mongo_query(
        start_date=start_date,
        end_date=end_date,
        activities=activities,
        actor_search=actor_search,
        target_search=target_search,
    )

    docs = list(col.find(query).sort("created_at", -1))
    if not docs:
        return pd.DataFrame()

    rows = [_normalize_audit_entry(doc) for doc in docs]
    rows = _hydrate_rows(rows)

    return pd.DataFrame(
        [build_audit_table_row(row, formatted_timestamp=False) for row in rows]
    )
