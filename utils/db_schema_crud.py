import re
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.results import DeleteResult, InsertOneResult, UpdateResult

from utils.db import get_collection
from utils.names import format_full_name
from utils.password import hash_password


def create_user(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    roles: list[str],
) -> InsertOneResult | None:
    col = get_collection("users")
    if col is None:
        return None
    return col.insert_one(
        {
            "first_name": first_name,
            "last_name": last_name,
            "name": format_full_name(
                {"first_name": first_name, "last_name": last_name}
            ),
            "email": email,
            "password_hash": hash_password(password),
            "roles": roles,
            "disabled": False,
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
    return col.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})


def get_users_by_role(role: str, *, include_disabled: bool = False) -> list[dict]:
    col = get_collection("users")
    if col is None:
        return []
    query: dict = {"roles": role}
    if not include_disabled:
        query["disabled"] = {"$ne": True}
    return list(col.find(query))


def get_users_by_ids(user_ids: list[str | ObjectId]) -> list[dict]:
    col = get_collection("users")
    if col is None:
        return []
    object_ids = [ObjectId(u_id) for u_id in user_ids]
    return list(col.find({"_id": {"$in": object_ids}}))


def get_users_by_emails(emails: list[str]) -> dict[str, dict]:
    if not emails:
        return {}
    col = get_collection("users")
    if col is None:
        return {}
    conditions = [
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}
        for email in emails
    ]
    users = col.find({"$or": conditions})
    return {u["email"].lower().strip(): u for u in users}


def get_users_by_names(names: list[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    if not names:
        return {}
    col = get_collection("users")
    if col is None:
        return {}
    conditions = [
        {
            "first_name": {"$regex": f"^{re.escape(first)}$", "$options": "i"},
            "last_name": {"$regex": f"^{re.escape(last)}$", "$options": "i"},
        }
        for first, last in names
    ]
    users = col.find({"$or": conditions})
    result: dict[tuple[str, str], dict] = {}
    for u in users:
        key = (
            u.get("first_name", "").lower().strip(),
            u.get("last_name", "").lower().strip(),
        )
        result[key] = u
    return result


def get_cadets_by_user_ids_map(user_ids: list) -> dict[str, dict]:
    if not user_ids:
        return {}
    col = get_collection("cadets")
    if col is None:
        return {}
    object_ids = [ObjectId(uid) for uid in user_ids]
    cadets = col.find({"user_id": {"$in": object_ids}})
    return {str(c["user_id"]): c for c in cadets}


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
    first_name: str,
    last_name: str,
    email: str = "",
    flight_id: str | ObjectId | None = None,
) -> InsertOneResult | None:
    col = get_collection("cadets")
    if col is None:
        return None

    cadet_doc = {
        "user_id": ObjectId(user_id),
        "rank": rank,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
    }

    if flight_id:
        cadet_doc["flight_id"] = ObjectId(flight_id)

    return col.insert_one(cadet_doc)


def get_cadet_by_id(cadet_id: str | ObjectId) -> dict | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(cadet_id)})


def get_all_cadets() -> list[dict]:
    col = get_collection("cadets")
    if col is None:
        return []
    return list(col.find())


def get_cadets_by_ids(cadet_ids: list[str | ObjectId]) -> list[dict]:
    col = get_collection("cadets")
    if col is None or not cadet_ids:
        return []
    object_ids = [ObjectId(cadet_id) for cadet_id in cadet_ids]
    return list(col.find({"_id": {"$in": object_ids}}))


def get_cadet_by_user_id(user_id: str | ObjectId) -> dict | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.find_one({"user_id": ObjectId(user_id)})


def set_at_risk_email_sent(
    cadet_id: str | ObjectId, pt_absences: int, llab_absences: int
) -> UpdateResult | None:
    col = get_collection("cadets")
    if col is None:
        return None
    return col.update_one(
        {"_id": ObjectId(cadet_id)},
        {
            "$set": {
                "at_risk_email_last_pt": pt_absences,
                "at_risk_email_last_llab": llab_absences,
            }
        },
    )


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


