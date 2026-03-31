import streamlit as st
from datetime import date, timedelta
from services.event_config import get_event_config, save_event_config
from services.events import get_all_events, create_event, delete_event
from utils.auth import require_role, get_current_user

require_role("admin", "cadre")

st.title("Event Management")

# ── helpers ──────────────────────────────────────────────────────────────────

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

def infer_event_type(selected_date: date, config: dict) -> str:
    """Return PT, LLAB, or empty string based on the saved schedule config."""
    day_name = selected_date.strftime("%A")
    if day_name in config.get("pt_days", []):
        return "pt"
    if day_name in config.get("llab_days", []):
        return "llab"
    return ""

# ── load config once ─────────────────────────────────────────────────────────

config = get_event_config()

# =============================================================================
# SECTION 1 — Schedule Configuration (merged from #33)
# =============================================================================

with st.expander("⚙️ Event Schedule Configuration", expanded=False):
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

    if st.button("Save Schedule Configuration"):
        if save_event_config(pt_days, llab_days):
            st.success("Schedule configuration saved!")
            config = get_event_config()   # refresh so create form picks it up
            st.rerun()
        else:
            st.error("Database unavailable — could not save configuration.")

st.divider()

# =============================================================================
# SECTION 2 — Create New Event
# =============================================================================

st.subheader("➕ Create New Event")

with st.form("create_event_form"):
    event_name = st.text_input("Event Name", placeholder="e.g. Week 3 PT")

    start_date = st.date_input("Start Date", value=date.today())
    end_date   = st.date_input("End Date",   value=date.today())

    # Auto-populate type from schedule config based on start date
    auto_type = infer_event_type(start_date, config)
    type_options = ["pt", "llab"]
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
        if create_event(event_name.strip(), event_type, start_date, end_date, user_id):
            st.success(f"Event '{event_name}' created successfully!")
            st.rerun()
        else:
            st.error("Database unavailable — could not create event.")

st.divider()

# =============================================================================
# SECTION 3 — Existing Events (table view + delete)
# =============================================================================

st.subheader("📋 Existing Events")

events = get_all_events()

if not events:
    st.info("No events found. Create one above.")
else:
    # Build display table
    import pandas as pd

    df = pd.DataFrame([
        {
            "Name": e.get("event_name", "—"),
            "Type": e.get("event_type", "—").upper(),
            "Start Date": e.get("start_date", "—"),
            "End Date": e.get("end_date", "—"),
        }
        for e in events
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Delete section below the table
    st.markdown("**Delete an Event**")
    event_labels = [
         f"{e.get('start_date', '—')} — {e.get('event_name', '—')}" for e in events
    ]
    selected_label = st.selectbox("Select event to delete", event_labels)
    selected_event = events[event_labels.index(selected_label)]

    if st.button("🗑️ Delete Selected Event", type="primary"):
        if delete_event(selected_event["_id"]):
            st.success("Event deleted.")
            st.rerun()
        else:
            st.error("Could not delete event.")