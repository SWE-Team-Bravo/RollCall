from __future__ import annotations

from datetime import datetime, timezone

import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

from services.attendance import (
    is_already_checked_in,
    is_within_checkin_window,
    is_within_geofence,
)
from services.event_config import get_checkin_window_minutes
from services.cadet_attendance import get_cadet_flight_label, load_cadet_flights
from services.event_codes import validate_code
from utils.audit_log import log_checkin_attempt
from utils.auth import get_current_user, require_auth
from utils.auth_logic import user_has_any_role
from utils.db_schema_crud import (
    create_attendance_record,
    get_attendance_by_cadet,
    get_cadet_by_user_id,
    get_event_by_id,
    get_user_by_email,
)


require_auth()
st.title("Attendance Submission")

current_user = get_current_user()
assert current_user is not None

user = get_user_by_email(str(current_user.get("email", "") or "").strip())
if not user:
    st.error("Could not find your account.")
    st.stop()
assert user is not None

cadet = get_cadet_by_user_id(user["_id"])
if not cadet:
    if user_has_any_role(current_user, ["admin"]):
        st.info(
            "Admin accounts do not have a cadet profile. Attendance submission is for cadets only."
        )
    else:
        st.error(
            "No cadet profile is linked to your account. "
            "If you are a cadet, contact your cadre to have a profile created."
        )
    st.stop()
assert cadet is not None

cadet_id = cadet["_id"]

first = str(current_user.get("first_name", "") or "").strip()
last = str(current_user.get("last_name", "") or "").strip()
rank = str(cadet.get("rank", "") or "").strip()
flights = load_cadet_flights(cadet)
flight_label = get_cadet_flight_label(cadet, flights)
name_parts = [p for p in [rank, first, last] if p]
st.caption(f"Checking in as **{' '.join(name_parts)}** - Flight: {flight_label}")
st.divider()

# hide that
st.markdown(
    "<style>.st-key-geo_checkin{height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden}</style>",
    unsafe_allow_html=True,
)
_location = get_geolocation(component_key="geo_checkin")
_coords = _location.get("coords") if isinstance(_location, dict) else None
_has_coords = isinstance(_coords, dict)

if _has_coords:
    st.caption("Location detected")
else:
    st.caption("Location unavailable")


st.subheader("Enter your 6-digit event code")

code = st.text_input(
    "Event code",
    max_chars=6,
    placeholder="000000",
    label_visibility="collapsed",
)

code_clean = code.strip()

event_code = None
already_checked_in = False
cadet_lat: float | None = None
cadet_lon: float | None = None
geo_outside_fence = False
geo_unavailable = False
_validated_event: dict | None = None

if len(code_clean) == 6:
    event_code = validate_code(code_clean)
    if event_code is None:
        st.error("Invalid or expired code.")
    else:
        event = get_event_by_id(event_code["event_id"])
        if event:
            window = get_checkin_window_minutes()
            if not is_within_checkin_window(
                event, datetime.now(timezone.utc), window_minutes=window
            ):
                st.error(
                    f"Check-in is only available within {window} minutes of the event start time."
                )
                event_code = None
            else:
                _validated_event = event
                event_name = str(event.get("event_name", "") or "Event")
                event_type = (event.get("event_type") or "").upper()
                start = event.get("start_date")
                if hasattr(start, "strftime"):
                    date_str = start.strftime("%B %d, %Y")
                elif start:
                    date_str = str(start)[:10]
                else:
                    date_str = ""

                existing = get_attendance_by_cadet(cadet_id)
                already_checked_in = is_already_checked_in(
                    str(event_code["event_id"]), str(cadet_id), existing
                )

                if already_checked_in:
                    st.success(
                        f"You are already checked in for **{event_name}**"
                        + (f" ({event_type} - {date_str})" if date_str else "")
                        + "."
                    )
                else:
                    label = event_name
                    if event_type:
                        label += f" - {event_type}"
                    if date_str:
                        label += f" - {date_str}"
                    st.info(label)

                    # Geofence check
                    if event.get("geofence_enabled"):
                        if _has_coords:
                            cadet_lat = _coords.get("latitude")
                            cadet_lon = _coords.get("longitude")
                        if cadet_lat is not None and cadet_lon is not None:
                            within, warning = is_within_geofence(
                                event, cadet_lat, cadet_lon
                            )
                            if not within:
                                st.warning(
                                    f"Location: {warning} Check-in is still allowed."
                                )
                                geo_outside_fence = True
                        else:
                            st.warning(
                                "Could not verify your location. Check-in is still allowed."
                            )
                            geo_unavailable = True

# ── Location map — shown whenever GPS has resolved ────────────────────────────

if _has_coords:
    _lat = _coords.get("latitude")
    _lon = _coords.get("longitude")
    if _lat is not None and _lon is not None:
        _m = folium.Map(location=[_lat, _lon], zoom_start=17)
        folium.Marker(
            [_lat, _lon],
            tooltip="Your location",
            icon=folium.Icon(color="blue", icon="user", prefix="fa"),
        ).add_to(_m)

        # Overlay geofence if a validated geofence event is in scope
        if _validated_event and _validated_event.get("geofence_enabled"):
            fence_lat = _validated_event.get("geofence_lat")
            fence_lon = _validated_event.get("geofence_lon")
            radius = _validated_event.get("geofence_radius_meters", 150)
            if fence_lat is not None and fence_lon is not None:
                within, _ = is_within_geofence(_validated_event, _lat, _lon)
                folium.Circle(
                    location=[fence_lat, fence_lon],
                    radius=radius,
                    color="#00aa44" if within else "#cc0000",
                    fill=True,
                    fill_opacity=0.15,
                    tooltip="Geofence boundary",
                ).add_to(_m)
                folium.Marker(
                    [fence_lat, fence_lon],
                    tooltip="Formation location",
                    icon=folium.Icon(
                        color="green" if within else "red",
                        icon="flag",
                        prefix="fa",
                    ),
                ).add_to(_m)

        st_folium(_m, width=None, height=300, key="checkin_map")

# ── Submit ────────────────────────────────────────────────────────────────────

button_disabled = event_code is None or already_checked_in

if (
    st.button("Report In", type="primary", disabled=button_disabled)
    and event_code is not None
):
    existing = get_attendance_by_cadet(cadet_id)
    if is_already_checked_in(str(event_code["event_id"]), str(cadet_id), existing):
        st.info("You are already checked in for this event.")
    else:
        result = create_attendance_record(
            event_id=event_code["event_id"],
            cadet_id=cadet_id,
            status="present",
            recorded_by_user_id=user["_id"],
            recorded_by_roles=list(user.get("roles", [])),
            location_lat=cadet_lat,
            location_lon=cadet_lon,
            location_outside_fence=geo_outside_fence,
            location_unavailable=geo_unavailable,
        )
        if result is None:
            st.error("Database unavailable. Could not record attendance.")
        else:
            event = get_event_by_id(event_code["event_id"])
            event_name = (
                str(event.get("event_name", "") or "the event")
                if event
                else "the event"
            )
            log_checkin_attempt(
                cadet_id=cadet_id,
                outcome="success",
                event_id=event_code["event_id"],
                user_id=user["_id"],
                source="attendance_submission",
            )
            st.success(f"Checked in for **{event_name}**!")
            st.balloons()
