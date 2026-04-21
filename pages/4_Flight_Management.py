import streamlit as st

from utils.auth import require_role
from services.cadets import (
    assign_cadet_to_flight,
    build_cadet_display_map,
    get_assignable_cadet_display_map,
    get_cadets_by_flight,
)
from utils.db_schema_crud import (
    create_flight,
    delete_flight,
    get_all_flights,
    unassign_cadet_from_flight,
    unassign_all_cadets_from_flight,
    get_cadet_by_id,
    get_user_by_id,
)
from utils.names import format_full_name

require_role("admin", "cadre")

st.title("Flight Management")

if "confirm_delete_flight_id" not in st.session_state:
    st.session_state.confirm_delete_flight_id = None
if "create_flight_success" not in st.session_state:
    st.session_state.create_flight_success = None
if "flight_feedback" not in st.session_state:
    st.session_state.flight_feedback = None
if "expanded_flight_ids" not in st.session_state:
    st.session_state.expanded_flight_ids = []


def keep_flight_expanded(flight_id: str) -> None:
    expanded_ids = set(st.session_state.expanded_flight_ids)
    expanded_ids.add(flight_id)
    st.session_state.expanded_flight_ids = sorted(expanded_ids)


def forget_flight_expanded(flight_id: str) -> None:
    expanded_ids = set(st.session_state.expanded_flight_ids)
    expanded_ids.discard(flight_id)
    st.session_state.expanded_flight_ids = sorted(expanded_ids)


def set_flight_feedback(flight_id: str, level: str, message: str) -> None:
    st.session_state.flight_feedback = {
        "flight_id": flight_id,
        "level": level,
        "message": message,
    }
    keep_flight_expanded(flight_id)

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
            try:
                create_flight(flight_name, selected_commander)
                st.session_state.create_flight_success = "Flight created successfully!"
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        else:
            st.warning("Please fill all fields.")

if st.session_state.create_flight_success:
    st.success(st.session_state.create_flight_success)
    st.session_state.create_flight_success = None

st.divider()

# ----------------------------
# Existing Flights
# ----------------------------

flights = get_all_flights()
assignable_cadet_display_map = get_assignable_cadet_display_map()
rendered_feedback = False

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
                commander_name = format_full_name(user)
                commander_rank = commander.get("rank", "")

        cadets_in_flight = get_cadets_by_flight(flight["_id"])
        cadet_count = len(cadets_in_flight)

        expander_label = (
            f"{flight['name']}  ·  Commander: {commander_name}  ·  {cadet_count} cadet(s)"
        )
        force_expanded = (
            flight_id in st.session_state.expanded_flight_ids
            or st.session_state.confirm_delete_flight_id == flight_id
        )

        if force_expanded:
            expander = st.expander(expander_label, expanded=True)
        else:
            expander = st.expander(expander_label)

        with expander:
            feedback = st.session_state.flight_feedback
            if feedback and feedback.get("flight_id") == flight_id:
                level = feedback.get("level")
                message = feedback.get("message")
                if level == "success":
                    st.success(message)
                elif level == "warning":
                    st.warning(message)
                else:
                    st.error(message)
                rendered_feedback = True

            st.caption(
                f"Commander: {commander_name}"
                + (f" ({commander_rank})" if commander_rank else "")
            )

            st.markdown("**Assign / Reassign Cadet**")
            cadet_to_assign = None
            if assignable_cadet_display_map:
                cadet_to_assign_display = st.selectbox(
                    "Select cadet",
                    options=list(assignable_cadet_display_map.keys()),
                    key=f"assign_{flight_id}",
                    label_visibility="collapsed",
                )
                cadet_to_assign = assignable_cadet_display_map.get(cadet_to_assign_display)
                assign_clicked = st.button("Assign to Flight", key=f"btn_{flight_id}")
            else:
                st.caption("No assignable cadets are available.")
                assign_clicked = st.button(
                    "Assign to Flight",
                    key=f"btn_{flight_id}",
                    disabled=True,
                )

            if assign_clicked:
                keep_flight_expanded(flight_id)
                if cadet_to_assign:
                    try:
                        assign_cadet_to_flight(cadet_to_assign, flight["_id"])
                        set_flight_feedback(flight_id, "success", "Cadet assigned.")
                        st.rerun()
                    except ValueError as e:
                        set_flight_feedback(flight_id, "error", str(e))
                        st.rerun()

            st.markdown("**Cadets in this Flight**")
            if cadets_in_flight:
                for cadet in cadets_in_flight:
                    user = get_user_by_id(cadet["user_id"])
                    if user:
                        name = format_full_name(user)
                        rank = cadet.get("rank", "")
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            st.write(f"{name} ({rank})")
                        with col2:
                            if st.button("Unassign", key=f"unassign_{cadet['_id']}"):
                                unassign_cadet_from_flight(cadet["_id"])
                                set_flight_feedback(
                                    flight_id,
                                    "success",
                                    "Cadet unassigned.",
                                )
                                st.rerun()
            else:
                st.caption("No cadets assigned yet.")

            st.divider()
            if st.session_state.confirm_delete_flight_id == flight_id:
                if cadet_count > 0:
                    st.warning(
                        f"Type DELETE below to permanently delete **{flight['name']}**. "
                        f"{cadet_count} cadet(s) will be unassigned."
                    )
                else:
                    st.warning(
                        f"Type DELETE below to permanently delete **{flight['name']}**."
                    )
                confirmation = st.text_input(
                    "Confirm delete", key=f"confirm_input_{flight_id}"
                )
                c1, c2 = st.columns(2)
                if c1.button(
                    "Confirm Delete", key=f"confirm_del_{flight_id}", type="primary"
                ):
                    if confirmation.strip() != "DELETE":
                        st.error("Confirmation text does not match 'DELETE'.")
                    else:
                        unassign_all_cadets_from_flight(flight["_id"])
                        delete_flight(flight["_id"])
                        st.session_state.confirm_delete_flight_id = None
                        forget_flight_expanded(flight_id)
                        st.rerun()
                if c2.button("Cancel", key=f"cancel_del_{flight_id}"):
                    st.session_state.confirm_delete_flight_id = None
                    keep_flight_expanded(flight_id)
                    st.rerun()
            else:
                if st.button("Delete Flight", key=f"delete_{flight_id}"):
                    st.session_state.confirm_delete_flight_id = flight_id
                    keep_flight_expanded(flight_id)
                    st.rerun()

if rendered_feedback:
    st.session_state.flight_feedback = None
