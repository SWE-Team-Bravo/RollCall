from datetime import datetime, timezone

from bson import ObjectId
from pymongo.results import DeleteResult, InsertOneResult, UpdateResult

from utils.db import get_collection

# -- Users


def create_user(
    first_name: str,
    last_name: str,
    email: str,
    password_hash: str,
    roles: list[str],
) -> InsertOneResult | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.insert_one(
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password_hash": password_hash,
            "roles": roles,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_user_by_id(user_id: str | ObjectId) -> dict | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(user_id)})


def get_user_by_email(email: str) -> dict | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.find_one({"email": email})


def update_user(user_id: str | ObjectId, updates: dict) -> UpdateResult | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(user_id)}, {"$set": updates})


def delete_user(user_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(user_id)})


# -- Cadets


def create_cadet(
    user_id: str | ObjectId,
    rank: str,
    flight_id: str | ObjectId | None = None,
) -> InsertOneResult | None:
    col = get_collection("cadets")
    if col is None:
        return None

    cadet_doc = {
        "user_id": ObjectId(user_id),
        "rank": rank,
    }

    if flight_id:
        cadet_doc["flight_id"] = ObjectId(flight_id)

    return col.insert_one(cadet_doc)


def get_cadet_by_id(cadet_id: str | ObjectId) -> dict | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(cadet_id)})


def get_cadet_by_user_id(user_id: str | ObjectId) -> dict | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.find_one({"user_id": ObjectId(user_id)})


def update_cadet(cadet_id: str | ObjectId, updates: dict) -> UpdateResult | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(cadet_id)}, {"$set": updates})


def delete_cadet(cadet_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(cadet_id)})


def create_cadet_if_not_exists(
    user_id: str | ObjectId,
    rank: int = 100,  # default freshman
) -> InsertOneResult | None:
    """
    Creates a cadet profile for a user if one does not already exist.
    Rank follows ROTC level system (100, 200, 300, 400, 700, etc.)
    """
    col = get_collection("cadets")
    if col is None:
        return None

    existing = col.find_one({"user_id": ObjectId(user_id)})
    if existing:
        return None

    return col.insert_one(
        {
            "user_id": ObjectId(user_id),
            "rank": rank,
        }
    )


# -- Events


def create_event(
    event_name: str,
    event_type: str,
    start_date: datetime,
    end_date: datetime,
    created_by_user_id: str | ObjectId,
) -> InsertOneResult | None:
    col = get_collection("events")
    if col is None:
        return None
    return col.insert_one(
        {
            "event_name": event_name,
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "created_by_user_id": ObjectId(created_by_user_id),
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_event_by_id(event_id: str | ObjectId) -> dict | None:
    col = get_collection("events")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(event_id)})


def get_events_by_type(event_type: str) -> list[dict]:
    col = get_collection("events")
    if col is None:
        return []
    return list(col.find({"event_type": event_type}))


def get_events_by_creator(user_id: str | ObjectId) -> list[dict]:
    col = get_collection("events")
    if col is None:
        return []
    return list(col.find({"created_by_user_id": ObjectId(user_id)}))


def update_event(event_id: str | ObjectId, updates: dict) -> UpdateResult | None:
    col = get_collection("events")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(event_id)}, {"$set": updates})


def delete_event(event_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("events")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(event_id)})


# -- Event Assignments


def create_event_assignment(
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
    assigned_by_user_id: str | ObjectId,
) -> InsertOneResult | None:
    col = get_collection("event_assignments")
    if col is None:
        return None
    return col.insert_one(
        {
            "event_id": ObjectId(event_id),
            "cadet_id": ObjectId(cadet_id),
            "assigned_by_user_id": ObjectId(assigned_by_user_id),
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_event_assignment_by_id(assignment_id: str | ObjectId) -> dict | None:
    col = get_collection("event_assignments")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(assignment_id)})


def get_assignments_by_event(event_id: str | ObjectId) -> list[dict]:
    col = get_collection("event_assignments")
    if col is None:
        return []
    return list(col.find({"event_id": ObjectId(event_id)}))


def get_assignments_by_cadet(cadet_id: str | ObjectId) -> list[dict]:
    col = get_collection("event_assignments")
    if col is None:
        return []
    return list(col.find({"cadet_id": ObjectId(cadet_id)}))


def delete_event_assignment(assignment_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("event_assignments")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(assignment_id)})


# -- Attendance Records


