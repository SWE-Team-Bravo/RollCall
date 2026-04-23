import streamlit as st
from services.admin_users import confirm_destructive_action
from utils.auth import require_role
from services.cadets import build_cadet_display_map

from services.flight_management import (
    assign_selected_cadets_to_flight,
    get_assignment_table,
    get_cadet_rows_by_id,
    get_commander_member_table,
    get_flight_commander_details,
    get_flight_management_cadet_rows,
    get_flight_member_table,
    get_selectable_member_ids,
    has_selected_assigned_cadets,
    get_member_selection_table,
    get_selected_cadet_ids,
    unassign_selected_cadets,
)

from utils.db_schema_crud import (
    create_flight,
    delete_flight,
    get_all_flights,
    unassign_all_cadets_from_flight,
)

require_role("admin", "cadre")

st.title("Flight Management")

if "confirm_delete_flight_id" not in st.session_state:
    st.session_state.confirm_delete_flight_id = None
if "create_flight_success" not in st.session_state:
    st.session_state.create_flight_success = None
if "delete_flight_success" not in st.session_state:
    st.session_state.delete_flight_success = None
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


def get_assign_selection_key(flight_id: str) -> str:
    return f"selected_assign_cadet_ids_{flight_id}"


def get_member_selection_key(flight_id: str) -> str:
    return f"selected_member_cadet_ids_{flight_id}"


def get_show_assigned_key(flight_id: str) -> str:
    return f"show_assigned_cadets_{flight_id}"


def set_member_selection(flight_id: str, selected_cadet_ids: list[str]) -> None:
    st.session_state[get_member_selection_key(flight_id)] = selected_cadet_ids
    keep_flight_expanded(flight_id)


def clear_flight_table_state(flight_id: str) -> None:
    for key in (
        f"assign_table_{flight_id}",
        f"members_table_{flight_id}",
        f"assign_search_{flight_id}",
        get_show_assigned_key(flight_id),
        get_assign_selection_key(flight_id),
        get_member_selection_key(flight_id),
    ):
        st.session_state.pop(key, None)


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
if st.session_state.delete_flight_success:
    st.success(st.session_state.delete_flight_success)
    st.session_state.delete_flight_success = None

st.divider()

# ----------------------------
# Existing Flights
# ----------------------------

flights = get_all_flights()
cadet_rows = get_flight_management_cadet_rows()
cadet_rows_by_id = get_cadet_rows_by_id(cadet_rows)
rendered_feedback = False

if not flights:
    st.info("No flights created yet.")
