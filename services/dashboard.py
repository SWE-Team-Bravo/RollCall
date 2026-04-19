from datetime import datetime
from typing import Any
import pandas as pd

from utils.db import get_collection, get_db
from utils.names import format_full_name


def normalize_status(status: str | None) -> str:
    """Normalize a raw attendance status string to P/A/E."""
    if not status:
        return "A"
    s = status.strip().lower()
    if s == "present":
        return "P"
    if s == "absent":
        return "A"
    if s in ("excused", "waived"):
        return "E"
    return "A"


def event_sort_key(e: dict) -> Any:
    sd = e.get("start_date")
    return sd if isinstance(sd, datetime) else str(sd or "")


def format_event_row_label(event: dict[str, Any]) -> str:
    """Format an event document into a display label: 'YYYY-MM-DD — Event Name'."""
    sd = event.get("start_date")
    if isinstance(sd, datetime):
        date_str = sd.strftime("%Y-%m-%d")
    else:
        date_str = str(sd)[:10] if sd else "Unknown date"
    name = event.get("event_name") or event.get("name") or ""
    return f"{date_str} — {name}" if name else date_str


def build_attendance_grid(
    cadet_docs: list[dict],
    user_docs: list[dict],
    event_docs: list[dict],
    record_docs: list[dict],
) -> tuple[list[str], list[str], list[list[str]]]:
    """Build the attendance grid data for the dashboard.

    Returns:
        (event_row_labels, cadet_name_columns, grid_rows)
        where grid_rows[i][j] is the P/A/E status for event i and cadet j.
    """
    name_by_user_id = {
        u["_id"]: format_full_name(u, "Unknown")
        for u in user_docs
    }

    cadet_name_by_id = {
        c["_id"]: name_by_user_id.get(c.get("user_id"), "Unknown") for c in cadet_docs
    }

    cadet_pairs = sorted(cadet_name_by_id.items(), key=lambda x: x[1].lower())
    cadet_ids_sorted = [cid for cid, _ in cadet_pairs]
    cadet_names_sorted = [nm for _, nm in cadet_pairs]

    event_docs_sorted = sorted(event_docs, key=event_sort_key, reverse=True)
    event_ids_sorted = [e["_id"] for e in event_docs_sorted]
    event_row_labels = [format_event_row_label(e) for e in event_docs_sorted]

    status_by_pair: dict[tuple, str] = {}
    for r in record_docs:
        key = (r.get("event_id"), r.get("cadet_id"))
        status_by_pair[key] = normalize_status(r.get("status"))

    grid_rows: list[list[str]] = []
    for ev_id in event_ids_sorted:
        row = [status_by_pair.get((ev_id, cid), "A") for cid in cadet_ids_sorted]
        grid_rows.append(row)

    return event_row_labels, cadet_names_sorted, grid_rows


def get_data() -> tuple[list[dict], list[dict], list[dict], list[dict]] | None:
    db = get_db()
    if db is None:
        return None

    users_col = get_collection("users")
    cadets_col = get_collection("cadets")
    events_col = get_collection("events")
    attendance_col = get_collection("attendance_records")

    if any(x is None for x in (users_col, cadets_col, events_col, attendance_col)):
        return None

    assert users_col is not None
    assert cadets_col is not None
    assert events_col is not None
    assert attendance_col is not None

    cadet_docs = list(cadets_col.find({}, {"_id": 1, "user_id": 1}))
    if not cadet_docs:
        cadet_docs = []

    user_ids = [c["user_id"] for c in cadet_docs if "user_id" in c]
    user_docs = list(
        users_col.find(
            {"_id": {"$in": user_ids}}, {"_id": 1, "first_name": 1, "last_name": 1}
        )
    )

    event_docs = list(events_col.find({}, {"_id": 1, "start_date": 1, "event_name": 1}))
    if not event_docs:
        event_docs = []

    event_ids = [e["_id"] for e in event_docs]
    record_docs = list(
        attendance_col.find(
            {"event_id": {"$in": event_ids}},
            {"_id": 0, "event_id": 1, "cadet_id": 1, "status": 1},
        )
    )
    return cadet_docs, user_docs, event_docs, record_docs


def get_df() -> pd.DataFrame | str:
    data = get_data()

    if data is None:
        return "Database is unavailable."
    cadet_docs, user_docs, event_docs, record_docs = data

    if cadet_docs == []:
        return "No cadets found yet."
    if event_docs == []:
        return "No events found yet."

    event_row_labels, cadet_names, grid_rows = build_attendance_grid(
        cadet_docs, user_docs, event_docs, record_docs
    )

    df = pd.DataFrame(
        grid_rows,
        index=pd.Index(event_row_labels),
        columns=pd.Index(cadet_names),
    )

    return df
