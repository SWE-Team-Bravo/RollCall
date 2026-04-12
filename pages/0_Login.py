import streamlit as st
from utils.auth import init_auth, get_current_user

st.set_page_config(page_title="Login: RollCall", page_icon="🪖")

authenticator = init_auth()

if st.session_state.get("authentication_status") is False:
    st.error("Incorrect username or password.")

user = get_current_user()
if user:
    st.success(
        f"Logged in as **{user['first_name']} {user['last_name']}** ({', '.join(user['roles'])})"
    )
    if st.button("Go to Home"):
        st.switch_page("Home.py")
    authenticator.logout("Logout", location="main")