else:
    st.subheader(f"Flights ({len(flights)})")
    for flight in flights:
        flight_id = str(flight["_id"])

        commander_name, commander_rank = get_flight_commander_details(flight)
        commander_table = get_commander_member_table(flight)
        members_table, member_cadet_ids = get_flight_member_table(cadet_rows, flight)
        cadet_count = len(get_selectable_member_ids(member_cadet_ids))

        expander_label = f"{flight['name']}  ·  Commander: {commander_name}  ·  {cadet_count} cadet(s)"
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

            assign_selection_key = get_assign_selection_key(flight_id)
            member_selection_key = get_member_selection_key(flight_id)
            show_assigned_key = get_show_assigned_key(flight_id)
            if assign_selection_key not in st.session_state:
                st.session_state[assign_selection_key] = []
            if member_selection_key not in st.session_state:
                st.session_state[member_selection_key] = []
            if show_assigned_key not in st.session_state:
                st.session_state[show_assigned_key] = False

            st.markdown("**Assign / Reassign Cadets**")
            search_term = st.text_input(
                "Search by cadet name or email",
                key=f"assign_search_{flight_id}",
                placeholder="Search cadets by name, email, rank, or current flight",
            ).strip()
            show_assigned = st.toggle(
                "Show cadets already in flights",
                key=show_assigned_key,
            )
            st.caption(
                "By default this table shows unassigned cadets. Searching also shows cadets from other flights."
            )
            assignment_table, assignment_cadet_ids = get_assignment_table(
                cadet_rows,
                flight_id,
                st.session_state[assign_selection_key],
                search_term,
                show_assigned,
            )
            if assignment_cadet_ids:
                with st.form(f"assign_form_{flight_id}"):
                    edited_assignments = st.data_editor(
                        assignment_table,
                        key=f"assign_table_{flight_id}",
                        column_config={
                            "Assign": st.column_config.CheckboxColumn(),
                            "Cadet": st.column_config.TextColumn(disabled=True),
                            "Rank": st.column_config.TextColumn(disabled=True),
                            "Email": st.column_config.TextColumn(disabled=True),
                            "Current Flight": st.column_config.TextColumn(
                                disabled=True
                            ),
                        },
                        hide_index=True,
                        width="stretch",
                    )
                    selected_cadet_ids = get_selected_cadet_ids(
                        edited_assignments,
                        assignment_cadet_ids,
                        "Assign",
                    )
                    is_reassigning = has_selected_assigned_cadets(
                        selected_cadet_ids,
                        cadet_rows_by_id,
                    )
                    if is_reassigning:
                        st.caption(
                            f"Selected cadets already in another flight will be unassigned and moved to {flight['name']}."
                        )
                    assign_clicked = st.form_submit_button("Assign Selected Cadets")
            else:
                st.caption("No cadets matched the current filter.")
                selected_cadet_ids = []
                assign_clicked = st.button(
                    f"Assign to {flight['name']}",
                    key=f"btn_{flight_id}",
                    disabled=True,
                )

            if assign_clicked:
                keep_flight_expanded(flight_id)
                st.session_state[assign_selection_key] = selected_cadet_ids
                level, message = assign_selected_cadets_to_flight(
                    selected_cadet_ids,
                    flight["_id"],
                    cadet_rows_by_id,
                )
                clear_flight_table_state(flight_id)
                set_flight_feedback(flight_id, level, message)
                st.rerun()

            st.markdown("**Cadets in this Flight**")
            if not commander_table.empty:
                st.dataframe(
                    commander_table,
                    hide_index=True,
                    width="stretch",
                )
            if member_cadet_ids:
                selectable_member_ids = get_selectable_member_ids(member_cadet_ids)
                controls_col1, controls_col2, _ = st.columns([1, 1.4, 5.6])
                controls_col1.button(
                    "Select All",
                    key=f"select_all_members_{flight_id}",
                    disabled=not selectable_member_ids,
                    on_click=set_member_selection,
                    args=(flight_id, selectable_member_ids),
                )
                controls_col2.button(
                    "Clear Selection",
                    key=f"clear_members_{flight_id}",
                    disabled=not st.session_state[member_selection_key],
                    on_click=set_member_selection,
                    args=(flight_id, []),
                )

                member_selection_table = get_member_selection_table(
                    members_table,
                    st.session_state[member_selection_key],
                    member_cadet_ids,
                )
                with st.form(f"members_form_{flight_id}"):
                    edited_members_table = st.data_editor(
                        member_selection_table,
                        key=f"members_table_{flight_id}",
                        column_config={
                            "Unassign": st.column_config.CheckboxColumn(),
                            "Cadet": st.column_config.TextColumn(disabled=True),
                            "Role": st.column_config.TextColumn(disabled=True),
                            "Rank": st.column_config.TextColumn(disabled=True),
                            "Email": st.column_config.TextColumn(disabled=True),
                            "Current Flight": st.column_config.TextColumn(
                                disabled=True
                            ),
                        },
                        hide_index=True,
                        width="stretch",
                    )
                    selected_member_ids = get_selected_cadet_ids(
                        edited_members_table,
                        member_cadet_ids,
                        "Unassign",
                    )
                    unassign_members_clicked = st.form_submit_button(
                        "Unassign Selected"
                    )
                if unassign_members_clicked:
                    keep_flight_expanded(flight_id)
                    st.session_state[member_selection_key] = selected_member_ids
                    level, message = unassign_selected_cadets(
                        selected_member_ids,
                        cadet_rows_by_id,
                    )
                    clear_flight_table_state(flight_id)
                    set_flight_feedback(flight_id, level, message)
                    st.rerun()
            else:
                st.caption("No cadets assigned yet beyond the commander.")

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
                    if not confirm_destructive_action(confirmation):
                        st.error("Confirmation text does not match 'DELETE'.")
                    else:
                        unassign_all_cadets_from_flight(flight["_id"])
                        delete_flight(flight["_id"])
                        st.session_state.confirm_delete_flight_id = None
                        st.session_state.delete_flight_success = (
                            "Flight deleted successfully."
                        )

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
