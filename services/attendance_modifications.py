from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd
from bson import ObjectId

from services.commander_attendance import compute_upserts
from utils.attendance_status import (
    NO_RECORD_STATUS_LABEL,
    get_attendance_status_cell_style,
    get_attendance_status_label,
)
from utils.audit_log import log_attendance_modification
from utils.db import get_collection
from utils.db_schema_crud import (
    delete_attendance_record,
    get_attendance_record_by_event_cadet,
    get_cadets_by_ids,
    get_users_by_ids,
    get_waiver_by_attendance_record,
    upsert_attendance_record,
)
from utils.datetime_utils import ensure_utc
from utils.names import format_full_name
from utils.pagination import build_pagination_metadata, paginate_list


_AUDIT_SOURCE = "attendance_modification"
_ACTION_LABELS = {
    "applied": "Saved",
    "undo": "Undo",
    "redo": "Redo",
}


def _normalize_status(status: Any) -> str | None:
    normalized = str(status or "").strip().lower()
    return normalized or None


def _status_label(status: str | None) -> str:
    return get_attendance_status_label(status, default=NO_RECORD_STATUS_LABEL)


def _safe_object_id(value: str | ObjectId) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


def _record_operation(
    before_record: dict[str, Any] | None,
    after_record: dict[str, Any] | None,
) -> str:
    if before_record is None and after_record is not None:
        return "create"
    if before_record is not None and after_record is None:
        return "delete"
    return "update"


def _fmt_timestamp(value: Any) -> str:
    if not isinstance(value, datetime):
        return "Unknown"
    return ensure_utc(value).strftime("%Y-%m-%d %H:%M UTC")


