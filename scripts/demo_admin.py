from bson import ObjectId


def get_temp_cadet() -> dict:
    return {
        "_id": str(ObjectId()),
        "user_id": str(ObjectId()),
        "first_name": "Demo",
        "last_name": "Admin",
        "email": "admin@rollcall.local",
        "rank": "",
    }
