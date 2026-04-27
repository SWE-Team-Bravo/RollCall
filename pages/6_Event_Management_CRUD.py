import folium
import streamlit as st
from datetime import date, time
from typing import cast
from streamlit_folium import st_folium
from services.event_config import (
    DEFAULT_CHECKIN_WINDOW_MINUTES,
    DEFAULT_LLAB_THRESHOLD,
    DEFAULT_PT_THRESHOLD,
    DEFAULT_TIMEZONE,
    DEFAULT_WAIVER_REMINDER_DAYS,
    get_default_timezone,
    get_event_config,
    save_event_config,
)
from services.events import (
    archive_event,
    bulk_create_events,
    create_event,
    get_all_events,
    get_timezone_options,
    preview_semester_schedule,
    restore_event,
    update_event,
)
from utils.auth import require_role, get_current_user_doc
from utils.date_range import parse_streamlit_date_range
from utils.st_helpers import require

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
if "edit_geofence_init_id" not in st.session_state:
    st.session_state.edit_geofence_init_id = None
if "gen_holidays" not in st.session_state:
    st.session_state.gen_holidays = []
if "gen_preview" not in st.session_state:
    st.session_state.gen_preview = None
if "gen_preview_params" not in st.session_state:
    st.session_state.gen_preview_params = None
