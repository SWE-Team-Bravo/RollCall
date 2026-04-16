from datetime import datetime, timedelta, timezone
from bson import ObjectId

def get_temp_cadet():
    # IDs
    cadet_id = str(ObjectId())
    user_id  = str(ObjectId())
    event_id = str(ObjectId())

    return {
        #=== ID ===#
        "_id": cadet_id,
        
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
        "user_id": user_id,
        "rank": 100,
        "first_name": "Demo",
        "last_name": "Admin",
        "email": "demoAdmin@rollcall.local",

        #=== Events ===#
        "event_name": "Demo LLAB 1",
        "event_type": "lab",
        "start_date": datetime.now(timezone.utc) - timedelta(days=2),
        "end_date": datetime.now(timezone.utc) - timedelta(days=2) + timedelta(hours=1.5),
        "created_by_user_id": user_id,
        "created_at": datetime.now(timezone.utc),

        #=== Event Assignments ===#

        #=== Attendance Records ===#
        "records": [
            {
                "event_id": event_id,
                "cadet_id": cadet_id,
                "status": "absent",
                "recorded_by_user_id": user_id,
                "created_at": datetime.now(timezone.utc),
            }
        ],

        #=== Waivers ===#


        #=== Waiver Approvals ===#


        #=== Flights ===#

    }
