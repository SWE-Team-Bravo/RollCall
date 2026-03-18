import streamlit as st
from utils.auth import get_current_user

st.set_page_config(page_title="RollCall", page_icon="🪖", layout="wide")

user = get_current_user()

login = st.Page("pages/0_Login.py", title="Login", icon="🔑")

if not user:
    pg = st.navigation([login])
else:
    roles = set(user["roles"])

    dashboard = st.Page("pages/1_Dashboard.py", title="Dashboard")
    attendance = st.Page("pages/2_Attendance_Submission.py", title="Attendance")
    cadets = st.Page("pages/3_Cadets.py", title="Cadets")
    flight_mgmt = st.Page("pages/4_Flight_Management.py", title="Flight Management")
    waivers = st.Page("pages/5_Waivers.py", title="Waivers")
    waiver_review = st.Page("pages/6_Waiver_Review.py", title="Waiver Review")
    event_sched = st.Page("pages/6_Event_Schedule_Config.py", title="Event Schedule")
    cadet_attendance = st.Page(
        "pages/8_Cadet_Attendance.py", title="Cadet Attendance View"
    )

    if roles & {"admin", "cadre"}:
        pages = [dashboard, attendance, cadets, flight_mgmt, waiver_review, event_sched]
    elif "flight_commander" in roles:
        pages = [dashboard, attendance, waiver_review]
    elif "cadet" in roles:
        pages = [attendance, waivers, cadet_attendance]
    else:
        pages = [login]

    authenticator = st.session_state.get("authenticator")
    if authenticator:
        with st.sidebar:
            authenticator.logout("Logout", location="sidebar")

    pg = st.navigation(pages)

pg.run()
