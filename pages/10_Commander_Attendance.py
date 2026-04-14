from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from services.commander_attendance import build_commander_roster, compute_upserts
from services.events import closest_event_index, get_all_events
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    create_attendance_record,
    get_all_cadets,
    get_attendance_by_event,
    get_user_by_email,
    get_user_by_id,
    update_attendance_record,
)

STATUS_OPTIONS = ["Present", "Absent", "Excused"]
STATUS_TO_DB = {"Present": "present", "Absent": "absent", "Excused": "excused"}
DB_TO_STATUS = {"present": "Present", "absent": "Absent", "excused": "Excused"}

require_role("admin", "cadre")
st.title("Modify Attendance")
st.caption("Manually set attendance for cadets. These entries override self-check-ins.")

current_user = get_current_user()
assert current_user is not None

email = str(current_user.get("email", "")).strip()
user = get_user_by_email(email)
if user is None:
    st.error("Could not find your account.")
    st.stop()
assert user is not None

all_events = get_all_events()
if not all_events:
    st.info("No events found.")
    st.stop()


def _event_label(event: dict[str, Any]) -> str:
    name = str(event.get("event_name", "Event")).strip() or "Event"
    start = event.get("start_date")
    if isinstance(start, datetime):
        date_str = start.date().isoformat()
    elif isinstance(start, str):
        date_str = start[:10]
    else:
        date_str = ""
    return f"{name} ({date_str})" if date_str else name


selected_event = st.selectbox(
    "Select event",
    options=all_events,
    format_func=_event_label,
    index=closest_event_index(all_events),
)
if selected_event is None:
    st.stop()

event_id: str = selected_event["_id"]

all_cadets = get_all_cadets()
if not all_cadets:
    st.info("No cadets found.")
    st.stop()

for i, c in enumerate(all_cadets):
    first = str(c.get("first_name", "") or "").strip()
    last = str(c.get("last_name", "") or "").strip()
    if not first and not last:
        uid = c.get("user_id")
        if uid is not None:
            user_doc = get_user_by_id(uid)
            if user_doc is not None:
                c = dict(c)
                c["first_name"] = user_doc.get("first_name", "")
                c["last_name"] = user_doc.get("last_name", "")
                all_cadets[i] = c

records = get_attendance_by_event(event_id)
roster = build_commander_roster(all_cadets, records)

cadet_ids = [str(entry["cadet"]["_id"]) for entry in roster]

df = pd.DataFrame(
    {
        "Cadet": [
            f"{str(e['cadet'].get('last_name', '') or '').strip()}, "
            f"{str(e['cadet'].get('first_name', '') or '').strip()}".strip(", ")
            or "Unknown"
            for e in roster
        ],
        "Status": [DB_TO_STATUS.get(e["current_status"], "Present") for e in roster],
    }
)

edited = st.data_editor(
    df,
    column_config={
        "Cadet": st.column_config.TextColumn(disabled=True),
        "Status": st.column_config.SelectboxColumn(
            options=STATUS_OPTIONS, required=True
        ),
    },
    hide_index=True,
    use_container_width=True,
)

st.divider()
if st.button("Save All", type="primary"):
    new_statuses = {
        cadet_ids[idx]: STATUS_TO_DB[row["Status"]]
        for idx, (_, row) in enumerate(edited.iterrows())
    }
    upserts = compute_upserts(roster, new_statuses)
    for op in upserts:
        if op["action"] == "update":
            update_attendance_record(op["record_id"], {"status": op["status"]})
        else:
            create_attendance_record(
                event_id=event_id,
                cadet_id=op["cadet_id"],
                status=op["status"],
                recorded_by_user_id=user["_id"],
            )
    st.success(f"Saved attendance for {len(upserts)} cadet(s).")
    st.rerun()
