import smtplib
import pymongo
from email.message import EmailMessage

# Email parameters
msg = EmailMessage()
msg["Subject"] = "Python Test"
msg["From"] = "charlesdgale@gmail.com"
msg["To"] = "cgale2@kent.edu"

# Mongo client object with connection URL
myclient = pymongo.MongoClient("mongodb://localhost:27017")

# The actual database
mydb = myclient["rollcall"]

# Query for filtering
myquery = {"decision": "approved"}

# Print all items in collection
mycol = mydb["waiver_approvals"]
for x in mycol.find(myquery):
    # Email body
    msg.set_content(str(x))

    # Send email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("charlesdgale@gmail.com", "") # Put your own code in the empty ""
        smtp.send_message(msg)