def get_events_by_type(
    event_type: str,
    *,
    include_archived: bool = False,
) -> list[dict]:
    col = get_collection("events")
    if col is None:
        return []
    query: dict = {"event_type": event_type}
    if not include_archived:
        query["archived"] = {"$ne": True}
    return list(col.find(query))


def get_events_by_creator(user_id: str | ObjectId) -> list[dict]:
    col = get_collection("events")
    if col is None:
        return []
    return list(col.find({"created_by_user_id": ObjectId(user_id)}))


def get_events_by_ids(event_ids: list[str | ObjectId]) -> list[dict]:
    col = get_collection("events")
    if col is None or not event_ids:
        return []
    object_ids = [ObjectId(e_id) for e_id in event_ids]
    return list(col.find({"_id": {"$in": object_ids}}))


def get_events_by_date_range(
    start: datetime,
    end: datetime,
    *,
    event_types: list[str] | None = None,
    include_archived: bool = False,
) -> list[dict]:
    """Return events whose start_date falls within [start, end] inclusive."""
    col = get_collection("events")
    if col is None:
        return []
    query: dict = {"start_date": {"$gte": start, "$lte": end}}
    if event_types:
        query["event_type"] = {"$in": list(event_types)}
    if not include_archived:
        query["archived"] = {"$ne": True}
    return list(col.find(query))


def update_event(event_id: str | ObjectId, updates: dict) -> UpdateResult | None:
    col = get_collection("events")
    if col is None:
        return None
    return col.update_one({"_id": ObjectId(event_id)}, {"$set": updates})


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
    recorded_by_roles: list[str] | None = None,
    location_lat: float | None = None,
    location_lon: float | None = None,
    location_outside_fence: bool = False,
    location_unavailable: bool = False,
) -> InsertOneResult | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    doc: dict[str, Any] = {
        "event_id": ObjectId(event_id),
        "cadet_id": ObjectId(cadet_id),
        "status": status,
        "recorded_by_user_id": ObjectId(recorded_by_user_id),
        "created_at": datetime.now(timezone.utc),
    }
    if recorded_by_roles is not None:
        doc["recorded_by_roles"] = list(recorded_by_roles)
    if location_lat is not None:
        doc["location_lat"] = location_lat
        doc["location_lon"] = location_lon
    if location_outside_fence:
        doc["location_outside_fence"] = True
    if location_unavailable:
        doc["location_unavailable"] = True
    return col.insert_one(doc)


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


def get_attendance_by_events(events_ids: list[str | ObjectId]) -> list[dict]:
    col = get_collection("attendance_records")
    if col is None:
        return []
    object_ids = [ObjectId(e_id) for e_id in events_ids]
    return list(col.find({"event_id": {"$in": object_ids}}))


def get_attendance_by_cadet(cadet_id: str | ObjectId) -> list[dict]:
    col = get_collection("attendance_records")
    if col is None:
        return []
    return list(col.find({"cadet_id": ObjectId(cadet_id)}))


def get_attendance_record_by_event_cadet(
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
) -> dict | None:
    col = get_collection("attendance_records")
    if col is None:
        return None
    return col.find_one(
        {
            "event_id": ObjectId(event_id),
            "cadet_id": ObjectId(cadet_id),
        }
    )


