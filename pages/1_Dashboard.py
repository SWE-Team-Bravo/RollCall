from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

import pandas as pd
import streamlit as st

from bson import ObjectId

from services.dashboard import get_semester_df
from services.events import closest_event_index
from utils.auth import get_current_user, require_role
from utils.attendance_status import (
    get_attendance_status_cell_style,
    get_attendance_status_label,
)
from utils.db import get_collection, get_db
from utils.export import to_excel
from utils.pagination import (
    build_pagination_metadata,
    init_pagination_state,
    paginate_list,
    render_pagination_controls,
    sync_pagination_state,
)


require_role("admin", "cadre", "flight_commander")


def _utc_datetime(d: date, end_of_day: bool) -> datetime:
    t = time(23, 59, 59, 999999) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t).replace(tzinfo=timezone.utc)


def _status_bucket(raw: str | None) -> str:
    return get_attendance_status_label(raw, default="Absent")


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

if roles & {"admin", "cadre"}:
    st.subheader("Export Full Semester Data")
    semester_df = get_semester_df()

    if isinstance(semester_df, str):
        st.warning(semester_df)

    if isinstance(semester_df, pd.DataFrame):
        col1, col2, spacer = st.columns([1.5, 2, 10])
        col1.download_button(
            "Export CSV",
            semester_df.to_csv().encode("utf-8"),
            "attendance.csv",
            "text/csv",
            key="semester_data_csv",
        )
        col2.download_button(
            "Export Excel",
            to_excel(semester_df),
            "attendance.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="semester_data_excel",
        )

st.subheader("Filters")
today = datetime.now(timezone.utc).date()
default_start = today.replace(month=1, day=1)

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

event_pagination_reset_token = "|".join(
    [
        start_dt.isoformat(),
        end_dt.isoformat(),
        event_type_choice,
        selected_flight_name,
    ]
)
event_page, event_page_size = init_pagination_state(
    "dashboard_events",
    reset_token=event_pagination_reset_token,
)
total_event_count = int(events_col.count_documents(event_query))
event_pagination = build_pagination_metadata(
    page=event_page,
    page_size=event_page_size,
    total_count=total_event_count,
)

event_docs = list(
    events_col.find(
        event_query,
        {"_id": 1, "start_date": 1, "event_name": 1, "event_type": 1},
    )
    .sort("start_date", -1)
    .skip(event_pagination["skip"])
    .limit(event_pagination["page_size"])
)
event_pagination = {**event_pagination, "items": event_docs}
sync_pagination_state("dashboard_events", event_pagination)

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

        st.subheader("Event Summary")
        st.caption(f"Showing {len(event_docs)} event(s) on this page.")

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
            st.warning(
                "Could not load attendance summary. Some counts may be incomplete."
            )

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
                width="stretch",
                hide_index=True,
            )
            render_pagination_controls("dashboard_events", event_pagination)

            summary_event_ids = list(summary_df["_event_id"])
            if (
                "dashboard_selected_event_id" not in st.session_state
                or st.session_state["dashboard_selected_event_id"] not in summary_event_ids
            ):
                _summary_events = [event_by_id.get(eid, {}) for eid in summary_event_ids]
                default_index = closest_event_index(_summary_events)
                st.session_state["dashboard_selected_event_id"] = summary_event_ids[
                    default_index
                ]

            selected_event_id = st.selectbox(
                "Select an event to view cadets",
                options=summary_event_ids,
                format_func=lambda eid: _event_label(event_by_id.get(eid, {})),
                key="dashboard_selected_event_id",
            )
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
                    cadet_pagination_reset_token = "|".join(
                        [
                            str(selected_event_id),
                            status_choice,
                            selected_flight_name,
                        ]
                    )
                    cadet_page, cadet_page_size = init_pagination_state(
                        "dashboard_cadets",
                        reset_token=cadet_pagination_reset_token,
                    )
                    paginated_cadets = paginate_list(
                        cadet_rows,
                        page=cadet_page,
                        page_size=cadet_page_size,
                    )
                    sync_pagination_state("dashboard_cadets", paginated_cadets)

                    cadet_df = pd.DataFrame(paginated_cadets["items"])
                    export_cadet_df = pd.DataFrame(cadet_rows)
                    styler = cadet_df.style
                    if hasattr(styler, "map"):
                        styler = styler.map(
                            get_attendance_status_cell_style,
                            subset=["Status"],
                        )
                    else:
                        styler = styler.applymap(
                            get_attendance_status_cell_style,
                            subset=["Status"],
                        )

                    col1, col2, spacer = st.columns([1.5, 2, 10])
                    if isinstance(export_cadet_df, pd.DataFrame):
                        col1.download_button(
                            "Export CSV",
                            export_cadet_df.to_csv(index=False).encode("utf-8"),
                            "attendance.csv",
                            "text/csv",
                        )
                        col2.download_button(
                            "Export Excel",
                            to_excel(export_cadet_df),
                            "attendance.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

                    leg1, leg2, leg3 = st.columns(3)
                    with leg1:
                        st.success("Present")
                    with leg2:
                        st.error("Absent")
                    with leg3:
                        st.warning("Excused")

                    st.dataframe(styler, width="stretch", hide_index=True)
                    render_pagination_controls("dashboard_cadets", paginated_cadets)
