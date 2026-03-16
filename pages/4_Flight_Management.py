import streamlit as st

from utils.auth import require_role
from services.cadets import build_cadet_display_map, get_cadets_by_flight
from utils.db_schema_crud import (
    assign_cadet_to_flight,
    create_flight,
    delete_flight,
    get_all_flights,
    assign_cadet_to_flight,
    unassign_cadet_from_flight,
    get_user_by_id,
    get_cadet_by_id,
    get_user_by_id,
)

require_role("admin", "cadre")

st.title("Flight Management")

# ----------------------------
# Create Flight Section
# ----------------------------

st.subheader("Create New Flight")

flight_name = st.text_input("Flight Name")

cadet_display_map = build_cadet_display_map()

selected_display = st.selectbox(
    "Select Commander (Cadet)",
    options=list(cadet_display_map.keys()) if cadet_display_map else [],
)

selected_commander = cadet_display_map.get(selected_display)

if st.button("Create Flight"):
    if flight_name and selected_commander:
        create_flight(flight_name, selected_commander)
        st.success("Flight created successfully!")
        st.rerun()
    else:
        st.warning("Please fill all fields.")


# ----------------------------
# Existing Flights
# ----------------------------

st.subheader("Existing Flights")

flights = get_all_flights()

if not flights:
    st.info("No flights created yet.")

for flight in flights:
    st.markdown("---")
    st.write(f"### {flight['name']}")

    commander = get_cadet_by_id(flight["commander_cadet_id"])
    if commander:
        user = get_user_by_id(commander["user_id"])
        if user:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            rank = commander.get("rank", "")
            st.write(f"Commander: {name} ({rank})")

    st.write("Assign / Reassign Cadet")

    cadet_display_map = build_cadet_display_map()

    cadet_to_assign_display = st.selectbox(
        f"Select Cadet for {flight['name']}",
        options=list(cadet_display_map.keys()),
        key=f"assign_{flight['_id']}",
    )

    cadet_to_assign = cadet_display_map.get(cadet_to_assign_display)

    if st.button("Assign Cadet", key=f"btn_{flight['_id']}"):
        if cadet_to_assign:
            assign_cadet_to_flight(cadet_to_assign, flight["_id"])
            st.success("Cadet assigned successfully!")
            st.rerun()


    # Show Cadets in Flight
    st.write("Cadets in this Flight:")

    cadets_in_flight = get_cadets_by_flight(flight["_id"])

    if cadets_in_flight:
        for cadet in cadets_in_flight:
            user = get_user_by_id(cadet["user_id"])

            if user:
                name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                rank = cadet.get("rank", "")

                col1, col2 = st.columns([4, 1])

                with col1:
                    st.write(f"{name} ({rank})")

                with col2:
                    if st.button("Unassign", key=f"unassign_{cadet['_id']}"):
                        unassign_cadet_from_flight(cadet["_id"])
                        st.success("Cadet unassigned from flight.")
                        st.rerun()
    else:
        st.write("No cadets assigned yet.")


    # Delete Flight
    if st.button("Delete Flight", key=f"delete_{flight['_id']}"):
        delete_flight(flight["_id"])
        st.success("Flight deleted.")
        st.rerun()
