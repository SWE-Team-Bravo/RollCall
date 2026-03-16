import streamlit as st
import os

from utils.auth import require_role
from utils.db import get_db

require_role("admin", "flight_commander")

st.title("Event Schedule Configuration")

# --- Connect to DB ---
db = get_db()

# --- Load Existing Config ---
config = db.event_config.find_one({})

if not config:
    db.event_config.insert_one({
        "pt_days": ["Monday", "Tuesday", "Thursday"],
        "llab_days": ["Friday"]
    })
    config = db.event_config.find_one({})

days_of_week = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

pt_days = st.multiselect(
    "Select PT Days",
    days_of_week,
    default=config.get("pt_days", [])
)

llab_days = st.multiselect(
    "Select LLAB Days",
    days_of_week,
    default=config.get("llab_days", [])
)

if st.button("Save Configuration"):
    db.event_config.update_one(
        {},
        {"$set": {"pt_days": pt_days, "llab_days": llab_days}}
    )
    st.success("Configuration saved successfully!")
