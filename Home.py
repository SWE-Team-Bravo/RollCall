import streamlit as st
from utils.auth import require_auth

st.set_page_config(
    page_title="RollCall",
    page_icon="🪖",
    layout="wide",
)

require_auth()

st.title("Welcome to RollCall! 🪖")
st.subheader("ROTC Attendance Tracker")
st.write("Simple, efficient, and secure attendance tracking for ROTC units.")
