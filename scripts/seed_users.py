"""
Populate the rollcall MongoDB database with demo data.

Usage:
    python scripts/populate_db.py

All demo users have password: password
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.create_indexes import create_indexes
from utils.db import get_db


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


PASSWORD = _hash("password")


USERS = [
    ("admin1", "Admin", "User", "admin1@rollcall.local", "admin"),
    ("cadre1", "Cadre", "Member", "cadre1@rollcall.local", "cadre"),
    ("cadre2", "Sarah", "Williams", "cadre2@rollcall.local", "cadre"),
    ("fc1", "James", "Anderson", "fc1@rollcall.local", "flight_commander"),
    ("fc2", "Maria", "Garcia", "fc2@rollcall.local", "flight_commander"),
    ("cadet1", "Tyler", "Brooks", "cadet1@rollcall.local", "cadet"),
    ("cadet2", "Emily", "Chen", "cadet2@rollcall.local", "cadet"),
    ("cadet3", "Marcus", "Davis", "cadet3@rollcall.local", "cadet"),
    ("cadet4", "Ashley", "Foster", "cadet4@rollcall.local", "cadet"),
    ("cadet5", "Jordan", "Hayes", "cadet5@rollcall.local", "cadet"),
    ("cadet6", "Nicole", "Kim", "cadet6@rollcall.local", "cadet"),
    ("cadet7", "Brian", "Lopez", "cadet7@rollcall.local", "cadet"),
    ("cadet8", "Rachel", "Martinez", "cadet8@rollcall.local", "cadet"),
    ("cadet9", "Kevin", "Nguyen", "cadet9@rollcall.local", "cadet"),
    ("cadet10", "Megan", "O'Brien", "cadet10@rollcall.local", "cadet"),
]

CADET_RANKS = {
    "fc1": 300,
    "fc2": 300,
    "cadet1": 200,
    "cadet2": 200,
    "cadet3": 100,
    "cadet4": 100,
    "cadet5": 200,
    "cadet6": 300,
    "cadet7": 100,
    "cadet8": 400,
    "cadet9": 200,
    "cadet10": 100,
}

FLIGHTS = [
    ("Alpha Flight", "fc1"),
    ("Bravo Flight", "fc2"),
]

FLIGHT_ASSIGNMENTS = {
    "Alpha Flight": ["fc1", "cadet1", "cadet2", "cadet3", "cadet4", "cadet5"],
    "Bravo Flight": ["fc2", "cadet6", "cadet7", "cadet8", "cadet9", "cadet10"],
}

now = datetime.now(timezone.utc)

EVENTS = [
    ("PT Session 1", "pt", 21, 1.5, "cadre1"),
    ("PT Session 2", "pt", 14, 1.5, "cadre1"),
    ("PT Session 3", "pt", 7, 1.5, "cadre1"),
    ("PT Session 4", "pt", 0, 1.5, "cadre1"),
    ("LLAB Week 1", "lab", 20, 2.0, "cadre1"),
    ("LLAB Week 2", "lab", 13, 2.0, "cadre1"),
    ("LLAB Week 3", "lab", 6, 2.0, "cadre2"),
]

CADET_USERNAMES = [u[0] for u in USERS if u[4] == "cadet"] + ["fc1", "fc2"]

_PATTERNS = [
    "PPPPPPPPPPPP",
    "APPPAPPPPPP",
    "PPPPPPAPPEPP",
    "APAPPPPPPPPP",
    "PPPPPPPPPPPP",
    "APPPPPAPPPPPP",
    "PPPPPPPPAPPP",
]

STATUS_MAP = {"P": "present", "A": "absent", "E": "excused"}


def populate():
    db = get_db()
    if db is None:
        print("ERROR: Could not connect to MongoDB. Check MONGODB_URI in .env")
        sys.exit(1)
    assert db is not None

    for col_name in [
        "users",
        "cadets",
        "events",
        "event_assignments",
        "attendance_records",
        "waivers",
        "waiver_approvals",
        "flights",
    ]:
        db.drop_collection(col_name)
    print("Cleared all collections.")

    user_id_by_username: dict[str, object] = {}

    for username, first, last, email, role in USERS:
        full_name = f"{first} {last}"
        doc = {
            "username": username,
            "first_name": first,
            "last_name": last,
            "name": full_name,
            "email": email,
            "password": PASSWORD,
            "password_hash": PASSWORD,
            "role": role,
            "roles": [role],
            "created_at": now,
        }
        result = db["users"].insert_one(doc)
        user_id_by_username[username] = result.inserted_id

    print(f"Inserted {len(USERS)} users.")

    cadet_id_by_username: dict[str, object] = {}

    user_info = {u[0]: u for u in USERS}
    for username, rank in CADET_RANKS.items():
        _, first, last, email, _ = user_info[username]
        result = db["cadets"].insert_one(
            {
                "user_id": user_id_by_username[username],
                "rank": rank,
                "first_name": first,
                "last_name": last,
                "email": email,
            }
        )
        cadet_id_by_username[username] = result.inserted_id

    print(f"Inserted {len(CADET_RANKS)} cadet profiles.")

    flight_id_by_name: dict[str, object] = {}

    for flight_name, commander_username in FLIGHTS:
        result = db["flights"].insert_one(
            {
                "name": flight_name,
                "commander_cadet_id": cadet_id_by_username[commander_username],
            }
        )
        flight_id_by_name[flight_name] = result.inserted_id

    for flight_name, members in FLIGHT_ASSIGNMENTS.items():
        fid = flight_id_by_name[flight_name]
        for username in members:
            db["cadets"].update_one(
                {"_id": cadet_id_by_username[username]},
                {"$set": {"flight_id": fid}},
            )

    print(f"Inserted {len(FLIGHTS)} flights with assignments.")

    event_ids: list[object] = []

    for event_name, event_type, days_ago, hours, creator in EVENTS:
        start = now - timedelta(days=days_ago)
        end = start + timedelta(hours=hours)
        result = db["events"].insert_one(
            {
                "event_name": event_name,
                "event_type": event_type,
                "start_date": start,
                "end_date": end,
                "created_by_user_id": user_id_by_username[creator],
                "created_at": now,
            }
        )
        event_ids.append(result.inserted_id)

    print(f"Inserted {len(EVENTS)} events.")

    rec_count = 0
    for event_idx, event_id in enumerate(event_ids):
        pattern = _PATTERNS[event_idx]
        for cadet_idx, username in enumerate(CADET_USERNAMES):
            status_char = pattern[cadet_idx] if cadet_idx < len(pattern) else "P"
            db["attendance_records"].insert_one(
                {
                    "event_id": event_id,
                    "cadet_id": cadet_id_by_username[username],
                    "status": STATUS_MAP[status_char],
                    "recorded_by_user_id": user_id_by_username["cadre1"],
                    "created_at": now,
                }
            )
            rec_count += 1

    print(f"Inserted {rec_count} attendance records.")

    create_indexes()
    print("Recreated indexes.")
    print()
    print("Done! All demo users have password: password")
    print()
    print("Demo logins:")
    print("  admin1  / password  (admin)")
    print("  cadre1  / password  (cadre)")
    print("  fc1     / password  (flight_commander)")
    print("  cadet1  / password  (cadet)")


if __name__ == "__main__":
    populate()