def upsert_attendance_record(
    event_id: str | ObjectId,
    cadet_id: str | ObjectId,
    status: str,
    recorded_by_user_id: str | ObjectId,
    recorded_by_roles: list[str] | None = None,
) -> UpdateResult | None:
    """Insert or update a single attendance record atomically.

    Safe to call concurrently — uses MongoDB upsert so the last writer wins
    on status without ever creating duplicate (event_id, cadet_id) pairs.
    """
    col = get_collection("attendance_records")
    if col is None:
        return None
    set_doc: dict[str, Any] = {
        "status": status,
        "recorded_by_user_id": ObjectId(recorded_by_user_id),
        "updated_at": datetime.now(timezone.utc),
    }
    if recorded_by_roles is not None:
        set_doc["recorded_by_roles"] = list(recorded_by_roles)
    return col.update_one(
        {
            "event_id": ObjectId(event_id),
            "cadet_id": ObjectId(cadet_id),
        },
        {
            "$set": set_doc,
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


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


def get_cadet_absence_stats() -> list[dict]:
    col = get_collection("attendance_records")
    if col is None:
        return []

    pipeline = [
        {"$match": {"status": "absent"}},
        {
            "$lookup": {
                "from": "events",
                "localField": "event_id",
                "foreignField": "_id",
                "as": "event",
            }
        },
        {"$unwind": "$event"},
        {"$match": {"event.event_type": {"$in": ["pt", "lab"]}}},
        {
            "$lookup": {
                "from": "waivers",
                "localField": "_id",
                "foreignField": "attendance_record_id",
                "as": "waiver",
            }
        },
        {
            "$unwind": {
                "path": "$waiver",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$match": {
                "$or": [
                    {"waiver": None},
                    {"waiver.status": {"$ne": "approved"}},
                ]
            }
        },
        {
            "$group": {
                "_id": "$cadet_id",
                "pt_absences": {
                    "$sum": {"$cond": [{"$eq": ["$event.event_type", "pt"]}, 1, 0]}
                },
                "llab_absences": {
                    "$sum": {"$cond": [{"$eq": ["$event.event_type", "lab"]}, 1, 0]}
                },
                "approved_waivers": {
                    "$sum": {"$cond": [{"$eq": ["$waiver.status", "approved"]}, 1, 0]}
                },
                "pending_waivers": {
                    "$sum": {"$cond": [{"$eq": ["$waiver.status", "pending"]}, 1, 0]}
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "cadet_id": "$_id",
                "pt_absences": 1,
                "llab_absences": 1,
                "total_absences": {"$add": ["$pt_absences", "$llab_absences"]},
                "approved_waivers": 1,
                "pending_waivers": 1,
            }
        },
        {"$sort": {"total_absences": -1}},
    ]

    return list(col.aggregate(pipeline))


# -- Waivers


def create_waiver(
    attendance_record_id: str | ObjectId | None,
    reason: str,
    status: str,
    submitted_by_user_id: str | ObjectId,
    waiver_type: str = "non-medical",
    cadre_only: bool = False,
    attachments: list | None = None,
    *,
    is_standing: bool = False,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    event_types: list[str] | None = None,
) -> InsertOneResult | None:
    col = get_collection("waivers")
    if col is None:
        return None

    doc: dict = {
        "reason": reason,
        "status": status,
        "submitted_by_user_id": ObjectId(submitted_by_user_id),
        "waiver_type": waiver_type,
        "cadre_only": cadre_only,
        "attachments": attachments or [],
        "created_at": datetime.now(timezone.utc),
    }

    if is_standing:
        doc["is_standing"] = True
        doc["attendance_record_id"] = None
        doc["start_date"] = start_date
        doc["end_date"] = end_date
        doc["event_types"] = list(event_types or ["pt", "lab"])
        return col.insert_one(doc)

    if attendance_record_id is None:
        return None

    attendance_oid = ObjectId(attendance_record_id)
    existing_withdrawn = col.find_one(
        {
            "attendance_record_id": attendance_oid,
            "status": "withdrawn",
        }
    )

    doc["attendance_record_id"] = attendance_oid
    if existing_withdrawn:
        doc["previous_waiver_id"] = existing_withdrawn["_id"]

    result = col.insert_one(doc)

    is_valid, why = validate_waiver(attendance_oid)
    if not is_valid:
        col.update_one(
            {"_id": result.inserted_id},
            {"$set": {"status": "denied", "auto_denied": True}},
        )

        create_waiver_approval(
            waiver_id=result.inserted_id,
            approver_id=None,
            decision="denied",
            comments=f"Auto-denied: {why}",
        )

    return result


def validate_waiver(attendance_record_id: str | ObjectId) -> tuple[bool, str]:
    rec_col = get_collection("attendance_records")
    evt_col = get_collection("events")

    if rec_col is None or evt_col is None:
        return False, "Database unavailable."

    attendance_oid = ObjectId(attendance_record_id)

    record = rec_col.find_one({"_id": attendance_oid})
    if not record:
        return False, "Attendance record not found."

    event = evt_col.find_one({"_id": record["event_id"]})
    if not event:
        return False, "Event not found."

    start_date = event.get("start_date")
    now = datetime.now(timezone.utc)

    if not isinstance(start_date, datetime):
        return False, "Invalid event date."

    if start_date.year != now.year:
        return False, "Event is not in the current year."

    event_type = (event.get("event_type") or "").lower()

    if event_type not in ("pt", "lab"):
        return False, f"Waivers are not allowed for event type '{event_type}'."

    return True, ""


def get_sickness_waivers_by_user(user_id: str | ObjectId) -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(
        col.find(
            {
                "submitted_by_user_id": ObjectId(user_id),
                "waiver_type": "sickness",
                "status": {"$in": ["approved", "pending"]},
            }
        )
    )


def get_standing_waivers_by_user(user_id: str | ObjectId) -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(
        col.find(
            {
                "submitted_by_user_id": ObjectId(user_id),
                "is_standing": True,
            }
        )
    )


def get_approved_waivers_by_user(user_id: str | ObjectId) -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(
        col.find(
            {
                "submitted_by_user_id": ObjectId(user_id),
                "status": "approved",
            }
        )
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
    return col.find_one(
        {
            "attendance_record_id": ObjectId(attendance_record_id),
            "status": {"$nin": ["withdrawn"]},
        }
    )


def get_waivers_by_status(status: str) -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(col.find({"status": status}))


def get_waivers_by_attendance_records(record_ids: list[str | ObjectId]) -> list[dict]:
    if not record_ids:
        return []
    col = get_collection("waivers")
    if col is None:
        return []
    object_ids = [ObjectId(r_id) for r_id in record_ids]
    return list(col.find({"attendance_record_id": {"$in": object_ids}}))


def get_all_waivers() -> list[dict]:
    col = get_collection("waivers")
    if col is None:
        return []
    return list(col.find())


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
    approver_id: str | ObjectId | None,
    decision: str,
    comments: str,
) -> InsertOneResult | None:
    col = get_collection("waiver_approvals")
    if col is None:
        return None

    doc = {
        "waiver_id": ObjectId(waiver_id),
        "decision": decision,
        "comments": comments,
        "created_at": datetime.now(timezone.utc),
    }
    if approver_id is not None:
        doc["approver_id"] = ObjectId(approver_id)

    return col.insert_one(doc)


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


def _validate_flight_association(
    cadet_id: str | ObjectId,
    target_flight_id: str | ObjectId | None = None,
) -> None:
    cadets_col = get_collection("cadets")
    flights_col = get_collection("flights")
    if cadets_col is None or flights_col is None:
        return

    cadet_object_id = ObjectId(cadet_id)
    target_object_id = (
        ObjectId(target_flight_id) if target_flight_id is not None else None
    )

    cadet = cadets_col.find_one({"_id": cadet_object_id})
    if cadet and cadet.get("flight_id") and cadet["flight_id"] != target_object_id:
        assigned_flight = flights_col.find_one({"_id": cadet["flight_id"]})
        assigned_flight_name = (
            assigned_flight.get("name") if assigned_flight else "another flight"
        )
        raise ValueError(
            f"Cadet is already assigned to {assigned_flight_name}. Unassign them first."
        )

    commander_query: dict[str, Any] = {"commander_cadet_id": cadet_object_id}
    if target_object_id is not None:
        commander_query["_id"] = {"$ne": target_object_id}

    commanded_flight = flights_col.find_one(commander_query)
    if commanded_flight:
        commanded_flight_name = commanded_flight.get("name", "another flight")
        raise ValueError(
            f"Cadet is already commanding {commanded_flight_name}. Remove them as commander first."
        )


def create_flight(name: str, commander_cadet_id: str | ObjectId):
    col = get_collection("flights")
    if col is None:
        return None

    _validate_flight_association(commander_cadet_id)

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


def get_flight_by_id(flight_id: str | ObjectId) -> dict | None:
    col = get_collection("flights")
    if col is None:
        return None
    return col.find_one({"_id": ObjectId(flight_id)})


def get_flight_by_commander(commander_cadet_id: str | ObjectId) -> dict | None:
    col = get_collection("flights")
    if col is None:
        return None
    return col.find_one({"commander_cadet_id": ObjectId(commander_cadet_id)})


def update_flight(flight_id: str | ObjectId, updates: dict):
    col = get_collection("flights")
    if col is None:
        return None

    if "commander_cadet_id" in updates:
        _validate_flight_association(updates["commander_cadet_id"], flight_id)

    return col.update_one({"_id": ObjectId(flight_id)}, {"$set": updates})


def delete_flight(flight_id: str | ObjectId):
    col = get_collection("flights")
    if col is None:
        return None
    return col.delete_one({"_id": ObjectId(flight_id)})


# -- Event Codes


def create_event_code(
    code: str,
    event_id: str | ObjectId,
    event_type: str,
    event_date: str,
    created_by_user_id: str | ObjectId,
    expires_at: datetime,
) -> InsertOneResult | None:
    col = get_collection("event_codes")
    if col is None:
        return None
    col.update_many(
        {"event_id": ObjectId(event_id), "active": True},
        {"$set": {"active": False}},
    )
    return col.insert_one(
        {
            "code": code,
            "event_id": ObjectId(event_id),
            "event_type": event_type,
            "event_date": event_date,
            "created_by_user_id": ObjectId(created_by_user_id),
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "active": True,
        }
    )


def get_active_event_code(event_id: str | ObjectId) -> dict | None:
    col = get_collection("event_codes")
    if col is None:
        return None
    now = datetime.now(timezone.utc)
    return col.find_one(
        {
            "event_id": ObjectId(event_id),
            "active": True,
            "expires_at": {"$gt": now},
        }
    )


def deactivate_event_code(code_id: str | ObjectId) -> UpdateResult | None:
    col = get_collection("event_codes")
    if col is None:
        return None
    return col.update_one(
        {"_id": ObjectId(code_id)},
        {"$set": {"active": False}},
    )


def get_event_codes_by_event(event_id: str | ObjectId) -> list[dict]:
    col = get_collection("event_codes")
    if col is None:
        return []
    return list(col.find({"event_id": ObjectId(event_id)}).sort("created_at", -1))


def find_active_event_code_by_value(code: str) -> dict | None:
    col = get_collection("event_codes")
    if col is None:
        return None
    now = datetime.now(timezone.utc)
    return col.find_one(
        {
            "code": code,
            "active": True,
            "expires_at": {"$gt": now},
        }
    )


def assign_cadet_to_flight(cadet_id: str | ObjectId, flight_id: str | ObjectId):
    col = get_collection("cadets")
    if col is None:
        return None

    _validate_flight_association(cadet_id, flight_id)

    return col.update_one(
        {"_id": ObjectId(cadet_id)},
        {"$set": {"flight_id": ObjectId(flight_id)}},
    )


def unassign_all_cadets_from_flight(flight_id: str | ObjectId):
    col = get_collection("cadets")
    if col is None:
        return None

    return col.update_many(
        {"flight_id": ObjectId(flight_id)},
        {"$unset": {"flight_id": ""}},
    )


def unassign_cadet_from_flight(cadet_id: str | ObjectId):
    col = get_collection("cadets")
    if col is None:
        return None

    return col.update_one(
        {"_id": ObjectId(cadet_id)},
        {"$unset": {"flight_id": ""}},
    )
