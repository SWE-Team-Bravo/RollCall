from __future__ import annotations
from datetime import datetime
import re

from bson import ObjectId
import pandas as pd

from utils.db import get_collection
from utils.db_schema_crud import (
    create_waiver_approval,
    get_all_flights,
    get_all_waivers,
    get_attendance_record_by_id,
    get_cadet_by_id,
    get_event_by_id,
    get_flight_by_id,
    get_user_by_id,
    update_waiver,
)

from utils.names import format_full_name
from utils.pagination import build_pagination_metadata, paginate_list
from utils.waiver_email import send_waiver_decision_email


def _fmt_date(dt: object) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return "Unknown date"


def get_flight_options() -> list[str]:
    flights = get_all_flights()
    return ["All flights"] + [f.get("name", "Unnamed flight") for f in flights]


def get_waivers(
    status_filter: str, viewer_roles: list[str] | None = None
) -> list[dict]:
    waivers = get_all_waivers()
    if status_filter != "all":
        waivers = [
            w for w in waivers if (w.get("status") or "").lower() == status_filter
        ]

    roles = set(viewer_roles or [])
    if not (roles & {"admin", "cadre"}):
        waivers = [w for w in waivers if not w.get("cadre_only", False)]

    waivers.sort(key=lambda w: w.get("created_at") or datetime.min, reverse=True)
    return waivers


def _waiver_review_match_stage(
    status_filter: str,
    viewer_roles: list[str] | None = None,
) -> dict:
    match_stage: dict[str, object] = {}
    if status_filter != "all":
        match_stage["status"] = status_filter

    roles = set(viewer_roles or [])
    if not (roles & {"admin", "cadre"}):
        match_stage["cadre_only"] = {"$ne": True}

    return match_stage


def _waiver_review_base_pipeline(
    *,
    status_filter: str,
    flight_filter: str,
    cadet_search: str,
    viewer_roles: list[str] | None,
) -> list[dict]:
    search_regex = re.escape(cadet_search.strip()) if cadet_search.strip() else ""
    pipeline: list[dict] = []
    match_stage = _waiver_review_match_stage(status_filter, viewer_roles)
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend(
        [
            {
                "$lookup": {
                    "from": "attendance_records",
                    "localField": "attendance_record_id",
                    "foreignField": "_id",
                    "as": "attendance_record",
                }
            },
            {"$unwind": "$attendance_record"},
            {
                "$lookup": {
                    "from": "cadets",
                    "localField": "attendance_record.cadet_id",
                    "foreignField": "_id",
                    "as": "cadet",
                }
            },
            {"$unwind": "$cadet"},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "cadet.user_id",
                    "foreignField": "_id",
                    "as": "cadet_user",
                }
            },
            {
                "$unwind": {
                    "path": "$cadet_user",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "flights",
                    "localField": "cadet.flight_id",
                    "foreignField": "_id",
                    "as": "flight",
                }
            },
            {
                "$unwind": {
                    "path": "$flight",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "events",
                    "localField": "attendance_record.event_id",
                    "foreignField": "_id",
                    "as": "event",
                }
            },
            {
                "$unwind": {
                    "path": "$event",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$addFields": {
                    "cadet_name_search": {
                        "$trim": {
                            "input": {
                                "$concat": [
                                    {"$ifNull": ["$cadet_user.first_name", "$cadet.first_name"]},
                                    " ",
                                    {"$ifNull": ["$cadet_user.last_name", "$cadet.last_name"]},
                                ]
                            }
                        }
                    },
                    "cadet_email_search": {
                        "$ifNull": ["$cadet_user.email", "$cadet.email"]
                    },
                }
            },
        ]
    )

    if flight_filter != "All flights":
        pipeline.append({"$match": {"flight.name": flight_filter}})

    if search_regex:
        pipeline.append(
            {
                "$match": {
                    "$or": [
                        {"cadet_name_search": {"$regex": search_regex, "$options": "i"}},
                        {"cadet_email_search": {"$regex": search_regex, "$options": "i"}},
                    ]
                }
            }
        )

    return pipeline


