from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, available_timezones

import streamlit as st

<<<<<<< Updated upstream
from utils.at_risk_email import send_at_risk_emails
from utils.auth import get_current_user, require_role
from utils.export import to_excel
from utils.db import get_collection
=======
from services.attendance import CHECKIN_WINDOW_MINUTES
from services.event_code_display import (
    build_code_panel_html,
    build_fullscreen_code_html,
)
from services.event_codes import (
    build_expires_at,
    create_code,
    expire_code,
    get_active_code,
    is_expiry_valid,
    latest_allowed_expiry,
)
from services.events import closest_event_index, get_all_events
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import get_user_by_email
>>>>>>> Stashed changes

require_role("flight_commander", "cadre", "admin")

st.title("Event Code Generator")
st.caption("Generate attendance codes for cadets to self-report.")

current_user = get_current_user()
assert current_user is not None

<<<<<<< Updated upstream
current_user = get_current_user()
roles = set((current_user or {}).get("roles", []))
is_fc_only = "flight_commander" in roles and not (roles & {"admin", "cadre"})

fc_flight_id = None
if is_fc_only and current_user:
    users_col = get_collection("users")
    cadets_col = get_collection("cadets")
    if users_col and cadets_col:
        user_doc = users_col.find_one({"email": current_user.get("email")}, {"_id": 1})
        if user_doc:
            cadet_doc = cadets_col.find_one(
                {"user_id": user_doc["_id"]}, {"flight_id": 1}
            )
            if cadet_doc:
                fc_flight_id = cadet_doc.get("flight_id")

df = get_df(flight_id=fc_flight_id)
if isinstance(df, str):
    st.info("No cadets found.")
elif isinstance(df, pd.DataFrame):
    col1, col2, col3, spacer = st.columns([2, 2, 4, 8])
    col1.download_button(
        "Export CSV",
        df.to_csv(index=False).encode("utf-8"),
        "at_risk_cadets.csv",
        "text/csv",
=======
email = str(current_user.get("email", "") or "").strip()
user = get_user_by_email(email)
if user is None:
    st.error("Could not find user account.")
    st.stop()
assert user is not None

all_events = get_all_events()

if not all_events:
    st.info("No events found. Create events in Event Management first.")
    st.stop()

_PREFERRED = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
]
TZ_OPTIONS = _PREFERRED + [
    tz for tz in sorted(available_timezones()) if tz not in _PREFERRED
]

col_event, col_tz = st.columns([2, 1])

with col_event:
    event_labels = [
        f"{e.get('event_type', '').upper()} | {e.get('start_date', '')} | {e.get('event_name', '')}"
        for e in all_events
    ]
    selected_label = st.selectbox(
        "Event", event_labels, index=closest_event_index(all_events)
>>>>>>> Stashed changes
    )
    selected_event = all_events[event_labels.index(selected_label)]

with col_tz:
    tz_name = st.selectbox("Timezone", TZ_OPTIONS, index=0)

selected_event_start = selected_event.get("start_date")
max_expires_at = (
    latest_allowed_expiry(selected_event_start)
    if isinstance(selected_event_start, datetime)
    else None
)
if max_expires_at is not None:
    local_event_start = max_expires_at.astimezone(ZoneInfo(tz_name))
    st.caption(
        "Codes must expire no later than the event start time "
        f"({CHECKIN_WINDOW_MINUTES}-minute check-in window)."
    )
    st.caption(
        f"Selected event starts at {local_event_start.strftime('%Y-%m-%d %I:%M %p %Z')}"
    )

col_date, col_time = st.columns(2)

with col_date:
    exp_date = st.date_input("Expiration date", value=date.today())

with col_time:
    exp_time = st.time_input("Expiration time", value=time(23, 59))

expires_at = build_expires_at(exp_date, exp_time, tz_name)

if st.button("Generate New Code", type="primary", width="stretch"):