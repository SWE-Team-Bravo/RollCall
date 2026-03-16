import streamlit as st
from datetime import datetime

from services.attendance import generate_attendance_password

st.title("Attendance Submission Page")

# Generate password once per session
if "password" not in st.session_state:
    st.session_state.password = generate_attendance_password()
    st.session_state.correctPassword = False
correctPassword = st.session_state.correctPassword

# Writes the password for testing purposes
st.info("testing password: " + password)

# Current day of the week
weekDay = datetime.now().strftime("%A")
#st.info(weekDay)

# Default message for attendance status
attendanceStatus = st.empty()
if correctPassword:
    attendanceStatus.markdown("Attendance Status: Reported")
else:
    attendanceStatus.markdown("Attendance Status: Needs Reported")

# Password submission and checking
answer = st.text_input("Password", type="password")

if st.button("Report In") and not correctPassword:
    if answer == password:
        st.success("correct password")
        st.balloons()
        st.session_state.correctPassword = True
        attendanceStatus.markdown("Attendance Status: Reported")
    else:
        st.error("wrong password")
