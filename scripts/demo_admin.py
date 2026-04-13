from datetime import datetime, timezone
from bson import ObjectId

def get_temp_cadet():

    return {
        #=== ID ===#
        "_id": str(ObjectId()),
        
        #=== Users ===#
        "username": "Demo Admin",
        "first_name": "Demo",
        "last_name": "Admin",
        "name": "Demo Admin",
        "email": "demoAdmin@rollcall.local",
        "password": "password",
        "password_hash": "password",
        "role": "cadet",
        "roles": ["cadet"],
        "created_at": datetime.now(timezone.utc),

        #=== Cadets ===#
        "user_id": str(ObjectId()),
        "rank": 100,
        "first_name": "Demo",
        "last_name": "Admin",
        "email": "demoAdmin@rollcall.local",

        #=== Events ===#

        #=== Event Assignments ===#

        #=== Attendance Records ===#

        #=== Waivers ===#

        #=== Waiver Approvals ===#

        #=== Flights ===#
    }