def _audit_docs(query: dict[str, Any]) -> list[dict[str, Any]]:
    col = get_collection("audit_log")
    if col is None:
        return []

    cursor = col.find(query)
    if hasattr(cursor, "sort"):
        try:
            return list(cursor.sort("created_at", -1))
        except TypeError:
            pass

    docs = list(cursor)
    docs.sort(
        key=lambda doc: (
            doc.get("created_at") or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    return docs


def _paged_audit_docs(
    query: dict[str, Any],
    *,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    col = get_collection("audit_log")
    if col is None:
        return []

    cursor = col.find(query)
    if hasattr(cursor, "sort"):
        try:
            cursor = cursor.sort("created_at", -1)
            if skip > 0:
                cursor = cursor.skip(skip)
            if limit > 0:
                cursor = cursor.limit(limit)
            return list(cursor)
        except TypeError:
            pass

    docs = _audit_docs(query)
    return docs[skip : skip + limit]


def _pair_history_docs(event_id: ObjectId, cadet_id: ObjectId) -> list[dict[str, Any]]:
    return _audit_docs(
        {
            "source": _AUDIT_SOURCE,
            "event_id": event_id,
            "cadet_id": cadet_id,
        }
    )


def _latest_pair_history_doc(
    event_id: ObjectId, cadet_id: ObjectId
) -> dict[str, Any] | None:
    docs = _paged_audit_docs(
        {
            "source": _AUDIT_SOURCE,
            "event_id": event_id,
            "cadet_id": cadet_id,
        },
        skip=0,
        limit=1,
    )
    return docs[0] if docs else None


def _latest_visible_event_change_docs(event_id: str | ObjectId) -> list[dict[str, Any]]:
    docs = _audit_docs(
        {
            "source": _AUDIT_SOURCE,
            "event_id": ObjectId(event_id),
        }
    )

    visible_docs: list[dict[str, Any]] = []
    seen_cadet_ids: set[ObjectId] = set()
    for doc in docs:
        cadet_id = doc.get("cadet_id")
        if cadet_id is None or cadet_id in seen_cadet_ids:
            continue
        seen_cadet_ids.add(cadet_id)
        visible_docs.append(doc)
    return visible_docs


def _latest_visible_event_change_pipeline(
    event_id: str | ObjectId,
) -> list[dict[str, Any]]:
    return [
        {
            "$match": {
                "source": _AUDIT_SOURCE,
                "event_id": ObjectId(event_id),
            }
        },
        {"$sort": {"created_at": -1, "_id": -1}},
        {
            "$group": {
                "_id": "$cadet_id",
                "doc": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"created_at": -1, "_id": -1}},
    ]


def _hydrate_changes(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not docs:
        return []

    cadet_ids = [doc["cadet_id"] for doc in docs if doc.get("cadet_id") is not None]
    actor_ids = [doc["user_id"] for doc in docs if doc.get("user_id") is not None]

    cadets = get_cadets_by_ids(cadet_ids)
    cadet_by_id = {cadet["_id"]: cadet for cadet in cadets}

    cadet_user_ids = [
        cadet["user_id"] for cadet in cadets if cadet.get("user_id") is not None
    ]
    users = get_users_by_ids(cadet_user_ids + actor_ids)
    user_by_id = {user["_id"]: user for user in users}

    rows: list[dict[str, Any]] = []
    for doc in docs:
        metadata = doc.get("metadata") or {}
        cadet = cadet_by_id.get(doc.get("cadet_id"))
        cadet_user = user_by_id.get(cadet.get("user_id")) if cadet else None
        actor = user_by_id.get(doc.get("user_id"))

        cadet_name = format_full_name(cadet_user)
        if not cadet_name and cadet:
            first = str(cadet.get("first_name", "") or "").strip()
            last = str(cadet.get("last_name", "") or "").strip()
            cadet_name = f"{first} {last}".strip()
        if not cadet_name:
            cadet_name = "Unknown cadet"

        changed_by = format_full_name(actor, "Unknown user")
        from_status = _status_label(_normalize_status(metadata.get("old_status")))
        to_status = _status_label(_normalize_status(metadata.get("new_status")))
        action_key = str(doc.get("outcome", "applied")).strip().lower()

        rows.append(
            {
                "change_id": str(doc.get("_id", "")),
                "cadet_name": cadet_name,
                "changed_by": changed_by,
                "from_status": from_status,
                "to_status": to_status,
                "action": _ACTION_LABELS.get(action_key, action_key.title() or "Saved"),
                "timestamp": _fmt_timestamp(doc.get("created_at")),
            }
        )

    return rows


def _set_attendance_state(
    *,
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
    status: str | None,
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    before_record = get_attendance_record_by_event_cadet(event_id, cadet_id)

    if status is None:
        if before_record is not None:
            delete_attendance_record(before_record["_id"])
        return before_record, None

    upsert_attendance_record(
        event_id=event_id,
        cadet_id=cadet_id,
        status=status,
        recorded_by_user_id=recorded_by_user_id,
        recorded_by_roles=recorded_by_roles,
    )
    after_record = get_attendance_record_by_event_cadet(event_id, cadet_id)
    return before_record, after_record


def apply_bulk_attendance_changes(
    *,
    event_id: str | ObjectId,
    roster: list[dict[str, Any]],
    new_statuses: dict[str, str],
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None,
) -> dict[str, Any]:
    upserts = compute_upserts(roster, new_statuses)
    if not upserts:
        return {"ok": True, "changed_count": 0, "batch_id": None}

    entry_by_cadet = {str(entry["cadet"]["_id"]): entry for entry in roster}
    batch_id = uuid4().hex

    for op in upserts:
        cadet_id = op["cadet_id"]
        entry = entry_by_cadet[str(cadet_id)]
        before_record = entry.get("record")
        old_status = _normalize_status(entry.get("current_status"))
        new_status = _normalize_status(op.get("status"))

        _, after_record = _set_attendance_state(
            event_id=event_id,
            cadet_id=cadet_id,
            status=new_status,
            recorded_by_user_id=recorded_by_user_id,
            recorded_by_roles=recorded_by_roles,
        )

        log_attendance_modification(
            event_id=event_id,
            cadet_id=cadet_id,
            user_id=recorded_by_user_id,
            outcome="applied",
            old_status=old_status,
            new_status=new_status,
            metadata={
                "batch_id": batch_id,
                "record_operation": _record_operation(before_record, after_record),
                "old_record_id": str(before_record.get("_id", ""))
                if before_record
                else None,
                "new_record_id": str(after_record.get("_id", ""))
                if after_record
                else None,
                "recorded_by_roles": list(recorded_by_roles or []),
            },
        )

    return {"ok": True, "changed_count": len(upserts), "batch_id": batch_id}


def get_event_change_history(
    event_id: str | ObjectId,
    *,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    col = get_collection("audit_log")
    docs: list[dict[str, Any]] = []

    if col is not None and hasattr(col, "aggregate"):
        base_pipeline = _latest_visible_event_change_pipeline(event_id)
        count_docs = list(col.aggregate(base_pipeline + [{"$count": "total_count"}]))
        total_count = int(count_docs[0]["total_count"]) if count_docs else 0
        pagination = build_pagination_metadata(
            page=page,
            page_size=page_size,
            total_count=total_count,
        )
        docs = list(
            col.aggregate(
                base_pipeline
                + [
                    {"$skip": pagination["skip"]},
                    {"$limit": pagination["page_size"]},
                ]
            )
        )
    else:
        paginated = paginate_list(
            _latest_visible_event_change_docs(event_id),
            page=page,
            page_size=page_size,
        )
        pagination = {
            key: paginated[key]
            for key in ("page", "page_size", "total_count", "total_pages", "skip")
        }
        docs = list(paginated["items"])

    items = _hydrate_changes(docs)
    for doc, item in zip(docs, items):
        latest_doc = (
            doc
            if col is not None and hasattr(col, "aggregate")
            else _latest_pair_history_doc(doc["event_id"], doc["cadet_id"])
        )
        if latest_doc is not None:
            item.update(_selected_action_state(doc, latest_doc))

    return {
        "items": items,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_count": pagination["total_count"],
        "total_pages": pagination["total_pages"],
    }


def _selected_action_state(
    selected_doc: dict[str, Any],
    latest_doc: dict[str, Any],
) -> dict[str, Any]:
    selected_metadata = selected_doc.get("metadata") or {}
    latest_status = _normalize_status(selected_metadata.get("new_status"))
    restore_status = _normalize_status(selected_metadata.get("old_status"))
    current_record = get_attendance_record_by_event_cadet(
        selected_doc["event_id"],
        selected_doc["cadet_id"],
    )
    current_status = _normalize_status(
        current_record.get("status") if current_record else None
    )

    state = {
        "can_undo": False,
        "can_redo": False,
        "undo_target_label": _status_label(restore_status),
        "redo_target_label": _status_label(
            _normalize_status(selected_metadata.get("old_status"))
        ),
        "action_block_reason": "",
    }

    if selected_doc.get("_id") != latest_doc.get("_id"):
        state["action_block_reason"] = (
            "Only the latest change for this cadet can be undone or redone."
        )
        return state

    if current_status != latest_status:
        state["action_block_reason"] = (
            "Attendance changed after this audit entry was created."
        )
        return state

    outcome = str(selected_doc.get("outcome", "")).strip().lower()
    if outcome == "undo":
        state["can_redo"] = True
        state["redo_target_label"] = _status_label(
            _normalize_status(selected_metadata.get("old_status"))
        )
        return state

    if restore_status is None and current_record is not None:
        waiver = get_waiver_by_attendance_record(current_record["_id"])
        if waiver is not None:
            state["action_block_reason"] = (
                "This change cannot be undone to No Record because the attendance record "
                "has a waiver attached."
            )
            return state

    state["can_undo"] = True
    return state


def build_recent_changes_table(items: list[dict[str, Any]]):
    df = pd.DataFrame(
        [
            {
                "Timestamp": item["timestamp"],
                "Cadet": item["cadet_name"],
                "From": item["from_status"],
                "To": item["to_status"],
                "Changed By": item["changed_by"],
                "Action": item["action"],
                "Available": (
                    "Undo"
                    if item["can_undo"]
                    else "Redo"
                    if item["can_redo"]
                    else "Unavailable"
                ),
            }
            for item in items
        ]
    )

    styler = df.style
    if hasattr(styler, "map"):
        styler = styler.map(get_attendance_status_cell_style, subset=["From", "To"])
    else:
        styler = styler.applymap(
            get_attendance_status_cell_style,
            subset=["From", "To"],
        )
    return styler


def get_selected_change_id(selection: Any, items: list[dict[str, Any]]) -> str | None:
    if not selection:
        return None

    rows: list[int]
    if isinstance(selection, dict):
        rows = list(selection.get("selection", {}).get("rows", []))
    else:
        selection_data = getattr(selection, "selection", None)
        if selection_data is None:
            return None
        if isinstance(selection_data, dict):
            rows = list(selection_data.get("rows", []))
        else:
            rows = list(getattr(selection_data, "rows", []) or [])

    if not rows:
        return None

    selected_index = rows[0]
    if 0 <= selected_index < len(items):
        return items[selected_index]["change_id"]
    return None


def get_selected_change_item(
    selected_change_id: str | None,
    items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if selected_change_id is None:
        return None
    return next(
        (item for item in items if item["change_id"] == selected_change_id),
        None,
    )


def _apply_change_from_audit(
    *,
    change_doc: dict[str, Any],
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None,
    outcome: str,
    relation_field: str,
) -> tuple[bool, str]:
    history_docs = _pair_history_docs(change_doc["event_id"], change_doc["cadet_id"])
    if not history_docs or history_docs[0].get("_id") != change_doc.get("_id"):
        return False, "Only the latest change can be modified."

    metadata = change_doc.get("metadata") or {}
    current_record = get_attendance_record_by_event_cadet(
        change_doc["event_id"],
        change_doc["cadet_id"],
    )
    current_status = _normalize_status(
        current_record.get("status") if current_record else None
    )
    expected_current_status = _normalize_status(metadata.get("new_status"))
    target_status = _normalize_status(metadata.get("old_status"))

    if current_status != expected_current_status:
        return False, "Attendance changed after this audit entry was created."

    if target_status is None and current_record is not None:
        waiver = get_waiver_by_attendance_record(current_record["_id"])
        if waiver is not None:
            return (
                False,
                "This change cannot be undone to No Record because the attendance record has a waiver attached.",
            )

    before_record, after_record = _set_attendance_state(
        event_id=change_doc["event_id"],
        cadet_id=change_doc["cadet_id"],
        status=target_status,
        recorded_by_user_id=recorded_by_user_id,
        recorded_by_roles=recorded_by_roles,
    )

    log_attendance_modification(
        event_id=change_doc["event_id"],
        cadet_id=change_doc["cadet_id"],
        user_id=recorded_by_user_id,
        outcome=outcome,
        old_status=current_status,
        new_status=target_status,
        metadata={
            relation_field: str(change_doc["_id"]),
            "record_operation": _record_operation(before_record, after_record),
            "old_record_id": str(before_record.get("_id", ""))
            if before_record
            else None,
            "new_record_id": str(after_record.get("_id", "")) if after_record else None,
            "recorded_by_roles": list(recorded_by_roles or []),
        },
    )

    return True, "Attendance change updated."


def undo_change(
    change_id: str | ObjectId,
    *,
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None,
) -> tuple[bool, str]:
    oid = _safe_object_id(change_id)
    if oid is None:
        return False, "Could not find that attendance change."

    col = get_collection("audit_log")
    if col is None:
        return False, "Database unavailable. Could not undo attendance change."

    change_doc = col.find_one({"_id": oid, "source": _AUDIT_SOURCE})
    if change_doc is None:
        return False, "Could not find that attendance change."

    if str(change_doc.get("outcome", "")).strip().lower() == "undo":
        return False, "This change has already been undone."

    ok, message = _apply_change_from_audit(
        change_doc=change_doc,
        recorded_by_user_id=recorded_by_user_id,
        recorded_by_roles=recorded_by_roles,
        outcome="undo",
        relation_field="reverts_audit_id",
    )
    if not ok:
        return False, message
    return True, "Attendance change undone."


def redo_change(
    change_id: str | ObjectId,
    *,
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None,
) -> tuple[bool, str]:
    oid = _safe_object_id(change_id)
    if oid is None:
        return False, "Could not find that attendance change."

    col = get_collection("audit_log")
    if col is None:
        return False, "Database unavailable. Could not redo attendance change."

    change_doc = col.find_one({"_id": oid, "source": _AUDIT_SOURCE})
    if change_doc is None:
        return False, "Could not find that attendance change."

    if str(change_doc.get("outcome", "")).strip().lower() != "undo":
        return False, "Only the latest undo can be redone."

    ok, message = _apply_change_from_audit(
        change_doc=change_doc,
        recorded_by_user_id=recorded_by_user_id,
        recorded_by_roles=recorded_by_roles,
        outcome="redo",
        relation_field="redoes_audit_id",
    )
    if not ok:
        return False, message
    return True, "Attendance change redone."