if "gen_schedule_success" not in st.session_state:
    st.session_state.gen_schedule_success = None

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
TZ_OPTIONS = get_timezone_options()
_configured_tz = get_default_timezone()
_configured_tz_index = (
    TZ_OPTIONS.index(_configured_tz) if _configured_tz in TZ_OPTIONS else 0
)

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

    st.divider()

    _cfg_tz_default = config.get("default_timezone", DEFAULT_TIMEZONE)
    _cfg_tz_index = (
        TZ_OPTIONS.index(_cfg_tz_default) if _cfg_tz_default in TZ_OPTIONS else 0
    )
    default_timezone = st.selectbox(
        "Default Timezone for Events",
        TZ_OPTIONS,
        index=_cfg_tz_index,
        key="cfg_default_timezone",
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
            default_timezone,
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
# SECTION 1b — Generate Semester Schedule
# =============================================================================

with st.expander("Generate Semester Schedule", expanded=False):
    st.markdown(
        "Bulk-create PT and LLAB events for a full semester. "
        "Events are named automatically (e.g. *PT Mon Aug 25 2025*)."
    )

    import pandas as _pd

    _pt_days = config.get("pt_days", ["Monday", "Tuesday", "Thursday"])
    _llab_days = config.get("llab_days", ["Friday"])

    # ── Date range picker ─────────────────────────────────────────────────────
    _today = date.today()
    _gen_range = st.date_input(
        "Semester date range",
        value=(_today, _today),
        min_value=_today,
        help="Select the first and last day of the semester.",
        key="gen_date_range",
    )

    _parsed_start, _parsed_end, _range_complete = parse_streamlit_date_range(
        _gen_range, _today, _today
    )
    _gen_start: date | None = _parsed_start if _range_complete else None
    _gen_end: date | None = _parsed_end if _range_complete else None

    st.divider()

    # ── Times ─────────────────────────────────────────────────────────────────
    gc1, gc2 = st.columns(2)
    with gc1:
        st.caption("PT event times")
        gen_pt_start = st.time_input(
            "PT Start Time", value=time(6, 0), key="gen_pt_start"
        )
        gen_pt_end = st.time_input("PT End Time", value=time(7, 0), key="gen_pt_end")
    with gc2:
        st.caption("LLAB event times")
        gen_llab_start = st.time_input(
            "LLAB Start Time", value=time(6, 0), key="gen_llab_start"
        )
        gen_llab_end = st.time_input(
            "LLAB End Time", value=time(9, 0), key="gen_llab_end"
        )

    gen_tz = st.selectbox(
        "Timezone", TZ_OPTIONS, index=_configured_tz_index, key="gen_tz"
    )

    st.divider()

    # ── Holiday / break picker ────────────────────────────────────────────────
    st.markdown("**Holidays / breaks to skip**")
    st.caption(
        "Add individual dates that should be skipped (e.g. federal holidays, spring break days)."
    )

    _add_holiday = st.date_input(
        "Add a date to skip",
        value=None,
        key="gen_holiday_picker",
    )
    hc1, hc2 = st.columns([1, 3])
    if hc1.button("Add date", key="gen_add_holiday"):
        if _add_holiday and _add_holiday not in st.session_state.gen_holidays:
            st.session_state.gen_holidays.append(_add_holiday)
            st.session_state.gen_preview = None
            st.rerun()

    if st.session_state.gen_holidays:
        _sorted_holidays = sorted(st.session_state.gen_holidays)
        for _hd in _sorted_holidays:
            hrow1, hrow2 = st.columns([3, 1])
            hrow1.write(_hd.strftime("%A, %B %d %Y"))
            if hrow2.button("Remove", key=f"gen_rm_{_hd}"):
                st.session_state.gen_holidays.remove(_hd)
                st.session_state.gen_preview = None
                st.rerun()
    else:
        st.caption("No holidays added.")

    st.divider()

    gen_use_geofence = st.checkbox(
        "Enable geofence check-in verification for all semester events",
        key="gen_use_geofence",
    )
    if gen_use_geofence:
        st.caption(
            "Click the map to set the geofence center. All events in this semester will share this location."
        )
        _glat = st.session_state.get("gen_geofence_lat")
        _glon = st.session_state.get("gen_geofence_lon")
        _grad = st.session_state.get("gen_geofence_radius", 150)
        _ghas_pin = _glat is not None and _glon is not None
        _gcenter: list[float] = (
            [cast(float, _glat), cast(float, _glon)]
            if _ghas_pin
            else [41.1548, -81.3414]
        )
        _gzoom = 16 if _ghas_pin else 15
        _gm = folium.Map(location=_gcenter, zoom_start=_gzoom)
        if _ghas_pin:
            _gloc: list[float] = [cast(float, _glat), cast(float, _glon)]
            folium.Circle(
                location=_gloc,
                radius=_grad,
                color="#0066cc",
                fill=True,
                fill_opacity=0.2,
            ).add_to(_gm)
            folium.Marker(_gloc, tooltip="Geofence center").add_to(_gm)
        _gmap_data = st_folium(_gm, width=None, height=400, key="gen_geofence_map")
        if _gmap_data and _gmap_data.get("last_clicked"):
            _new_glat = _gmap_data["last_clicked"]["lat"]
            _new_glon = _gmap_data["last_clicked"]["lng"]
            if _new_glat != _glat or _new_glon != _glon:
                st.session_state.gen_geofence_lat = _new_glat
                st.session_state.gen_geofence_lon = _new_glon
                st.rerun()
        if _glat is not None:
            st.caption(f"Center: {_glat:.6f}, {_glon:.6f}")
        else:
            st.caption("No location selected yet — click the map.")
        st.number_input(
            "Radius (meters)",
            min_value=50,
            max_value=1000,
            value=_grad,
            step=25,
            key="gen_geofence_radius",
        )

    st.divider()

    _cur_params = {
        "range": (_gen_start, _gen_end),
        "pt_start": gen_pt_start,
        "pt_end": gen_pt_end,
        "llab_start": gen_llab_start,
        "llab_end": gen_llab_end,
        "holidays": tuple(sorted(st.session_state.gen_holidays)),
    }
    if (
        st.session_state.gen_preview is not None
        and st.session_state.gen_preview_params != _cur_params
    ):
        st.session_state.gen_preview = None
        st.session_state.gen_preview_params = None
        st.rerun()

    # ── Preview ───────────────────────────────────────────────────────────────
    if st.button(
        "Preview Schedule", key="gen_preview_btn", disabled=not _range_complete
    ):
        if _gen_start and _gen_end and _gen_end >= _gen_start:
            if gen_pt_end <= gen_pt_start:
                st.error("PT end time must be after PT start time.")
            elif gen_llab_end <= gen_llab_start:
                st.error("LLAB end time must be after LLAB start time.")
            else:
                st.session_state.gen_preview = preview_semester_schedule(
                    _gen_start,
                    _gen_end,
                    _pt_days,
                    _llab_days,
                    st.session_state.gen_holidays,
                )
                st.session_state.gen_preview_params = _cur_params
        else:
            st.error("Select a valid date range first.")

    if st.session_state.gen_preview is not None:
        _preview = st.session_state.gen_preview
        if not _preview:
            st.info(
                "No events would be created for this range with the current schedule configuration."
            )
        else:
            _pt_count = sum(1 for e in _preview if e["type"] == "PT")
            _llab_count = sum(1 for e in _preview if e["type"] == "LLAB")
            st.success(
                f"**{len(_preview)} events** will be created: "
                f"{_pt_count} PT · {_llab_count} LLAB"
            )
            _preview_df = _pd.DataFrame(
                [
                    {
                        "Date": e["date"].strftime("%Y-%m-%d"),
                        "Day": e["day"],
                        "Type": e["type"],
                    }
                    for e in _preview
                ]
            )
            st.dataframe(_preview_df, hide_index=True, width="stretch")

            # ── Generate button ───────────────────────────────────────────────
            st.warning(
                "This will create all events shown above. This cannot be undone in bulk."
            )
            if st.button("Generate Schedule", key="gen_confirm_btn", type="primary"):
                _creator_id = (
                    str(current_user_doc["_id"]) if current_user_doc else "unknown"
                )
                _start = require(_gen_start, "Select a valid date range first.")
                _end = require(_gen_end, "Select a valid date range first.")
                _gen_geo = st.session_state.get("gen_use_geofence", False)
                _created, _skipped = bulk_create_events(
                    _start,
                    _end,
                    _pt_days,
                    _llab_days,
                    gen_pt_start,
                    gen_pt_end,
                    gen_llab_start,
                    gen_llab_end,
                    gen_tz,
                    st.session_state.gen_holidays,
                    _creator_id,
                    geofence_enabled=_gen_geo,
                    geofence_lat=st.session_state.get("gen_geofence_lat")
                    if _gen_geo
                    else None,
                    geofence_lon=st.session_state.get("gen_geofence_lon")
                    if _gen_geo
                    else None,
                    geofence_radius_meters=int(
                        st.session_state.get("gen_geofence_radius", 150)
                    ),
                    actor_user_id=current_user_doc.get("_id")
                    if current_user_doc
                    else None,
                    actor_email=current_user_doc.get("email")
                    if current_user_doc
                    else None,
                )
                st.session_state.gen_preview = None
                st.session_state.gen_preview_params = None
                st.session_state.gen_holidays = []
                st.session_state.gen_geofence_lat = None
                st.session_state.gen_geofence_lon = None
                st.session_state.gen_schedule_success = (
                    f"Created {_created} events ({_skipped} holiday dates skipped)."
                )
                st.rerun()

    if st.session_state.gen_schedule_success:
        st.success(st.session_state.gen_schedule_success)
        st.session_state.gen_schedule_success = None

st.divider()

# =============================================================================
# SECTION 2 — Create New Event
# =============================================================================

with st.expander("Create One-Off Event", expanded=False):
    # ── Geofence picker (must live outside st.form so the map widget works) ──
    create_use_geofence = st.checkbox(
        "Enable geofence check-in verification", key="create_use_geofence"
    )
    if create_use_geofence:
        st.caption(
            "Click the map to set the geofence center. Cadets outside this radius will be warned but not blocked."
        )
        _clat = st.session_state.get("create_geofence_lat")
        _clon = st.session_state.get("create_geofence_lon")
        _crad = st.session_state.get("create_geofence_radius", 150)
        _has_pin = _clat is not None and _clon is not None
        _center: list[float] = (
            [cast(float, _clat), cast(float, _clon)]
            if _has_pin
            else [41.1548, -81.3414]
        )
        _zoom = 16 if _has_pin else 15
        _m = folium.Map(location=_center, zoom_start=_zoom)
        if _has_pin:
            _loc: list[float] = [cast(float, _clat), cast(float, _clon)]
            folium.Circle(
                location=_loc,
                radius=_crad,
                color="#0066cc",
                fill=True,
                fill_opacity=0.2,
            ).add_to(_m)
            folium.Marker(_loc, tooltip="Geofence center").add_to(_m)
        _map_data = st_folium(_m, width=None, height=400, key="create_geofence_map")
        if _map_data and _map_data.get("last_clicked"):
            _new_lat = _map_data["last_clicked"]["lat"]
            _new_lon = _map_data["last_clicked"]["lng"]
            if _new_lat != _clat or _new_lon != _clon:
                st.session_state.create_geofence_lat = _new_lat
                st.session_state.create_geofence_lon = _new_lon
                st.rerun()
        if _clat is not None:
            st.caption(f"Center: {_clat:.6f}, {_clon:.6f}")
        else:
            st.caption("No location selected yet — click the map.")
        st.number_input(
            "Radius (meters)",
            min_value=50,
            max_value=1000,
            value=_crad,
            step=25,
            key="create_geofence_radius",
        )

    with st.form("create_event_form"):
        event_name = st.text_input("Event Name", placeholder="e.g. Week 3 PT")

        c1, c2 = st.columns(2)
        start_date = c1.date_input(
            "Start Date", value=date.today(), min_value=date.today()
        )
        start_time = c1.time_input("Start Time", value=time(6, 0))
        end_date = c2.date_input("End Date", value=date.today(), min_value=date.today())
        end_time = c2.time_input("End Time", value=time(7, 0))
        tz_name = st.selectbox("Timezone", TZ_OPTIONS, index=_configured_tz_index)

        auto_type = infer_event_type(start_date, config)
        type_options = ["pt", "lab"]
        default_index = (
            type_options.index(auto_type) if auto_type in type_options else 0
        )

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
        elif end_date == start_date and end_time <= start_time:
            st.error("End time must be after start time.")
        else:
            creator_id = str(current_user_doc["_id"]) if current_user_doc else "unknown"
            _geo_enabled = st.session_state.get("create_use_geofence", False)
            if create_event(
                event_name.strip(),
                event_type,
                start_date,
                end_date,
                creator_id,
                tz_name,
                _geo_enabled,
                st.session_state.get("create_geofence_lat") if _geo_enabled else None,
                st.session_state.get("create_geofence_lon") if _geo_enabled else None,
                int(st.session_state.get("create_geofence_radius", 150)),
                start_time,
                end_time,
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
                    "Start": e.get("_display_start", "—"),
                    "End": e.get("_display_end", "—"),
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
            f"{e.get('_display_start', '—')} — {e.get('event_name', '—')}"
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
            # Seed geofence session state from event data when first opening this edit
            if st.session_state.edit_geofence_init_id != st.session_state.edit_event_id:
                st.session_state.edit_use_geofence = selected_edit_event.get(
                    "geofence_enabled", False
                )
                st.session_state.edit_geofence_lat = selected_edit_event.get(
                    "geofence_lat"
                )
                st.session_state.edit_geofence_lon = selected_edit_event.get(
                    "geofence_lon"
                )
                st.session_state.edit_geofence_radius = selected_edit_event.get(
                    "geofence_radius_meters", 150
                )
                st.session_state.edit_geofence_init_id = st.session_state.edit_event_id

            # ── Geofence picker (outside form) ────────────────────────────────
            edit_use_geofence = st.checkbox(
                "Enable geofence check-in verification",
                value=st.session_state.get("edit_use_geofence", False),
                key="edit_use_geofence",
            )
            if edit_use_geofence:
                st.caption("Click the map to update the geofence center.")
                _elat = st.session_state.get("edit_geofence_lat")
                _elon = st.session_state.get("edit_geofence_lon")
                _erad = st.session_state.get("edit_geofence_radius", 150)
                _ehas_pin = _elat is not None and _elon is not None
                _ecenter: list[float] = (
                    [cast(float, _elat), cast(float, _elon)]
                    if _ehas_pin
                    else [41.1548, -81.3414]
                )
                _ezoom = 16 if _ehas_pin else 15
                _em = folium.Map(location=_ecenter, zoom_start=_ezoom)
                if _ehas_pin:
                    _eloc: list[float] = [cast(float, _elat), cast(float, _elon)]
                    folium.Circle(
                        location=_eloc,
                        radius=_erad,
                        color="#0066cc",
                        fill=True,
                        fill_opacity=0.2,
                    ).add_to(_em)
                    folium.Marker(_eloc, tooltip="Geofence center").add_to(_em)
                _emap_data = st_folium(
                    _em, width=None, height=400, key="edit_geofence_map"
                )
                if _emap_data and _emap_data.get("last_clicked"):
                    _new_elat = _emap_data["last_clicked"]["lat"]
                    _new_elon = _emap_data["last_clicked"]["lng"]
                    if _new_elat != _elat or _new_elon != _elon:
                        st.session_state.edit_geofence_lat = _new_elat
                        st.session_state.edit_geofence_lon = _new_elon
                        st.rerun()
                if _elat is not None:
                    st.caption(f"Center: {_elat:.6f}, {_elon:.6f}")
                else:
                    st.caption("No location selected yet — click the map.")
                st.number_input(
                    "Radius (meters)",
                    min_value=50,
                    max_value=1000,
                    value=_erad,
                    step=25,
                    key="edit_geofence_radius",
                )

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

                from zoneinfo import ZoneInfo
                from utils.datetime_utils import ensure_utc

                _event_tz = ZoneInfo(selected_edit_event.get("timezone_name", "UTC"))
                _es = (
                    ensure_utc(existing_start).astimezone(_event_tz)
                    if hasattr(existing_start, "hour")
                    else None
                )
                _ee = (
                    ensure_utc(existing_end).astimezone(_event_tz)
                    if hasattr(existing_end, "hour")
                    else None
                )
                _default_start_time = time(_es.hour, _es.minute) if _es else time(6, 0)
                _default_end_time = time(_ee.hour, _ee.minute) if _ee else time(7, 0)

                ec1, ec2 = st.columns(2)
                new_start = ec1.date_input(
                    "Start Date", value=parsed_start, key="edit_start"
                )
                new_start_time = ec1.time_input(
                    "Start Time", value=_default_start_time, key="edit_start_time"
                )
                new_end = ec2.date_input("End Date", value=parsed_end, key="edit_end")
                new_end_time = ec2.time_input(
                    "End Time", value=_default_end_time, key="edit_end_time"
                )

                existing_tz = selected_edit_event.get("timezone_name", "UTC")
                tz_index = (
                    TZ_OPTIONS.index(existing_tz)
                    if existing_tz in TZ_OPTIONS
                    else _configured_tz_index
                )
                new_tz = st.selectbox(
                    "Timezone", TZ_OPTIONS, index=tz_index, key="edit_tz"
                )

                existing_type = selected_edit_event.get("event_type", "pt")
                type_options = ["pt", "lab"]
                type_index = (
                    type_options.index(existing_type)
                    if existing_type in type_options
                    else 0
                )
                new_type = st.selectbox(
                    "Event Type", type_options, index=type_index, key="edit_type"
                )

                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Save Changes", type="primary")
                cancel = c2.form_submit_button("Cancel")

            if save:
                if not new_name.strip():
                    st.error("Event name cannot be empty.")
                elif new_end < new_start:
                    st.error("End date cannot be before start date.")
                else:
                    _egeo = st.session_state.get("edit_use_geofence", False)
                    if update_event(
                        selected_edit_event["_id"],
                        new_name.strip(),
                        new_type,
                        new_start,
                        new_end,
                        new_tz,
                        _egeo,
                        st.session_state.get("edit_geofence_lat") if _egeo else None,
                        st.session_state.get("edit_geofence_lon") if _egeo else None,
                        int(st.session_state.get("edit_geofence_radius", 150)),
                        new_start_time,
                        new_end_time,
                        actor_user_id=current_user_doc.get("_id")
                        if current_user_doc
                        else None,
                        actor_email=current_user_doc.get("email")
                        if current_user_doc
                        else None,
                    ):
                        st.session_state.edit_event_id = None
                        st.session_state.edit_geofence_init_id = None
                        st.session_state.edit_event_success = (
                            f"Event '{new_name.strip()}' updated successfully!"
                        )
                        st.rerun()
                    else:
                        st.error("Could not update event.")
            if cancel:
                st.session_state.edit_event_id = None
                st.session_state.edit_geofence_init_id = None
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
            f"{e.get('_display_start', '—')} — {e.get('event_name', '—')}"
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
                    actor_user_id=current_user_doc.get("_id")
                    if current_user_doc
                    else None,
                    actor_email=current_user_doc.get("email")
                    if current_user_doc
                    else None,
                ):
                    st.session_state.confirm_archive_event_id = None
                    st.session_state.archive_event_success = (
                        "Event archived successfully."
                    )
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
        len(archived_events) > 0 and "restore_event_selectbox" in st.session_state
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
                        "Start": e.get("_display_start", "—"),
                        "End": e.get("_display_end", "—"),
                    }
                    for e in archived_events
                ]
            )
            st.dataframe(archived_df, width="stretch", hide_index=True)

            archived_labels = [
                f"{e.get('_display_start', '—')} — {e.get('event_name', '—')}"
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
                    actor_user_id=current_user_doc.get("_id")
                    if current_user_doc
                    else None,
                    actor_email=current_user_doc.get("email")
                    if current_user_doc
                    else None,
                ):
                    st.session_state.restore_event_success = (
                        "Event restored successfully."
                    )
                    st.rerun()
                else:
                    st.error("Could not restore event.")
