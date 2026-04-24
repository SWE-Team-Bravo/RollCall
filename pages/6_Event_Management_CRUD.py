import streamlit as st
from datetime import date
from services.event_config import (
    get_event_config,
    save_event_config,
    _DEFAULT_PT_THRESHOLD,
    _DEFAULT_LLAB_THRESHOLD,
    _DEFAULT_WAIVER_REMINDER_DAYS,
    _DEFAULT_CHECKIN_WINDOW_MINUTES,
)
from services.events import (
    create_event,
    delete_event,
    get_all_events,
    get_timezone_options,
)
from utils.auth import require_role, get_current_user

require_role("admin", "cadre")

if "confirm_delete_event_id" not in st.session_state:
    st.session_state.confirm_delete_event_id = None
if "create_event_success" not in st.session_state:
    st.session_state.create_event_success = None
if "delete_event_success" not in st.session_state:
    st.session_state.delete_event_success = None

st.title("Event Management")

# ── helpers ──────────────────────────────────────────────────────────────────

DAYS_OF_WEEK = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def infer_event_type(selected_date: date, config: dict) -> str:
    """Return PT, LLAB, or empty string based on the saved schedule config."""
    day_name = selected_date.strftime("%A")
    if day_name in config.get("pt_days", []):
        return "pt"
    if day_name in config.get("llab_days", []):
        return "lab"
    return ""


# ── load config once ─────────────────────────────────────────────────────────

config = get_event_config() or {}

# =============================================================================
# SECTION 1 — Schedule Configuration (merged from #33)
# =============================================================================

with st.expander("Event Schedule Configuration", expanded=False):
    st.markdown("Configure which days of the week map to PT vs LLAB.")

    pt_days = st.multiselect(
        "PT Days",
        DAYS_OF_WEEK,
        default=config.get("pt_days", []),
        key="cfg_pt_days",
    )
    llab_days = st.multiselect(
        "LLAB Days",
        DAYS_OF_WEEK,
        default=config.get("llab_days", []),
        key="cfg_llab_days",
    )

    st.divider()

    st.markdown("Configure PT and LLAB absence thresholds.")
    pt_threshold = st.number_input(
        "PT Absence Threshold",
        min_value=1,
        max_value=20,
        value=config.get("pt_threshold", _DEFAULT_PT_THRESHOLD),
        step=1,
    )
    llab_threshold = st.number_input(
        "LLAB Absence Threshold",
        min_value=1,
        max_value=20,
        value=config.get("llab_threshold", _DEFAULT_LLAB_THRESHOLD),
        step=1,
    )

    st.divider()

    checkin_window = st.number_input(
        "Check-in window (in minutes)",
        min_value=5,
        max_value=30,
        value=config.get("checkin_window", _DEFAULT_CHECKIN_WINDOW_MINUTES),
        step=5,
    )

    st.divider()

    waiver_reminder_days = st.number_input(
        "Waiver Review Reminder Days (for Cadre)",
        min_value=1,
        max_value=20,
        value=config.get("waiver_reminder_days", _DEFAULT_WAIVER_REMINDER_DAYS),
        step=1,
    )

    if st.button("Save Schedule Configuration"):
        if save_event_config(
            pt_days,
            llab_days,
            pt_threshold,
            llab_threshold,
            checkin_window,
            waiver_reminder_days,
        ):
            st.success("Schedule configuration saved!")
            config = get_event_config() or {}  # refresh so create form picks it up
            st.rerun()
        else:
            st.error("Database unavailable — could not save configuration.")

st.divider()

# =============================================================================
# SECTION 2 — Create New Event
# =============================================================================

st.subheader("Create New Event")

TZ_OPTIONS = get_timezone_options()

with st.form("create_event_form"):
    event_name = st.text_input("Event Name", placeholder="e.g. Week 3 PT")

    start_date = st.date_input("Start Date", value=date.today())
    end_date = st.date_input("End Date", value=date.today())
    tz_name = st.selectbox("Timezone", TZ_OPTIONS, index=0)
    st.caption(
        "Dates are stored as 12:00 AM through 11:59 PM in the selected timezone."
    )

    # Auto-populate type from schedule config based on start date
    auto_type = infer_event_type(start_date, config)
    type_options = ["pt", "lab"]
    default_index = type_options.index(auto_type) if auto_type in type_options else 0

    event_type = st.selectbox(
        "Event Type",
        type_options,
        index=default_index,
        help="Auto-filled based on the day's schedule. You can override it.",
    )

    submitted = st.form_submit_button("Create Event")

if submitted:
    if not event_name.strip():
        st.error("Event name cannot be empty.")
    elif end_date < start_date:
        st.error("End date cannot be before start date.")
    else:
        user = get_current_user()
        user_id = user.get("email", "unknown") if user else "unknown"
        if create_event(
            event_name.strip(),
            event_type,
            start_date,
            end_date,
            user_id,
            tz_name,
        ):
            st.session_state.create_event_success = (
                f"Event '{event_name.strip()}' created successfully!"
            )
            st.rerun()
        else:
            st.error("Database unavailable — could not create event.")

if st.session_state.create_event_success:
    st.success(st.session_state.create_event_success)
    st.session_state.create_event_success = None
if st.session_state.delete_event_success:
    st.success(st.session_state.delete_event_success)
    st.session_state.delete_event_success = None

st.divider()

# =============================================================================
# SECTION 3 — Existing Events (table view + delete)
# =============================================================================

st.subheader("Existing Events")
st.caption("Start Date and End Date in the table below are shown in UTC.")

events = get_all_events()

if not events:
    st.info("No events found. Create one above.")
else:
    # Build display table
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Name": e.get("event_name", "—"),
                "Type": e.get("event_type", "—").upper(),
                "Start Date": e.get("start_date", "—"),
                "End Date": e.get("end_date", "—"),
            }
            for e in events
        ]
    )

    st.dataframe(df, width="stretch", hide_index=True)

    # Delete section below the table
    st.markdown("**Delete an Event**")
    event_labels = [
        f"{e.get('start_date', '—')} — {e.get('event_name', '—')}" for e in events
    ]
    selected_label = st.selectbox("Select event to delete", event_labels)
    selected_event = events[event_labels.index(selected_label)]

    if st.session_state.confirm_delete_event_id == selected_event["_id"]:
        st.warning(
            f"Delete **{selected_event.get('event_name', 'this event')}**? This cannot be undone."
        )
        c1, c2 = st.columns(2)
        if c1.button("Yes, delete", type="primary"):
            if delete_event(selected_event["_id"]):
                st.session_state.confirm_delete_event_id = None
                st.session_state.delete_event_success = "Event deleted successfully."
                st.rerun()
            else:
                st.error("Could not delete event.")
        if c2.button("Cancel"):
            st.session_state.confirm_delete_event_id = None
            st.rerun()
    else:
        if st.button("Delete Selected Event"):
            st.session_state.confirm_delete_event_id = selected_event["_id"]
            st.rerun()
