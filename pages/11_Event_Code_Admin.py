from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, available_timezones

import streamlit as st

from services.event_codes import (
    build_expires_at,
    create_code,
    expire_code,
    get_active_code,
    is_expiry_valid,
)
from services.events import closest_event_index, get_all_events
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import get_user_by_email

require_role("flight_commander", "cadre", "admin")

st.title("Event Code Generator")
st.caption("Generate attendance codes for cadets to self-report.")

current_user = get_current_user()
assert current_user is not None

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
    )
    selected_event = all_events[event_labels.index(selected_label)]

with col_tz:
    tz_name = st.selectbox("Timezone", TZ_OPTIONS, index=0)

col_date, col_time = st.columns(2)

with col_date:
    exp_date = st.date_input("Expiration date", value=date.today())

with col_time:
    exp_time = st.time_input("Expiration time", value=time(23, 59))

expires_at = build_expires_at(exp_date, exp_time, tz_name)

if st.button("Generate New Code", type="primary", width="stretch"):
    if not is_expiry_valid(expires_at):
        st.error("Expiration must be in the future.")
    else:
        result = create_code(
            event_id=selected_event["_id"],
            event_type=selected_event.get("event_type", ""),
            event_date=str(selected_event.get("start_date", "")),
            created_by_user_id=user["_id"],
            expires_at=expires_at,
        )
        if result is None:
            st.error("Database unavailable. Could not generate code.")
        else:
            st.success("New code generated.")
            st.rerun()

st.divider()

_selected_event_id = selected_event["_id"]


@st.fragment(run_every=30)
def _active_code_panel(event_id: str, tz: str) -> None:
    active_code = get_active_code(event_id)

    if not active_code:
        st.info(
            "No active code for the selected event. Use **Generate New Code** above."
        )
        return

    code_str = str(active_code.get("code", ""))
    code_expires_at = active_code.get("expires_at")

    st.markdown(
        f"""
        <div style="
            text-align: center;
            padding: 2.5rem 1rem;
            background: #0e1117;
            border: 2px solid #2d2d3a;
            border-radius: 1rem;
            margin: 1rem 0;
        ">
            <p style="
                color: #888;
                font-size: 1rem;
                margin: 0 0 0.5rem 0;
                letter-spacing: 0.1em;
                text-transform: uppercase;
            ">Active Code</p>
            <p style="
                font-size: 7rem;
                font-weight: 900;
                letter-spacing: 0.35em;
                color: #ffffff;
                margin: 0;
                font-family: monospace;
                line-height: 1;
            ">{code_str}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if isinstance(code_expires_at, datetime):
        if code_expires_at.tzinfo is None:
            code_expires_at = code_expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        remaining_secs = (code_expires_at - now).total_seconds()
        local_expires = code_expires_at.astimezone(ZoneInfo(tz))
        if remaining_secs > 0:
            mins = int(remaining_secs // 60)
            secs = int(remaining_secs % 60)
            st.caption(
                f"Expires {local_expires.strftime('%Y-%m-%d %I:%M %p %Z')}"
                f" — {mins}m {secs}s remaining"
            )
        else:
            st.warning("This code has expired. Generate a new one above.")

    if st.button("Expire Code Now", type="secondary"):
        if expire_code(active_code["_id"]):
            st.success("Code expired.")
            st.rerun()
        else:
            st.error("Could not expire code.")


_active_code_panel(_selected_event_id, tz_name)
