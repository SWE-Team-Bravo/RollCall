import streamlit as st

from utils.auth import require_role
from services.cadets import build_cadet_display_map, get_cadets_by_flight
from utils.db_schema_crud import (
    create_flight,
    delete_flight,
    get_all_flights,
    assign_cadet_to_flight,
    unassign_cadet_from_flight,
    get_cadet_by_id,
    get_user_by_id,
)

require_role("admin", "cadre")

st.title("Flight Management")

if "confirm_delete_flight_id" not in st.session_state:
    st.session_state.confirm_delete_flight_id = None
if "_success_msg" not in st.session_state:
    st.session_state["_success_msg"] = None
if st.session_state["_success_msg"]:
    st.success(st.session_state["_success_msg"])
    st.session_state["_success_msg"] = None

# ----------------------------
# Create Flight Section
# ----------------------------

cadet_display_map = build_cadet_display_map()

with st.expander("Create New Flight", expanded=False):
    with st.form("create_flight_form"):
        flight_name = st.text_input("Flight Name")
        selected_display = st.selectbox(
            "Select Commander (Cadet)",
            options=list(cadet_display_map.keys()) if cadet_display_map else [],
        )
        submitted = st.form_submit_button("Create Flight", type="primary")

    if submitted:
        selected_commander = cadet_display_map.get(selected_display)
        if flight_name and selected_commander:
            create_flight(flight_name, selected_commander)
            st.session_state["_success_msg"] = "Flight created successfully!"
            st.rerun()
        else:
            st.warning("Please fill all fields.")

st.divider()

# ----------------------------
# Existing Flights
# ----------------------------

flights = get_all_flights()

if not flights:
    st.info("No flights created yet.")
else:
    st.subheader(f"Flights ({len(flights)})")
    for flight in flights:
        flight_id = str(flight["_id"])

        commander_name = "—"
        commander_rank = ""
        commander = get_cadet_by_id(flight["commander_cadet_id"])
        if commander:
            user = get_user_by_id(commander["user_id"])
            if user:
                commander_name = (
                    f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                )
                commander_rank = commander.get("rank", "")

        cadets_in_flight = get_cadets_by_flight(flight["_id"])
        cadet_count = len(cadets_in_flight)

        with st.expander(
            f"{flight['name']}  ·  Commander: {commander_name}  ·  {cadet_count} cadet(s)"
        ):
            st.caption(
                f"Commander: {commander_name}"
                + (f" ({commander_rank})" if commander_rank else "")
            )

            st.markdown("**Assign / Reassign Cadet**")
            cadet_to_assign_display = st.selectbox(
                "Select cadet",
                options=list(cadet_display_map.keys()),
                key=f"assign_{flight_id}",
                label_visibility="collapsed",
            )
            cadet_to_assign = cadet_display_map.get(cadet_to_assign_display)
            if st.button("Assign to Flight", key=f"btn_{flight_id}"):
                if cadet_to_assign:
                    assign_cadet_to_flight(cadet_to_assign, flight["_id"])
                    st.session_state["_success_msg"] = "Cadet assigned."
                    st.rerun()

            st.markdown("**Cadets in this Flight**")
            if cadets_in_flight:
                for cadet in cadets_in_flight:
                    user = get_user_by_id(cadet["user_id"])
                    if user:
                        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                        rank = cadet.get("rank", "")
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            st.write(f"{name} ({rank})")
                        with col2:
                            if st.button("Unassign", key=f"unassign_{cadet['_id']}"):
                                unassign_cadet_from_flight(cadet["_id"])
                                st.rerun()
            else:
                st.caption("No cadets assigned yet.")

            st.divider()
            if st.session_state.confirm_delete_flight_id == flight_id:
                st.warning(f"Delete **{flight['name']}**? This cannot be undone.")
                c1, c2 = st.columns(2)
                if c1.button(
                    "Yes, delete", key=f"confirm_del_{flight_id}", type="primary"
                ):
                    delete_flight(flight["_id"])
                    st.session_state.confirm_delete_flight_id = None
                    st.rerun()
                if c2.button("Cancel", key=f"cancel_del_{flight_id}", type="secondary"):
                    st.session_state.confirm_delete_flight_id = None
                    st.rerun()
            else:
                if st.button("Delete Flight", key=f"delete_{flight_id}"):
                    st.session_state.confirm_delete_flight_id = flight_id
                    st.rerun()
