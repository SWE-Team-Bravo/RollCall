import streamlit as st
import secrets
from datetime import datetime, timedelta
import pymongo
from utils.db import get_collection  # <-- use shared db helper

#=====Database stuff=====#
def getPassword():
    pswdData = get_collection("Password")  # uses MONGODB_URI + MONGODB_DB from config

    # Checks that password collection has data
    count = pswdData.count_documents({})
    if (count > 0):
        # Grabs the most recent password
        mostrecent = pswdData.find_one(sort=[("$natural", -1)])
        
        # Check if xx time has passed
        if(datetime.now() - mostrecent["timestamp"] >= timedelta(seconds=10)): # Use timedelta(minutes=30) for
            # Creates and adds new password if set time has passed
            pswd = {"password": f"{secrets.randbelow(1000000):06}", "timestamp": datetime.now()}
            pswdData.insert_one(pswd)
    else:
        # Adds initial data to the database
        pswd = {"password": 123456, "timestamp": datetime.now()}
        pswdData.insert_one(pswd)

    return str(pswdData.find_one(sort=[("$natural", -1)])["password"])

#=====Streamlit stuff=====#

st.title("Attendance Submission Page")

# Generate password once per session
if "password" not in st.session_state:
    st.session_state.correctPassword = False
correctPassword = st.session_state.correctPassword

# Writes the password for testing purposes
st.info("testing password: " + getPassword())

# Current day of the week
weekDay = datetime.now().strftime("%A")
#st.info(weekDay)
#st.info(weekDay)

# Default message for attendance status
# Default message for attendance status
attendanceStatus = st.empty()
if correctPassword:
    attendanceStatus.markdown("Attendance Status: Reported")
else: 
    attendanceStatus.markdown("Attendance Status: Needs Reported")

# Password submission and checking
answer = st.text_input("Password", type="password")

if(st.button("Report In") and not correctPassword):
    if answer == getPassword():
        st.success("correct password")
        st.balloons()
        st.session_state.correctPassword = True
        attendanceStatus.markdown("Attendance Status: Reported")
        attendanceStatus.markdown("Attendance Status: Reported")
    else:
        st.error("wrong password")
