import streamlit as st
from datetime import date
from services.event_config import (
    DEFAULT_CHECKIN_WINDOW_MINUTES,
    DEFAULT_LLAB_THRESHOLD,
    DEFAULT_PT_THRESHOLD,
    DEFAULT_WAIVER_REMINDER_DAYS,
    get_event_config,
    save_event_config,
)
from services.events import (
    archive_event,
    create_event,
    get_all_events,
    get_timezone_options,
    restore_event,
    update_event,
)
from utils.auth import require_role, get_current_user_doc

require_role("admin", "cadre")

if "confirm_archive_event_id" not in st.session_state:
    st.session_state.confirm_archive_event_id = None
if "create_event_success" not in st.session_state:
    st.session_state.create_event_success = None
if "archive_event_success" not in st.session_state:
    st.session_state.archive_event_success = None
if "edit_event_id" not in st.session_state:
    st.session_state.edit_event_id = None
if "edit_event_success" not in st.session_state:
    st.session_state.edit_event_success = None
if "restore_event_success" not in st.session_state:
    st.session_state.restore_event_success = None

st.title("Event Management")

current_user_doc = get_current_user_doc()

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
    """Return pt or lab based on the saved schedule config."""
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
        value=config.get("pt_threshold", DEFAULT_PT_THRESHOLD),
        step=1,
    )
    llab_threshold = st.number_input(
        "LLAB Absence Threshold",
        min_value=1,
        max_value=20,
        value=config.get("llab_threshold", DEFAULT_LLAB_THRESHOLD),
        step=1,
    )

    st.divider()

    checkin_window = st.number_input(
        "Check-in window (in minutes)",
        min_value=5,
        max_value=30,
        value=config.get("checkin_window", DEFAULT_CHECKIN_WINDOW_MINUTES),
        step=5,
    )

    st.divider()

    waiver_reminder_days = st.number_input(
        "Waiver Review Reminder Days (for Cadre)",
        min_value=1,
        max_value=20,
        value=config.get("waiver_reminder_days", DEFAULT_WAIVER_REMINDER_DAYS),
        step=1,
    )

    st.divider()

    email_enabled = st.toggle(
        "Enable Email Notifications",
        value=config.get("email_enabled", True),
        key="cfg_email_enabled",
    )

    if st.button("Save Schedule Configuration"):
        if save_event_config(
            pt_days,
            llab_days,
            pt_threshold,
            llab_threshold,
            checkin_window,
            waiver_reminder_days,
            email_enabled,
            actor_user_id=current_user_doc.get("_id") if current_user_doc else None,
            actor_email=current_user_doc.get("email") if current_user_doc else None,
        ):
            st.success("Schedule configuration saved!")
            config = get_event_config() or {}
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
        creator_id = (
            str(current_user_doc["_id"])
            if current_user_doc
            else "unknown"
        )
        if create_event(
            event_name.strip(),
            event_type,
            start_date,
            end_date,
            creator_id,
            tz_name,
            actor_user_id=current_user_doc.get("_id") if current_user_doc else None,
            actor_email=current_user_doc.get("email") if current_user_doc else None,
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
if st.session_state.edit_event_success:
    st.success(st.session_state.edit_event_success)
    st.session_state.edit_event_success = None

st.divider()

# =============================================================================
# SECTION 3 — Existing Events (table view + edit + delete)
# =============================================================================

st.subheader("Existing Events")
st.caption("Start Date and End Date in the table below are shown in UTC.")

events = get_all_events(include_archived=True)
active_events = [event for event in events if not event.get("archived", False)]
archived_events = [event for event in events if event.get("archived", False)]

if not active_events and not archived_events:
    st.info("No events found. Create one above.")
else:
    import pandas as pd

    if active_events:
        df = pd.DataFrame(
            [
                {
                    "Name": e.get("event_name", "—"),
                    "Type": e.get("event_type", "—").upper(),
                    "Start Date": e.get("start_date", "—"),
                    "End Date": e.get("end_date", "—"),
                }
                for e in active_events
            ]
        )

        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No active events found.")

    # ── Edit section ─────────────────────────────────────────────────────────
    st.subheader("Edit an Event")
    if not active_events:
        st.caption("No active events available to edit.")
    else:
        edit_labels = [
            f"{e.get('start_date', '—')} — {e.get('event_name', '—')}"
            for e in active_events
        ]
        selected_edit_label = st.selectbox(
            "Select event to edit", edit_labels, key="edit_selectbox"
        )
        selected_edit_event = active_events[edit_labels.index(selected_edit_label)]

        if st.button("Edit Selected Event"):
            st.session_state.edit_event_id = selected_edit_event["_id"]
            st.rerun()

        if st.session_state.edit_event_id == selected_edit_event["_id"]:
            with st.form("edit_event_form"):
                st.markdown(f"**Editing:** {selected_edit_event.get('event_name', '')}")

                new_name = st.text_input(
                    "Event Name",
                    value=selected_edit_event.get("event_name", ""),
                )

                existing_start = selected_edit_event.get("start_date", "")
                existing_end = selected_edit_event.get("end_date", "")
                try:
                    parsed_start = date.fromisoformat(str(existing_start)[:10])
                except ValueError:
                    parsed_start = date.today()
                try:
                    parsed_end = date.fromisoformat(str(existing_end)[:10])
                except ValueError:
                    parsed_end = date.today()

                new_start = st.date_input("Start Date", value=parsed_start, key="edit_start")
                new_end = st.date_input("End Date", value=parsed_end, key="edit_end")

                existing_tz = selected_edit_event.get("timezone_name", "UTC")
                tz_index = TZ_OPTIONS.index(existing_tz) if existing_tz in TZ_OPTIONS else 0
                new_tz = st.selectbox("Timezone", TZ_OPTIONS, index=tz_index, key="edit_tz")

                existing_type = selected_edit_event.get("event_type", "pt")
                type_options = ["pt", "lab"]
                type_index = type_options.index(existing_type) if existing_type in type_options else 0
                new_type = st.selectbox("Event Type", type_options, index=type_index, key="edit_type")

                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Save Changes", type="primary")
                cancel = c2.form_submit_button("Cancel")

            if save:
                if not new_name.strip():
                    st.error("Event name cannot be empty.")
                elif new_end < new_start:
                    st.error("End date cannot be before start date.")
                else:
                    if update_event(
                        selected_edit_event["_id"],
                        new_name.strip(),
                        new_type,
                        new_start,
                        new_end,
                        new_tz,
                        actor_user_id=current_user_doc.get("_id") if current_user_doc else None,
                        actor_email=current_user_doc.get("email") if current_user_doc else None,
                    ):
                        st.session_state.edit_event_id = None
                        st.session_state.edit_event_success = f"Event '{new_name.strip()}' updated successfully!"
                        st.rerun()
                    else:
                        st.error("Could not update event.")
            if cancel:
                st.session_state.edit_event_id = None
                st.rerun()

    st.divider()

    # ── Archive section ───────────────────────────────────────────────────────
    st.subheader("Archive an Event")
    if not active_events:
        st.caption("No active events available to archive.")
    else:
        if st.session_state.archive_event_success:
            st.success(st.session_state.archive_event_success)
            st.session_state.archive_event_success = None

        event_labels = [
            f"{e.get('start_date', '—')} — {e.get('event_name', '—')}"
            for e in active_events
        ]
        selected_label = st.selectbox("Select event to archive", event_labels)
        selected_event = active_events[event_labels.index(selected_label)]

        if st.session_state.confirm_archive_event_id == selected_event["_id"]:
            st.warning(
                f"Archive **{selected_event.get('event_name', 'this event')}**? Attendance history will be preserved."
            )
            c1, c2 = st.columns(2)
            if c1.button("Yes, archive", type="primary"):
                if archive_event(
                    selected_event["_id"],
                    actor_user_id=current_user_doc.get("_id") if current_user_doc else None,
                    actor_email=current_user_doc.get("email") if current_user_doc else None,
                ):
                    st.session_state.confirm_archive_event_id = None
                    st.session_state.archive_event_success = "Event archived successfully."
                    st.rerun()
                else:
                    st.error("Could not archive event.")
            if c2.button("Cancel"):
                st.session_state.confirm_archive_event_id = None
                st.rerun()
        else:
            if st.button("Archive Selected Event"):
                st.session_state.confirm_archive_event_id = selected_event["_id"]
                st.rerun()

    # Keep archived events expander open when user has previously interacted with it
    _archived_expanded = (
        len(archived_events) > 0
        and "restore_event_selectbox" in st.session_state
    )

    with st.expander(
        f"Archived Events ({len(archived_events)})",
        expanded=_archived_expanded,
    ):
        if not archived_events:
            st.caption("No archived events.")
        else:
            if st.session_state.restore_event_success:
                st.success(st.session_state.restore_event_success)
                st.session_state.restore_event_success = None

            archived_df = pd.DataFrame(
                [
                    {
                        "Name": e.get("event_name", "—"),
                        "Type": e.get("event_type", "—").upper(),
                        "Start Date": e.get("start_date", "—"),
                        "End Date": e.get("end_date", "—"),
                    }
                    for e in archived_events
                ]
            )
            st.dataframe(archived_df, width="stretch", hide_index=True)

            archived_labels = [
                f"{e.get('start_date', '—')} — {e.get('event_name', '—')}"
                for e in archived_events
            ]
            selected_archived_label = st.selectbox(
                "Select archived event to restore",
                archived_labels,
                key="restore_event_selectbox",
            )
            selected_archived_event = archived_events[
                archived_labels.index(selected_archived_label)
            ]

            if st.button("Restore Selected Event"):
                if restore_event(
                    selected_archived_event["_id"],
                    actor_user_id=current_user_doc.get("_id") if current_user_doc else None,
                    actor_email=current_user_doc.get("email") if current_user_doc else None,
                ):
                    st.session_state.restore_event_success = (
                        "Event restored successfully."
                    )
                    st.rerun()
                else:
                    st.error("Could not restore event.")
