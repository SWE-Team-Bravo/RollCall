import streamlit as st
from utils.db_schema_crud import (
    get_user_by_email,
    create_cadet,
    update_cadet,
    delete_cadet,
)
import re
import time


RANK_OPTIONS = (
    "100/150 (freshman)",
    "200/250/500 (sophomore)",
    "300 (junior)",
    "400 (senior)",
    "700/800/900 (super senior)",
)


def get_all_cadets() -> list:
    # col = get_collection("cadets")
    # if col is None:
    #     return []
    # return list(col.find())
    return [
        {
            "_id": "1",
            "user_id": "u1",
            "rank": "100/150 (freshman)",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@email.com",
        },
        {
            "_id": "2",
            "user_id": "u2",
            "rank": "200/250/500 (sophomore)",
            "first_name": "Emily",
            "last_name": "Johnson",
            "email": "emily.johnson@email.com",
        },
        {
            "_id": "3",
            "user_id": "u3",
            "rank": "300 (junior)",
            "first_name": "Michael",
            "last_name": "Brown",
            "email": "michael.brown@email.com",
        },
        {
            "_id": "4",
            "user_id": "u4",
            "rank": "400 (senior)",
            "first_name": "Sarah",
            "last_name": "Davis",
            "email": "sarah.davis@email.com",
        },
        {
            "_id": "5",
            "user_id": "u5",
            "rank": "700/800/900 (super senior)",
            "first_name": "Alex",
            "last_name": "Wilson",
            "email": "alex.wilson@email.com",
        },
    ]


def check_input(name: str, last_name: str, email: str) -> tuple[bool, str]:
    check = False
    msg = ""
    names_check = r"[A-Za-z'-]+(?: [A-Za-z'-]+)*"
    email_check = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    if name != "" and last_name != "" and email != "":
        if not re.fullmatch(names_check, name):
            msg = "Please enter a valid first name! First name can only contain letters, apostrophes, and hyphens."
        elif not re.fullmatch(names_check, last_name):
            msg = "Please enter a valid last name! Last name can only contain letters, apostrophes, and hyphens."
        elif not re.fullmatch(email_check, email):
            msg = "Please enter a valid email!"
        else:
            check = True
    else:
        msg = "Please fill all the fields!"
    return check, msg


def add_cadet_to_db(email: str, rank: str):
    user = get_user_by_email(email)
    if user is None:
        st.error("User not found!")
    else:
        create_cadet(user["_id"], rank)


def add_cadet():
    if st.session_state.show_form:
        with st.form("add_cadet"):
            cadet_name = st.text_input("Name")
            cadet_lastname = st.text_input("Last Name")
            cadet_email = st.text_input("Email")
            cadet_rank = st.selectbox("Rank", RANK_OPTIONS)

            col1, col2, spacer = st.columns([2, 2, 10])
            with col1:
                submit_button = st.form_submit_button("Submit")
            with col2:
                cancel_button = st.form_submit_button("Cancel", type="secondary")

        if cancel_button:
            st.session_state.show_form = False
            st.rerun()

        if submit_button:
            check, msg = check_input(cadet_name, cadet_lastname, cadet_email)
            if check:
                add_cadet_to_db(cadet_email, cadet_rank)
                st.session_state.show_form = False
                st.session_state.success_msg = "New cadet added successfully!"
                st.session_state.success_time = time.time()
                st.rerun()
            else:
                st.error(msg)
    else:
        if st.session_state.success_time:
            if time.time() - st.session_state.success_time < 3:
                st.success(st.session_state.success_msg)
                time.sleep(1)
                st.rerun()
            else:
                st.session_state.success_time = None
                st.session_state.success_msg = None


