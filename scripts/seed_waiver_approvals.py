import pymongo

# Add testing data to the collection for use in emails.py

mylist = [
    {"waiver_id": "1", "approver_id": "1", "decision": "approved", "comments": "N/A"},
    {"waiver_id": "2", "approver_id": "2", "decision": "dissaproved", "comments": "N/A"},
    {"waiver_id": "3", "approver_id": "3", "decision": "dissaproved", "comments": "N/A"},
    {"waiver_id": "4", "approver_id": "4", "decision": "approved", "comments": "N/A"},
    {"waiver_id": "5", "approver_id": "5", "decision": "approved", "comments": "N/A"},
    {"waiver_id": "6", "approver_id": "6", "decision": "dissaproved", "comments": "N/A"},
    {"waiver_id": "7", "approver_id": "7", "decision": "approved", "comments": "N/A"},
    {"waiver_id": "8", "approver_id": "8", "decision": "dissaproved", "comments": "N/A"},
    {"waiver_id": "9", "approver_id": "9", "decision": "approved", "comments": "N/A"}
]

myclient = pymongo.MongoClient("mongodb://localhost:27017")

# The actual database
mydb = myclient["rollcall"]


# Add all items to collection
mycol = mydb["waiver_approvals"]
x = mycol.insert_many(mylist)
