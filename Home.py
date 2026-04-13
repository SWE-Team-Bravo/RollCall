import streamlit as st
from utils.auth import ensure_authenticator, get_current_user, restore_session

st.set_page_config(page_title="RollCall", page_icon="🪖", layout="wide")
st.logo("static/logo.svg", size="large")
st.image("static/logo.svg", width=300)


restore_session()

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
    event_sched = st.Page("pages/6_Event_Management_CRUD.py", title="Event Management")
    fc_live_view = st.Page(
        "pages/7_Flight_Commander_Live_View.py", title="Flight Commander Live View"
    )
    cadet_attendance = st.Page(
        "pages/8_Cadet_Attendance.py", title="Cadet Attendance View"
    )
    user_management = st.Page(
        "pages/8_User_Management.py",
        title="User Management",
    )
    account_settings = st.Page(
        "pages/9_Account_Settings.py",
        title="Account Settings",
    )
    modify_attendance = st.Page(
        "pages/10_Commander_Attendance.py", title="Modify Attendance"
    )
    at_risk_report = st.Page("pages/11_At_Risk_Cadets.py", title="At-Risk Cadet Report")
    event_code_admin = st.Page(
        "pages/11_Event_Code_Admin.py", title="Event Code Generator"
    )

    # Use session state to save the current role then use the dropdown 
    # separatly to change the shown role

    # Allows viewing of all roles in the admin page
    if "view_role" not in st.session_state:
        st.session_state.view_role = roles

    # Dropdown for admin page that toggles role views
    if "admin" in roles:
        choice = st.sidebar.selectbox("Select Role", ["admin", "cadre", "flight commander", "cadet"])
        if choice == "admin":
            st.session_state.view_role = {"admin"}
        elif choice == "cadre":
            st.session_state.view_role = {"cadre"}
        elif choice == "flight commander":
            st.session_state.view_role = {"flight commander"}
        elif choice == "cadet":
            st.session_state.view_role = {"cadet"}

    if st.session_state.view_role & {"admin", "cadre"}:
        pages = [
            dashboard,
            cadets,
            flight_mgmt,
            waiver_review,
            event_sched,
            modify_attendance,
            at_risk_report,
            event_code_admin,
        ]
        if "admin" in st.session_state.view_role:
            pages.append(user_management)
    elif "flight_commander" in roles:
        pages = [dashboard, fc_live_view, attendance, waiver_review, at_risk_report, event_code_admin]
    elif "cadet" in roles:
        pages = [attendance, waivers, cadet_attendance]
    else:
        pages = []

    pages.append(account_settings)

    if not pages:
        pages = [login]

    pg = st.navigation(pages)

    if "authenticator" not in st.session_state:
        ensure_authenticator()
    authenticator = st.session_state.get("authenticator")
    if authenticator:
        with st.sidebar:
            authenticator.logout("Logout", location="sidebar")

pg.run()
