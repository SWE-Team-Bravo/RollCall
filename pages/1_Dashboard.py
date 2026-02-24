from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from pymongo.collection import Collection

from utils.auth import require_role
from utils.db import get_collection, get_db


def _format_event_row_label(event: dict[str, Any]) -> str:
    sd = event.get("start_date")
    if isinstance(sd, datetime):
        date_str = sd.strftime("%Y-%m-%d")
    else:
        date_str = str(sd)[:10] if sd else "Unknown date"

    name = event.get("event_name") or event.get("name") or ""
    return f"{date_str} — {name}" if name else date_str


def _normalize_status(status: str | None) -> str:
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


def _cell_style(val: str) -> str:
    if val == "P":
        return "background-color: #7FE08A; color: #0b2e13; font-weight: 700; text-align: center;"
    if val == "A":
        return "background-color: #E07F7F; color: #2b0b0b; font-weight: 700; text-align: center;"
    if val == "E":
        return "background-color: #E0D27F; color: #2b240b; font-weight: 700; text-align: center;"
    return "text-align: center;"


require_role("admin", "cadre", "flight_commander")

st.title("Dashboard")
st.caption("Rows = event dates (newest first). Columns = cadets (alphabetical).")

db = get_db()
if db is None:
    st.warning("Database is not configured as of now.")
    st.stop()

users = get_collection("users")
cadets = get_collection("cadets")
events = get_collection("events")
attendance = get_collection("attendance_records")

if any(x is None for x in (users, cadets, events, attendance)):
    st.error("Database unavailable.")
    st.stop()

# Tell the type-checker these are non-None from here on
assert isinstance(users, Collection)
assert isinstance(cadets, Collection)
assert isinstance(events, Collection)
assert isinstance(attendance, Collection)

# Cadets (columns)
cadet_docs = list(cadets.find({}, {"_id": 1, "user_id": 1}))
if not cadet_docs:
    st.info("No cadets found yet.")
    st.stop()

user_ids = [c["user_id"] for c in cadet_docs if "user_id" in c]
user_docs = list(users.find({"_id": {"$in": user_ids}}, {"_id": 1, "name": 1}))
name_by_user_id = {
    u["_id"]: f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Unknown"
    for u in user_docs
}

cadet_name_by_cadet_id = {
    c["_id"]: name_by_user_id.get(c.get("user_id"), "Unknown") for c in cadet_docs
}

cadet_pairs = sorted(cadet_name_by_cadet_id.items(), key=lambda x: x[1].lower())
cadet_ids_sorted = [cid for cid, _ in cadet_pairs]
cadet_names_sorted: list[str] = [nm for _, nm in cadet_pairs]

# Events (rows, newest first)
event_docs = list(events.find({}, {"_id": 1, "start_date": 1, "event_name": 1}))
if not event_docs:
    st.info("No events found yet.")
    st.stop()


def _event_sort_key(e: dict[str, Any]) -> Any:
    sd = e.get("start_date")
    return sd if isinstance(sd, datetime) else str(sd or "")


event_docs_sorted = sorted(event_docs, key=_event_sort_key, reverse=True)
event_ids_sorted = [e["_id"] for e in event_docs_sorted]
event_row_labels: list[str] = [_format_event_row_label(e) for e in event_docs_sorted]

# Attendance lookup (event_id, cadet_id) -> P/A/E
record_docs = list(
    attendance.find(
        {"event_id": {"$in": event_ids_sorted}},
        {"_id": 0, "event_id": 1, "cadet_id": 1, "status": 1},
    )
)

status_by_pair: dict[tuple[Any, Any], str] = {}
for r in record_docs:
    key = (r.get("event_id"), r.get("cadet_id"))
    status_by_pair[key] = _normalize_status(r.get("status"))

# Build grid (default absent)
grid_rows: list[list[str]] = []
for ev_id in event_ids_sorted:
    row: list[str] = []
    for cadet_id in cadet_ids_sorted:
        row.append(status_by_pair.get((ev_id, cadet_id), "A"))
    grid_rows.append(row)

df = pd.DataFrame(
    grid_rows,
    index=pd.Index(event_row_labels),
    columns=pd.Index(cadet_names_sorted),
)

st.dataframe(df.style.applymap(_cell_style), use_container_width=True)

st.divider()
st.subheader("Legend")

col1, col2, col3 = st.columns(3)
with col1:
    st.success("P = Present")
with col2:
    st.error("A = Absent")
with col3:
    st.warning("E = Excused / Waived")
