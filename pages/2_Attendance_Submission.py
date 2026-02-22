import streamlit as st
import random
import secrets
from datetime import datetime

st.title("Attendance Submission Page")

# Generate variables once per session
if "password" not in st.session_state:
    st.session_state.password = f"{secrets.randbelow(1000000):06}"
    st.session_state.correctPassword = False
password = st.session_state.password
correctPassword = st.session_state.correctPassword

# Writes the password for testing puprposes
st.info("testing password: " + password)

# Current day of the week
weekDay = datetime.now().strftime("%A")
st.info(weekDay)

# Default message for attendanc status
attendanceStatus = st.empty()
if correctPassword:
    attendanceStatus.markdown("Attendance Staus: Reported")
else: 
    attendanceStatus.markdown("Attendance Staus: Needs Reported")

# Passord submission and checking and displays attendance status
answer = st.text_input("Password", type="password")

if(st.button("Report In") and not correctPassword):
    if answer == password:
        st.success("correct password")
        st.balloons()
        st.session_state.correctPassword = True
        attendanceStatus.markdown("Attendance Staus: Reported")
    else:
        st.error("wrong password")
