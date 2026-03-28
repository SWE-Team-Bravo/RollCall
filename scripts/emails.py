import smtplib
import pymongo
from email.message import EmailMessage

msg = EmailMessage()
msg.set_content("Hello, this is a test email from Python!")
msg["Subject"] = "Python Test"
msg["From"] = "charlesdgale@gmail.com"
msg["To"] = "cgale2@kent.edu"

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login("charlesdgale@gmail.com", "ggjl hnef nutj nswn")
    smtp.send_message(msg)

# Mongo client object with connection URL
myclient = pymongo.MongoClient("mongodb://localhost:27017")

# The actual database
mydb = myclient["rollcall"]

print(mydb.list_collection_names())

# Use this to send personalized emails when there is data in it
mycol = mydb["waiver_approvals"]
for document in mycol.find():
    print(document)