def edit_cadet(cadet):
    current_rank = cadet.get("rank", "")
    rank_index = RANK_OPTIONS.index(current_rank) if current_rank in RANK_OPTIONS else 0
    cadet_id = str(cadet["_id"])

    new_first = st.text_input(
        "First Name", cadet.get("first_name", ""), key=f"first_{cadet_id}"
    )
    new_last = st.text_input(
        "Last Name", cadet.get("last_name", ""), key=f"last_{cadet_id}"
    )
    new_email = st.text_input("Email", cadet.get("email", ""), key=f"email_{cadet_id}")
    new_rank = st.selectbox(
        "Rank", RANK_OPTIONS, index=rank_index, key=f"rank_{cadet_id}"
    )

    col1, col2, spacer = st.columns([2, 2, 10])
    if col1.button("Save", key=f"save_{cadet_id}"):
        check, msg = check_input(new_first, new_last, new_email)
        if check:
            update_cadet(
                cadet_id,
                {
                    "first_name": new_first,
                    "last_name": new_last,
                    "email": new_email,
                    "rank": new_rank,
                },
            )
            st.session_state.editing_id = None
            st.rerun()
        else:
            st.error(msg)

    if col2.button("Cancel", key=f"cancel_{cadet_id}"):
        st.session_state.editing_id = None
        st.rerun()


def remove_cadet(cadet):
    cadet_id = str(cadet["_id"])
    st.warning(
        f"Are you sure you want to delete {cadet.get('first_name', '')} {cadet.get('last_name', '')}?"
    )
    col1, col2, spacer = st.columns([2, 2, 10])

    if col1.button("Yes", key=f"confirm_{cadet_id}"):
        result = delete_cadet(cadet_id)
        if result and result.deleted_count > 0:
            st.session_state.confirm_delete_id = None
            st.session_state.success_msg = "Cadet deleted successfully!"
            st.session_state.success_time = time.time()
            st.rerun()
        else:
            st.error("Failed to delete cadet.")

    if col2.button("Cancel", key=f"canceldelete_{cadet_id}"):
        st.session_state.confirm_delete_id = None
        st.rerun()


def show_row(i, cadet):
    col = st.columns([1, 2, 2, 3, 3, 4])
    col[0].write(i + 1)
    col[1].write(cadet.get("first_name", ""))
    col[2].write(cadet.get("last_name", ""))
    col[3].write(cadet.get("email", ""))
    col[4].write(cadet.get("rank", ""))

    action_cols = col[5].columns(2)
    if action_cols[0].button("Edit", key=f"edit_{cadet['_id']}"):
        st.session_state.editing_id = str(cadet["_id"])
        st.rerun()
    if action_cols[1].button("Delete", key=f"delete_{cadet['_id']}"):
        st.session_state.confirm_delete_id = str(cadet["_id"])
        st.rerun()


def show_cadets():
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None

    cadets = get_all_cadets()
    if not cadets:
        st.warning("No cadets found.")
    else:
        if st.session_state.success_time:
            if time.time() - st.session_state.success_time < 3:
                st.success(st.session_state.success_msg)
                time.sleep(1)
                st.rerun()
            else:
                st.session_state.success_time = None
                st.session_state.success_msg = None

        st.subheader(f"Total Number of Cadets: {len(cadets)}")
        header = st.columns([1, 2, 2, 3, 3, 4])
        header[0].markdown("**No.**")
        header[1].markdown("**First Name**")
        header[2].markdown("**Last Name**")
        header[3].markdown("**Email**")
        header[4].markdown("**Rank**")
        header[5].markdown("**Actions**")
        st.divider()

        for i, cadet in enumerate(cadets):
            if st.session_state.editing_id == str(cadet["_id"]):
                edit_cadet(cadet)
            else:
                show_row(i, cadet)
            if st.session_state.confirm_delete_id == str(cadet["_id"]):
                remove_cadet(cadet)
            st.divider()


st.title("Cadet Management")
flag = False
try:
    get_all_cadets()
    st.success("Database connection established successfully!")
    flag = True
except Exception:
    st.warning("Database is not configured as of now.")


if flag:
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    if "success_time" not in st.session_state:
        st.session_state.success_time = None
    if "success_msg" not in st.session_state:
        st.session_state.success_msg = None

    if st.button("Add Cadet"):
        st.session_state.show_form = True
    if st.session_state.show_form or st.session_state.success_time:
        add_cadet()

    show_cadets()
