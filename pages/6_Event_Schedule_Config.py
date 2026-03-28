import streamlit as st

from services.event_config import get_event_config, save_event_config
from utils.auth import require_role

require_role("admin", "cadre")

st.title("Event Schedule Configuration")

config = get_event_config()

days_of_week = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday",
]

pt_days = st.multiselect(
    "Select PT Days",
    days_of_week,
    default=config.get("pt_days", []),
)

llab_days = st.multiselect(
    "Select LLAB Days",
    days_of_week,
    default=config.get("llab_days", []),
)

if st.button("Save Configuration"):
    if save_event_config(pt_days, llab_days):
        st.success("Configuration saved successfully!")
    else:
        st.error("Database unavailable — could not save configuration.")
