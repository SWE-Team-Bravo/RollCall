from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

import pandas as pd
import streamlit as st
import pandas as pd

from services.dashboard import get_df
from bson import ObjectId

from utils.auth import get_current_user, require_role
from utils.db import get_collection, get_db
from utils.at_risk_email import send_at_risk_emails
from utils.export import to_excel

_DEFAULT_DAYS = 30
_MAX_ROWS = 2000
_MAX_EVENTS = 200


def _utc_datetime(d: date, end_of_day: bool) -> datetime:
    t = time(23, 59, 59, 999999) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t).replace(tzinfo=timezone.utc)


def _status_bucket(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if s == "present":
        return "Present"
    if s == "absent":
        return "Absent"
    if s in {"excused", "waived"}:
        return "Excused"
    return "Absent"


def _format_name(user_doc: dict[str, Any] | None) -> str:
    if not user_doc:
        return "Unknown"
    first = str(user_doc.get("first_name", "") or "").strip()
    last = str(user_doc.get("last_name", "") or "").strip()
    full = f"{first} {last}".strip()
    return full or "Unknown"


def _event_label(event_doc: dict[str, Any]) -> str:
    ev_start = event_doc.get("start_date")
    ev_date = ev_start.date().isoformat() if isinstance(ev_start, datetime) else ""
    ev_name = str(event_doc.get("event_name", "") or "").strip()
    ev_type = str(event_doc.get("event_type", "") or "").upper()
    left = f"{ev_date} — {ev_name}".strip(" —")
    return f"{left} ({ev_type})".strip()


def _status_cell_style(val: Any) -> str:
    """Return CSS style for a Status cell."""
    s = str(val or "")
    if s == "Present":
        return "background-color: #7FE08A; color: #0b2e13; font-weight: 700;"
    if s == "Absent":
        return "background-color: #E07F7F; color: #2b0b0b; font-weight: 700;"
    if s == "Excused":
        return "background-color: #E0D27F; color: #2b240b; font-weight: 700;"
    return ""


require_role("admin", "cadre", "flight_commander")

st.title("Dashboard")
st.caption("Filter and review attendance records.")

db = get_db()
if db is None:
    st.warning("Database is not configured as of now.")
    st.stop()

users_col = get_collection("users")
cadets_col = get_collection("cadets")
events_col = get_collection("events")
attendance_col = get_collection("attendance_records")
flights_col = get_collection("flights")

if any(
    x is None for x in (users_col, cadets_col, events_col, attendance_col, flights_col)
):
    st.error("Database unavailable.")
    st.stop()

assert users_col is not None
assert cadets_col is not None
assert events_col is not None
assert attendance_col is not None
assert flights_col is not None

current_user = get_current_user()
roles = set((current_user or {}).get("roles", []))
is_flight_commander_only = "flight_commander" in roles and not (
    roles & {"admin", "cadre"}
)

flight_filter_id: ObjectId | None = None
flight_filter_locked = False

if is_flight_commander_only and current_user:
    email = str(current_user.get("email", "") or "").strip()
    if email:
        user_doc = users_col.find_one({"email": email}, {"_id": 1})
        if user_doc and user_doc.get("_id") is not None:
            cadet_doc = cadets_col.find_one(
                {"user_id": user_doc["_id"]},
                {"flight_id": 1},
            )
            flight_id = cadet_doc.get("flight_id") if cadet_doc else None
            if isinstance(flight_id, ObjectId):
                flight_filter_id = flight_id
                flight_filter_locked = True

st.subheader("Filters")

today = datetime.now(timezone.utc).date()
default_start = today.fromordinal(today.toordinal() - _DEFAULT_DAYS)

col1, col2, col3, col4 = st.columns(4)
with col1:
    start_date = st.date_input("Start date", value=default_start)
with col2:
    end_date = st.date_input("End date", value=today)
with col3:
    event_type_choice = st.selectbox("Event type", ["All", "PT", "LLAB"], index=0)
with col4:
    status_choice = st.selectbox(
        "Status (cadet list)",
        ["All", "Present", "Absent", "Excused"],
        index=0,
    )

flight_docs = list(flights_col.find({}, {"_id": 1, "name": 1}).sort("name", 1))
flight_name_by_id = {
    f.get("_id"): str(f.get("name", ""))
    for f in flight_docs
    if f.get("_id") is not None
}

flight_names: list[str] = ["All flights"] + [
    str(f.get("name", "") or "") for f in flight_docs if str(f.get("name", "") or "")
]

selected_flight_name = "All flights"
if flight_filter_locked and flight_filter_id in flight_name_by_id:
    selected_flight_name = flight_name_by_id[flight_filter_id]

selected_flight_name = st.selectbox(
    "Flight",
    options=flight_names,
    index=flight_names.index(selected_flight_name)
    if selected_flight_name in flight_names
    else 0,
    disabled=flight_filter_locked,
)

if selected_flight_name != "All flights":
    # Map selected name back to ObjectId.
    for fid, fname in flight_name_by_id.items():
        if fname == selected_flight_name and isinstance(fid, ObjectId):
            flight_filter_id = fid
            break

if start_date > end_date:
    st.error("Start date must be on or before end date.")
    st.stop()

start_dt = _utc_datetime(start_date, end_of_day=False)
end_dt = _utc_datetime(end_date, end_of_day=True)

event_query: dict[str, Any] = {"start_date": {"$gte": start_dt, "$lte": end_dt}}
if event_type_choice == "PT":
    event_query["event_type"] = "pt"
elif event_type_choice == "LLAB":
    event_query["event_type"] = "lab"

event_docs = list(
    events_col.find(
        event_query,
        {"_id": 1, "start_date": 1, "event_name": 1, "event_type": 1},
    )
    .sort("start_date", -1)
    .limit(_MAX_EVENTS + 1)
)

too_many_events = len(event_docs) > _MAX_EVENTS
if too_many_events:
    event_docs = event_docs[:_MAX_EVENTS]

if not event_docs:
    st.info("No events found for the selected filters.")
    st.divider()
else:
    event_by_id = {e["_id"]: e for e in event_docs if e.get("_id") is not None}
    event_ids = list(event_by_id.keys())

    cadet_query: dict[str, Any] = {}
    if flight_filter_id is not None:
        cadet_query["flight_id"] = flight_filter_id

    cadet_docs = list(
        cadets_col.find(cadet_query, {"_id": 1, "user_id": 1, "flight_id": 1})
    )
    if not cadet_docs:
        st.info("No cadets found for the selected flight.")
        st.divider()
    else:
        cadet_ids = [c["_id"] for c in cadet_docs if c.get("_id") is not None]
        user_ids = [c["user_id"] for c in cadet_docs if c.get("user_id") is not None]

        user_docs = list(
            users_col.find(
                {"_id": {"$in": user_ids}},
                {"_id": 1, "first_name": 1, "last_name": 1},
            )
        )
        user_by_id = {u["_id"]: u for u in user_docs if u.get("_id") is not None}

        cadet_name_by_id: dict[ObjectId, str] = {}
        for c in cadet_docs:
            cid = c.get("_id")
            uid = c.get("user_id")
            if isinstance(cid, ObjectId) and uid is not None:
                cadet_name_by_id[cid] = _format_name(user_by_id.get(uid))

        # --- Event summary (one row per event)

        if too_many_events:
            st.warning(
                f"Showing newest {_MAX_EVENTS} events. Narrow the date range to see older events."
            )

        st.subheader("Event Summary")

        # Aggregate counts by event_id and status. Prefer doing this server-side.
        status_counts: dict[ObjectId, dict[str, int]] = {
            eid: {"Present": 0, "Absent": 0, "Excused": 0} for eid in event_ids
        }
        total_counts: dict[ObjectId, int] = {eid: 0 for eid in event_ids}

        match_stage: dict[str, Any] = {
            "event_id": {"$in": event_ids},
            "cadet_id": {"$in": cadet_ids},
        }

        try:
            pipeline = [
                {"$match": match_stage},
                {
                    "$group": {
                        "_id": {"event_id": "$event_id", "status": "$status"},
                        "count": {"$sum": 1},
                    }
                },
            ]

            for grp in attendance_col.aggregate(pipeline):
                key = grp.get("_id") or {}
                eid = key.get("event_id")
                raw_status = key.get("status")
                if not isinstance(eid, ObjectId):
                    continue
                bucket = _status_bucket(raw_status)
                status_counts.setdefault(eid, {"Present": 0, "Absent": 0, "Excused": 0})
                status_counts[eid][bucket] = status_counts[eid].get(bucket, 0) + int(
                    grp.get("count") or 0
                )
        except Exception:
            # Fallback: if aggregation is unavailable for some reason, do nothing.
            pass

        for eid, counts in status_counts.items():
            total_counts[eid] = sum(counts.values())

        summary_rows: list[dict[str, Any]] = []
        for eid in event_ids:
            ev = event_by_id.get(eid)
            if not ev:
                continue
            counts = status_counts.get(eid, {"Present": 0, "Absent": 0, "Excused": 0})
            summary_rows.append(
                {
                    "Event": _event_label(ev),
                    "Present": counts.get("Present", 0),
                    "Absent": counts.get("Absent", 0),
                    "Excused": counts.get("Excused", 0),
                    "Total": total_counts.get(eid, 0),
                    "_event_id": eid,
                }
            )

        summary_df = pd.DataFrame(summary_rows)
        if summary_df.empty:
            st.info("No attendance records found for the selected filters.")
            st.divider()
        else:
            # Keep the event_id hidden but available for selection.
            st.dataframe(
                summary_df.drop(columns=["_event_id"]),
                use_container_width=True,
                hide_index=True,
            )

            selected_label = st.selectbox(
                "Select an event to view cadets",
                options=list(summary_df["Event"]),
                index=0,
            )

            selected_row = summary_df.loc[summary_df["Event"] == selected_label].iloc[0]
            selected_event_id = selected_row["_event_id"]
            selected_event = event_by_id.get(selected_event_id)

            st.subheader("Cadets for Selected Event")
            if not selected_event:
                st.info("Could not load the selected event.")
            else:
                # Map cadet_id -> status for this event.
                recs = list(
                    attendance_col.find(
                        {"event_id": selected_event_id, "cadet_id": {"$in": cadet_ids}},
                        {"_id": 0, "cadet_id": 1, "status": 1},
                    )
                )
                status_by_cadet: dict[ObjectId, str] = {}
                for r in recs:
                    cid = r.get("cadet_id")
                    if isinstance(cid, ObjectId):
                        status_by_cadet[cid] = _status_bucket(r.get("status"))

                cadet_rows: list[dict[str, Any]] = []
                for cid, name in sorted(
                    cadet_name_by_id.items(), key=lambda x: x[1].lower()
                ):
                    status = status_by_cadet.get(cid, "Absent")
                    if status_choice != "All" and status != status_choice:
                        continue
                    cadet_rows.append({"Cadet": name, "Status": status})

                if not cadet_rows:
                    st.info("No cadets match the current status filter.")
                else:
                    cadet_df = pd.DataFrame(cadet_rows)
                    styler = cadet_df.style
                    if hasattr(styler, "map"):
                        styler = styler.map(_status_cell_style, subset=["Status"])
                    else:
                        styler = styler.applymap(_status_cell_style, subset=["Status"])

                    st.dataframe(styler, use_container_width=True, hide_index=True)

                st.subheader("Legend")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.success("Present")
                with c2:
                    st.error("Absent")
                with c3:
                    st.warning("Excused")

            st.divider()
st.subheader("At-Risk Report")
if st.button("Send At-Risk Emails"):
    sent, failed = send_at_risk_emails()
    if sent == 0 and failed == 0:
        st.info("At-risk cadets not found.")
    elif failed == 0:
        st.success(f"Emails sent to {sent} recipient(s).")
    else:
        st.warning(f"Sent: {sent}; Failed: {failed}.")
