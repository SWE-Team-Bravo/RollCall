from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from services.event_code_display import (
    build_code_panel_html,
    build_fullscreen_code_html,
)
from services.event_codes import (
    EVENT_CODE_VALID_AFTER_START_MINUTES,
    build_expires_at,
    build_valid_expiration_times,
    create_code,
    expire_code,
    get_active_code,
    is_expiry_valid,
    latest_allowed_expiry,
)
from services.events import (
    closest_event_index,
    get_all_events,
    get_event_time_bounds,
    get_timezone_options,
)
from utils.auth import get_current_user_doc, require_role

require_role("flight_commander", "cadre", "admin")

st.title("Event Code Generator")
st.caption("Generate attendance codes for cadets to self-report.")

user = get_current_user_doc()
if user is None:
    st.error("Could not find user account.")
    st.stop()
assert user is not None

all_events = get_all_events()

if not all_events:
    st.info("No events found. Create events in Event Management first.")
    st.stop()

TZ_OPTIONS = get_timezone_options()

col_event, col_tz = st.columns([2, 1])

with col_event:
    event_labels = [
        f"{e.get('event_type', '').upper()} | {e.get('start_date', '')} UTC | {e.get('event_name', '')}"
        for e in all_events
    ]
    selected_label = st.selectbox(
        "Event", event_labels, index=closest_event_index(all_events)
    )
    selected_event = all_events[event_labels.index(selected_label)]

with col_tz:
    tz_name = st.selectbox("Timezone", TZ_OPTIONS, index=0)

selected_event_start, _selected_event_end = get_event_time_bounds(
    selected_event,
    fallback_tz_name=tz_name,
)
max_expires_at = latest_allowed_expiry(selected_event_start)
if max_expires_at is not None:
    local_limit = max_expires_at.astimezone(ZoneInfo(tz_name))
    st.caption(
        "Codes must expire no later than "
        f"{EVENT_CODE_VALID_AFTER_START_MINUTES} minutes after the event start time."
    )
    if selected_event_start is not None:
        local_event_start = selected_event_start.astimezone(ZoneInfo(tz_name))
        st.caption(
            "Selected event starts at "
            f"{local_event_start.strftime('%Y-%m-%d %I:%M %p %Z')}; "
            "latest valid expiration is "
            f"{local_limit.strftime('%Y-%m-%d %I:%M %p %Z')}"
        )

default_expiry_local = (
    max_expires_at.astimezone(ZoneInfo(tz_name)) if max_expires_at else None
)
exp_date = (
    default_expiry_local.date()
    if default_expiry_local
    else datetime.now(timezone.utc).date()
)

valid_expiration_times = build_valid_expiration_times(
    exp_date,
    max_expires_at,
    tz_name,
)

if valid_expiration_times:
    default_exp_time = (
        default_expiry_local.time().replace(tzinfo=None, second=0, microsecond=0)
        if default_expiry_local
        else valid_expiration_times[-1]
    )
    default_exp_time_index = (
        valid_expiration_times.index(default_exp_time)
        if default_exp_time in valid_expiration_times
        else len(valid_expiration_times) - 1
    )
    exp_time = st.selectbox(
        "Expiration time",
        valid_expiration_times,
        index=default_exp_time_index,
        format_func=lambda t: t.strftime("%H:%M"),
    )
else:
    st.selectbox("Expiration time", ["No valid times"], disabled=True)
    exp_time = None

expires_at = build_expires_at(exp_date, exp_time, tz_name) if exp_time else None

if not valid_expiration_times:
    st.warning("No valid expiration times remain for this event.")

if st.button(
    "Generate New Code",
    type="primary",
    width="stretch",
    disabled=expires_at is None,
):
    assert expires_at is not None
    if not is_expiry_valid(expires_at, max_expires_at):
        if expires_at <= datetime.now(timezone.utc):
            st.error("Expiration must be in the future.")
        elif max_expires_at is not None:
            local_limit = max_expires_at.astimezone(ZoneInfo(tz_name))
            st.error(
                "Expiration must be no later than 10 minutes after the event starts: "
                f"{local_limit.strftime('%Y-%m-%d %I:%M %p %Z')}."
            )
        else:
            st.error("Invalid expiration time.")
    else:
        result = create_code(
            event_id=selected_event["_id"],
            event_type=selected_event.get("event_type", ""),
            event_date=str(selected_event.get("start_date", "")),
            created_by_user_id=user["_id"],
            expires_at=expires_at,
            actor_email=str(user.get("email", "") or "").strip() or None,
        )
        if result is None:
            st.error("Database unavailable. Could not generate code.")
        else:
            st.success("New code generated.")
            st.rerun()

st.divider()

_selected_event_id = selected_event["_id"]


@st.dialog("Event Code — Fullscreen", width="large")
def _fullscreen_dialog(code_str: str) -> None:
    st.markdown(build_fullscreen_code_html(code_str), unsafe_allow_html=True)


@st.fragment(run_every=1)
def _active_code_panel(event_id: str, tz: str) -> None:
    assert user is not None
    active_code = get_active_code(event_id)

    if not active_code:
        st.info(
            "No active code for the selected event. Use **Generate New Code** above."
        )
        return

    code_str = str(active_code.get("code", ""))
    code_expires_at = active_code.get("expires_at")

    st.markdown(build_code_panel_html(code_str), unsafe_allow_html=True)

    if st.button("⛶ Fullscreen", key="fullscreen_btn"):
        _fullscreen_dialog(code_str)

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
        if expire_code(
            active_code["_id"],
            actor_user_id=user.get("_id"),
            actor_email=str(user.get("email", "") or "").strip() or None,
        ):
            st.success("Code expired.")
            st.rerun()
        else:
            st.error("Could not expire code.")


_active_code_panel(_selected_event_id, tz_name)