def create_attendance_record(
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
    status: str,
    recorded_by_user_id: str | ObjectId,
) -> InsertOneResult | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    return col.insert_one(
        {
            "event_id": ObjectId(event_id),
            "cadet_id": ObjectId(cadet_id),
            "status": status,
            "recorded_by_user_id": ObjectId(recorded_by_user_id),
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_attendance_record_by_id(record_id: str | ObjectId) -> dict | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(record_id)})


def get_attendance_by_event(event_id: str | ObjectId) -> list[dict]:
    col = get_collection("attendance_records")
    if col is None:
        return []
    return list(col.find({"event_id": ObjectId(event_id)}))


def get_attendance_by_cadet(cadet_id: str | ObjectId) -> list[dict]:
    col = get_collection("attendance_records")
    if col is None:
        return []
    return list(col.find({"cadet_id": ObjectId(cadet_id)}))


def update_attendance_record(
    record_id: str | ObjectId, updates: dict
) -> UpdateResult | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(record_id)}, {"$set": updates})


def delete_attendance_record(record_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(record_id)})


# -- Waivers


def create_waiver(
    attendance_record_id: str | ObjectId,
    reason: str,
    status: str,
    submitted_by_user_id: str | ObjectId,
) -> InsertOneResult | None:
    col = get_collection("waivers")
    if col is None:
        return None
    return col.insert_one(
        {
            "attendance_record_id": ObjectId(attendance_record_id),
            "reason": reason,
            "status": status,
            "submitted_by_user_id": ObjectId(submitted_by_user_id),
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_waiver_by_id(waiver_id: str | ObjectId) -> dict | None:
    col = get_collection("waivers")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(waiver_id)})


def get_waiver_by_attendance_record(
    attendance_record_id: str | ObjectId,
) -> dict | None:
    col = get_collection("waivers")
    if col is None:
        return None
    return col.find_one({"attendance_record_id": ObjectId(attendance_record_id)})


def get_waivers_by_status(status: str) -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(col.find({"status": status}))


def update_waiver(waiver_id: str | ObjectId, updates: dict) -> UpdateResult | None:
    col = get_collection("waivers")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(waiver_id)}, {"$set": updates})


def delete_waiver(waiver_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("waivers")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(waiver_id)})


# -- Waiver Approvals


def create_waiver_approval(
    waiver_id: str | ObjectId,
    approver_id: str | ObjectId,
    decision: str,
    comments: str,
) -> InsertOneResult | None:
    col = get_collection("waiver_approvals")
    if col is None:
        return None
    return col.insert_one(
        {
            "waiver_id": ObjectId(waiver_id),
            "approver_id": ObjectId(approver_id),
            "decision": decision,
            "comments": comments,
            "created_at": datetime.now(timezone.utc),
        }
    )


def get_waiver_approval_by_id(approval_id: str | ObjectId) -> dict | None:
    col = get_collection("waiver_approvals")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(approval_id)})


def get_approvals_by_waiver(waiver_id: str | ObjectId) -> list[dict]:
    col = get_collection("waiver_approvals")
    if col is None:
        return []
    return list(col.find({"waiver_id": ObjectId(waiver_id)}))


def get_approvals_by_approver(approver_id: str | ObjectId) -> list[dict]:
    col = get_collection("waiver_approvals")
    if col is None:
        return []
    return list(col.find({"approver_id": ObjectId(approver_id)}))


def delete_waiver_approval(approval_id: str | ObjectId) -> DeleteResult | None:
    col = get_collection("waiver_approvals")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(approval_id)})


# -- Flights


def create_flight(name: str, commander_cadet_id: str | ObjectId):
    col = get_collection("flights")
    if col is None:
        return None
    return col.insert_one(
        {
            "name": name,
            "commander_cadet_id": ObjectId(commander_cadet_id),
        }
    )


def get_all_flights():
    col = get_collection("flights")
    if col is None:
        return []
    return list(col.find())


def update_flight(flight_id: str | ObjectId, updates: dict):
    col = get_collection("flights")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(flight_id)}, {"$set": updates})


def delete_flight(flight_id: str | ObjectId):
    col = get_collection("flights")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(flight_id)})


def assign_cadet_to_flight(cadet_id: str | ObjectId, flight_id: str | ObjectId):
    col = get_collection("cadets")
    if col is None:
        return None

    return col.update_one(
        {"_id": ObjectId(cadet_id)},
        {"$set": {"flight_id": ObjectId(flight_id)}},
    )