def _waiver_review_rows_from_docs(docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in docs:
        cadet_user = doc.get("cadet_user") or {}
        cadet = doc.get("cadet") or {}
        event = doc.get("event") or {}
        flight = doc.get("flight") or {}

        cadet_name = format_full_name(cadet_user)
        if not cadet_name:
            first = str(cadet.get("first_name", "") or "").strip()
            last = str(cadet.get("last_name", "") or "").strip()
            cadet_name = f"{first} {last}".strip() or "Unknown cadet"

        rows.append(
            {
                "waiver_id": doc.get("_id"),
                "waiver_status": str(doc.get("status") or "pending").lower(),
                "waiver_type": doc.get("waiver_type") or "non-medical",
                "attachments": doc.get("attachments") or [],
                "reason": doc.get("reason", ""),
                "cadet_name": cadet_name,
                "cadet_email": str(cadet_user.get("email") or cadet.get("email") or ""),
                "flight_name": str(flight.get("name") or "Unassigned"),
                "event_name": str(event.get("event_name") or "Unknown event"),
                "event_date": _fmt_date(event.get("start_date")),
                "event_type": (event.get("event_type") or "") or "unknown",
                "cadre_only": bool(doc.get("cadre_only", False)),
            }
        )
    return rows


def _fallback_waiver_review_rows(
    *,
    status_filter: str,
    flight_filter: str,
    cadet_search: str,
    viewer_roles: list[str] | None,
) -> list[dict]:
    rows: list[dict] = []
    search_value = cadet_search.strip().lower()

    for waiver in get_waivers(status_filter, viewer_roles):
        waiver_id = waiver.get("_id")
        if waiver_id is None:
            continue

        ctx = get_waiver_context(waiver)
        if ctx is None:
            continue

        if flight_filter != "All flights" and ctx["flight_name"] != flight_filter:
            continue

        if search_value:
            haystack = f"{ctx['cadet_name']} {ctx['cadet_email']}".lower()
            if search_value not in haystack:
                continue

        rows.append(
            {
                "waiver_id": waiver_id,
                "waiver_status": (waiver.get("status") or "pending").lower(),
                "waiver_type": ctx["waiver_type"],
                "attachments": ctx["attachments"],
                "reason": waiver.get("reason", ""),
                "cadet_name": ctx["cadet_name"],
                "cadet_email": ctx["cadet_email"],
                "flight_name": ctx["flight_name"],
                "event_name": ctx["event_name"],
                "event_date": ctx["event_date"],
                "event_type": ctx["event_type"],
                "cadre_only": ctx["cadre_only"],
            }
        )

    return rows


def get_waiver_review_rows(
    *,
    status_filter: str,
    flight_filter: str,
    cadet_search: str,
    viewer_roles: list[str] | None = None,
) -> list[dict]:
    col = get_collection("waivers")
    if col is None or not hasattr(col, "aggregate"):
        return _fallback_waiver_review_rows(
            status_filter=status_filter,
            flight_filter=flight_filter,
            cadet_search=cadet_search,
            viewer_roles=viewer_roles,
        )

    pipeline = _waiver_review_base_pipeline(
        status_filter=status_filter,
        flight_filter=flight_filter,
        cadet_search=cadet_search,
        viewer_roles=viewer_roles,
    )
    docs = list(col.aggregate(pipeline + [{"$sort": {"created_at": -1, "_id": -1}}]))
    return _waiver_review_rows_from_docs(docs)


def get_paginated_waiver_review_rows(
    *,
    status_filter: str,
    flight_filter: str,
    cadet_search: str,
    viewer_roles: list[str] | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, object]:
    col = get_collection("waivers")
    if col is None or not hasattr(col, "aggregate"):
        paginated = paginate_list(
            get_waiver_review_rows(
                status_filter=status_filter,
                flight_filter=flight_filter,
                cadet_search=cadet_search,
                viewer_roles=viewer_roles,
            ),
            page=page,
            page_size=page_size,
        )
        return paginated

    base_pipeline = _waiver_review_base_pipeline(
        status_filter=status_filter,
        flight_filter=flight_filter,
        cadet_search=cadet_search,
        viewer_roles=viewer_roles,
    )
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
                {"$sort": {"created_at": -1, "_id": -1}},
                {"$skip": pagination["skip"]},
                {"$limit": pagination["page_size"]},
            ]
        )
    )
    return {**pagination, "items": _waiver_review_rows_from_docs(docs)}


def get_waiver_context(waiver: dict) -> dict | None:
    """
    For a single waiver, fetch and return all related data.
    Returns None if any required data is missing.
    """
    attendance_record_id = waiver.get("attendance_record_id")
    if attendance_record_id is None:
        return None

    record = get_attendance_record_by_id(attendance_record_id)
    if record is None:
        return None

    event = None
    event_id = record.get("event_id")
    if event_id is not None:
        event = get_event_by_id(event_id)

    cadet = None
    cadet_id = record.get("cadet_id")
    if cadet_id is not None:
        cadet = get_cadet_by_id(cadet_id)

    user = None
    if cadet is not None:
        user_id = cadet.get("user_id")
        if user_id is not None:
            user = get_user_by_id(user_id)

    flight_name = "Unassigned"
    if cadet is not None:
        cadet_flight_id = cadet.get("flight_id")
        if cadet_flight_id is not None:
            flight = get_flight_by_id(cadet_flight_id)
            if flight:
                flight_name = flight.get("name", "Unassigned")

    cadet_name = format_full_name(user, "Unknown cadet")

    return {
        "cadet_name": cadet_name,
        "cadet_email": user.get("email") if user else "",
        "flight_name": flight_name,
        "event_name": event.get("event_name") if event else "Unknown event",
        "event_date": _fmt_date(event.get("start_date") if event else None),
        "event_type": (event.get("event_type") if event else "") or "unknown",
        "waiver_type": waiver.get("waiver_type") or "non-medical",
        "attachments": waiver.get("attachments") or [],
        "cadre_only": bool(waiver.get("cadre_only", False)),
    }


def submit_decision(
    waiver_id: str | ObjectId,
    approver_id: str | ObjectId,
    decision: str,
    comments: str,
    cadet_email: str,
    event_name: str,
    event_date: str,
) -> tuple[bool, str]:
    new_status = "approved" if decision == "Approve" else "denied"
    upd = update_waiver(waiver_id, {"status": new_status})
    if upd is None:
        return False, "Failed to update waiver status."

    appr = create_waiver_approval(
        waiver_id=waiver_id,
        approver_id=approver_id,
        decision=new_status,
        comments=comments or "Approved.",
    )
    if appr is None:
        return False, "Failed to create waiver approval record."

    if cadet_email:
        send_waiver_decision_email(
            waiver_id=str(waiver_id),
            to_email=cadet_email,
            event_name=event_name or "Unknown event",
            event_date=event_date,
            status=new_status,
            comments=comments or "Approved.",
        )

    return True, ""


def get_waiver_export_df(rows: list[dict]) -> pd.DataFrame | str:
    if not rows:
        return "No waivers found."
    return pd.DataFrame(
        [
            {
                "Cadet": r["cadet_name"],
                "Email": r["cadet_email"],
                "Flight": r["flight_name"],
                "Event": r["event_name"],
                "Date": r["event_date"],
                "Status": r["waiver_status"],
                "Type": r.get("waiver_type", "non-medical"),
                "Reason": r["reason"],
            }
            for r in rows
        ]
    )
