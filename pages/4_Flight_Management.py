import streamlit as st
from bson import ObjectId

from utils.db_schema_crud import (
    create_flight,
    get_all_flights,
    delete_flight,
    assign_cadet_to_flight,
    get_user_by_id,
    get_cadet_by_id,
)
from utils.db import get_collection

st.title("Flight Management")

# ----------------------------
# Helper Functions
# ----------------------------


def get_all_cadets():
    col = get_collection("cadets")
    if col is None:
        return []
    return list(col.find())


def get_cadets_by_flight(flight_id):
    col = get_collection("cadets")
    if col is None:
        return []
    return list(col.find({"flight_id": ObjectId(flight_id)}))


def build_cadet_display_map():
    """
    Returns:
        {
            "John Smith (300)": "cadet_id_string",
            ...
        }
    """
    cadets = get_all_cadets()
    display_map = {}

    for cadet in cadets:
        user = get_user_by_id(cadet["user_id"])
        if user:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            rank = cadet.get("rank", "")
            display_text = f"{name} ({rank})"
            display_map[display_text] = str(cadet["_id"])

    return display_map


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

    # Show Commander Name Instead of ID
    commander = get_cadet_by_id(flight["commander_cadet_id"])
    if commander:
        user = get_user_by_id(commander["user_id"])
        if user:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            rank = commander.get("rank", "")
            st.write(f"Commander: {name} ({rank})")

    # Assign / Reassign Cadet
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
                name = (
                    f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                )
                rank = cadet.get("rank", "")
                st.write(f"- {name} ({rank})")
    else:
        st.write("No cadets assigned yet.")

    # Delete Flight
    if st.button("Delete Flight", key=f"delete_{flight['_id']}"):
        delete_flight(flight["_id"])
        st.success("Flight deleted.")
        st.rerun()
