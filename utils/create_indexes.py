from pymongo import ASCENDING, IndexModel

from utils.db import get_db


def create_indexes() -> None:
    db = get_db()
    if db is None:
        raise ConnectionError("Could not connect to MongoDB")

    db["users"].create_indexes(
        [
            IndexModel([("email", ASCENDING)], name="email_unique", unique=True),
        ]
    )

    db["cadets"].create_indexes(
        [
            IndexModel([("user_id", ASCENDING)], name="user_id_unique", unique=True),
            IndexModel([("flight_id", ASCENDING)], name="flight_id"),
        ]
    )

    db["events"].create_indexes(
        [
            IndexModel([("event_type", ASCENDING)], name="event_type"),
            IndexModel([("created_by_user_id", ASCENDING)], name="created_by_user_id"),
            IndexModel([("start_date", ASCENDING)], name="start_date"),
        ]
    )

    db["event_assignments"].create_indexes(
        [
            IndexModel(
                [("event_id", ASCENDING), ("cadet_id", ASCENDING)],
                name="event_cadet_unique",
                unique=True,
            ),
            IndexModel(
                [("assigned_by_user_id", ASCENDING)], name="assigned_by_user_id"
            ),
        ]
    )

    db["attendance_records"].create_indexes(
        [
            IndexModel(
                [("event_id", ASCENDING), ("cadet_id", ASCENDING)],
                name="event_cadet_unique",
                unique=True,
            ),
            IndexModel(
                [("recorded_by_user_id", ASCENDING)], name="recorded_by_user_id"
            ),
        ]
    )

    db["waivers"].create_indexes(
        [
            IndexModel(
                [("attendance_record_id", ASCENDING)],
                name="attendance_record_id_unique",
                unique=True,
            ),
            IndexModel(
                [("submitted_by_user_id", ASCENDING)], name="submitted_by_user_id"
            ),
            IndexModel([("status", ASCENDING)], name="status"),
        ]
    )

    db["waiver_approvals"].create_indexes(
        [
            IndexModel([("waiver_id", ASCENDING)], name="waiver_id"),
            IndexModel([("approver_id", ASCENDING)], name="approver_id"),
        ]
    )

    db["flights"].create_indexes(
        [
            IndexModel([("name", ASCENDING)], name="flight_name_unique", unique=True),
            IndexModel([("commander_cadet_id", ASCENDING)], name="commander_cadet_id"),
        ]
    )

    db["event_codes"].create_indexes(
        [
            IndexModel(
                [("event_id", ASCENDING), ("active", ASCENDING)],
                name="event_id_active",
            ),
        ]
    )

    db["audit_log"].create_indexes(
        [
            IndexModel(
                [("cadet_id", ASCENDING), ("created_at", ASCENDING)],
                name="cadet_created_at",
            ),
            IndexModel(
                [("outcome", ASCENDING), ("created_at", ASCENDING)],
                name="outcome_created_at",
            ),
            IndexModel(
                [("source", ASCENDING), ("created_at", ASCENDING)],
                name="source_created_at",
            ),
        ]
    )

    db["checkin_codes"].create_indexes(
        [
            IndexModel(
                [("kind", ASCENDING), ("created_at", ASCENDING)],
                name="kind_created_at",
            ),
            IndexModel(
                [
                    ("kind", ASCENDING),
                    ("code_sha256", ASCENDING),
                    ("created_at", ASCENDING),
                ],
                name="kind_code_created_at",
            ),
            IndexModel(
                [("expires_at", ASCENDING)],
                name="expires_at_ttl",
                expireAfterSeconds=0,
            ),
        ]
    )