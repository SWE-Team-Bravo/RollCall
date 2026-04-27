"""
All demo users have password: password

Key demo accounts:
  admin@rollcall.local             (admin)
  henderson@rollcall.local         (cadre)
  fc.alpha@rollcall.local          (flight_commander - Alpha Flight)
  tyler.brooks@rollcall.local      (cadet  - Alpha Flight)
"""

import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cadets import RANK_TO_LEVEL
from utils.create_indexes import create_indexes
from utils.db import get_db

rng = random.Random(42)

NOW = datetime.now(timezone.utc)
TODAY = date.today()
SEMESTER_START = date(2026, 1, 12)


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


PASSWORD = _hash("password")

ADMIN_USERS = [
    ("admin", "Command", "Admin", "admin@rollcall.local", ["admin"], None),
]

CADRE_USERS = [
    ("henderson", "Michael", "Henderson", "henderson@rollcall.local", ["cadre"], None),
    ("torres", "Lisa", "Torres", "torres@rollcall.local", ["cadre"], None),
    ("washington", "James", "Washington", "washington@rollcall.local", ["cadre"], None),
]

FC_USERS = [
    (
        "fc.alpha",
        "Alexander",
        "Mitchell",
        "fc.alpha@rollcall.local",
        ["flight_commander"],
        "300",
    ),
    (
        "fc.bravo",
        "Samantha",
        "Reynolds",
        "fc.bravo@rollcall.local",
        ["flight_commander"],
        "300",
    ),
    (
        "fc.charlie",
        "David",
        "Thompson",
        "fc.charlie@rollcall.local",
        ["flight_commander"],
        "300",
    ),
    (
        "fc.delta",
        "Jennifer",
        "Williams",
        "fc.delta@rollcall.local",
        ["flight_commander"],
        "300",
    ),
    (
        "fc.echo",
        "Christopher",
        "Parker",
        "fc.echo@rollcall.local",
        ["flight_commander"],
        "300",
    ),
    (
        "fc.foxtrot",
        "Amanda",
        "Scott",
        "fc.foxtrot@rollcall.local",
        ["flight_commander"],
        "300",
    ),
]

CADETS_BY_FLIGHT: dict[str, list] = {
    "Alpha Flight": [
        (
            "tyler.brooks",
            "Tyler",
            "Brooks",
            "tyler.brooks@rollcall.local",
            ["cadet"],
            "200",
        ),
        ("emily.chen", "Emily", "Chen", "emily.chen@rollcall.local", ["cadet"], "400"),
        (
            "marcus.davis",
            "Marcus",
            "Davis",
            "marcus.davis@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "ashley.foster",
            "Ashley",
            "Foster",
            "ashley.foster@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "jordan.hayes",
            "Jordan",
            "Hayes",
            "jordan.hayes@rollcall.local",
            ["cadet"],
            "200",
        ),
        ("nicole.kim", "Nicole", "Kim", "nicole.kim@rollcall.local", ["cadet"], "400"),
        (
            "brian.lopez",
            "Brian",
            "Lopez",
            "brian.lopez@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "rachel.martinez",
            "Rachel",
            "Martinez",
            "rachel.martinez@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "kevin.nguyen",
            "Kevin",
            "Nguyen",
            "kevin.nguyen@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
    "Bravo Flight": [
        (
            "megan.obrien",
            "Megan",
            "O'Brien",
            "megan.obrien@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "arjun.patel",
            "Arjun",
            "Patel",
            "arjun.patel@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "sienna.quinn",
            "Sienna",
            "Quinn",
            "sienna.quinn@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "carlos.rivera",
            "Carlos",
            "Rivera",
            "carlos.rivera@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "destiny.santos",
            "Destiny",
            "Santos",
            "destiny.santos@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "hunter.taylor",
            "Hunter",
            "Taylor",
            "hunter.taylor@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "grace.underwood",
            "Grace",
            "Underwood",
            "grace.underwood@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "diego.valdez",
            "Diego",
            "Valdez",
            "diego.valdez@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "amber.wilson",
            "Amber",
            "Wilson",
            "amber.wilson@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
    "Charlie Flight": [
        (
            "cameron.adams",
            "Cameron",
            "Adams",
            "cameron.adams@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "jessica.baker",
            "Jessica",
            "Baker",
            "jessica.baker@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "nathan.clark",
            "Nathan",
            "Clark",
            "nathan.clark@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "olivia.duncan",
            "Olivia",
            "Duncan",
            "olivia.duncan@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "ethan.edwards",
            "Ethan",
            "Edwards",
            "ethan.edwards@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "hannah.franklin",
            "Hannah",
            "Franklin",
            "hannah.franklin@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "ryan.gibson",
            "Ryan",
            "Gibson",
            "ryan.gibson@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "sophia.harrison",
            "Sophia",
            "Harrison",
            "sophia.harrison@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "logan.ingram",
            "Logan",
            "Ingram",
            "logan.ingram@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
    "Delta Flight": [
        (
            "xavier.jackson",
            "Xavier",
            "Jackson",
            "xavier.jackson@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "brittany.knight",
            "Brittany",
            "Knight",
            "brittany.knight@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "derek.lambert",
            "Derek",
            "Lambert",
            "derek.lambert@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "courtney.murphy",
            "Courtney",
            "Murphy",
            "courtney.murphy@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "austin.nelson",
            "Austin",
            "Nelson",
            "austin.nelson@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "tiffany.owens",
            "Tiffany",
            "Owens",
            "tiffany.owens@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "blake.peterson",
            "Blake",
            "Peterson",
            "blake.peterson@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "maria.ramirez",
            "Maria",
            "Ramirez",
            "maria.ramirez@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "caleb.stevens",
            "Caleb",
            "Stevens",
            "caleb.stevens@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
    "Echo Flight": [
        (
            "danielle.turner",
            "Danielle",
            "Turner",
            "danielle.turner@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "andrew.upton",
            "Andrew",
            "Upton",
            "andrew.upton@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "victoria.vasquez",
            "Victoria",
            "Vasquez",
            "victoria.vasquez@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "sean.walker",
            "Sean",
            "Walker",
            "sean.walker@rollcall.local",
            ["cadet"],
            "100",
        ),
        ("jenna.xu", "Jenna", "Xu", "jenna.xu@rollcall.local", ["cadet"], "200"),
        (
            "jacob.young",
            "Jacob",
            "Young",
            "jacob.young@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "katelyn.zimmerman",
            "Katelyn",
            "Zimmerman",
            "katelyn.zimmerman@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "troy.abbott",
            "Troy",
            "Abbott",
            "troy.abbott@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "leah.barker",
            "Leah",
            "Barker",
            "leah.barker@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
    "Foxtrot Flight": [
        (
            "patrick.carter",
            "Patrick",
            "Carter",
            "patrick.carter@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "heather.dixon",
            "Heather",
            "Dixon",
            "heather.dixon@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "brandon.ellis",
            "Brandon",
            "Ellis",
            "brandon.ellis@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "cassandra.flynn",
            "Cassandra",
            "Flynn",
            "cassandra.flynn@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "travis.grant",
            "Travis",
            "Grant",
            "travis.grant@rollcall.local",
            ["cadet"],
            "200",
        ),
        (
            "lindsay.hughes",
            "Lindsay",
            "Hughes",
            "lindsay.hughes@rollcall.local",
            ["cadet"],
            "400",
        ),
        (
            "dustin.irwin",
            "Dustin",
            "Irwin",
            "dustin.irwin@rollcall.local",
            ["cadet"],
            "100",
        ),
        (
            "kelly.jensen",
            "Kelly",
            "Jensen",
            "kelly.jensen@rollcall.local",
            ["cadet"],
            "300",
        ),
        (
            "seth.keller",
            "Seth",
            "Keller",
            "seth.keller@rollcall.local",
            ["cadet"],
            "200",
        ),
    ],
}

FLIGHT_FC_MAP = {
    "Alpha Flight": "fc.alpha",
    "Bravo Flight": "fc.bravo",
    "Charlie Flight": "fc.charlie",
    "Delta Flight": "fc.delta",
    "Echo Flight": "fc.echo",
    "Foxtrot Flight": "fc.foxtrot",
}


AT_RISK_PT_ABSENCES: dict[str, set] = {
    "ashley.foster": {3, 8, 14, 18, 23, 28, 33, 38, 43},
    "destiny.santos": {2, 9, 17, 22, 30, 36, 40},
    "nathan.clark": {5, 12, 19, 26, 31},
    "brian.lopez": {4, 11, 20, 29},
    "brandon.ellis": {6, 16, 25, 37},
    "derek.lambert": {1, 13, 27, 41},
    "ryan.gibson": {7, 21, 34},
}

AT_RISK_LLAB_ABSENCES: dict[str, set] = {
    "olivia.duncan": {2, 8},
    "megan.obrien": {1, 6},
    "carlos.rivera": {4},
    "sean.walker": {3},
}


def _gen_status(cadet_key: str, event_type: str, type_idx: int) -> str:
    """Return attendance status for a cadet at a past event."""
    if event_type == "pt" and type_idx in AT_RISK_PT_ABSENCES.get(cadet_key, set()):
        return "absent"
    if event_type == "lab" and type_idx in AT_RISK_LLAB_ABSENCES.get(cadet_key, set()):
        return "absent"
    r = rng.random()
    if r < 0.87:
        return "present"
    if r < 0.97:
        return "absent"
    return "excused"


REASONS_NON_MEDICAL = [
    "Military Orders  - TDY orders attached to this waiver submission.",
    "Sport team conflict  - authorized absence, coach documentation on file.",
    "Crosstown (PASSED PFA)  - crosstown ROTC event scheduling conflict.",
    "School obligation  - required lab section was rescheduled to overlap with PT.",
    "Work  - mandatory on-call shift, no substitute available, notified flight commander.",
    "Personal/family emergency  - had to assist family member with medical situation.",
    "FTX excuse  - participated in authorized Field Training Exercise.",
    "Missed alarm  - phone died overnight; corrective action taken (backup alarm set).",
    "Late  - vehicle would not start; arrived 25 minutes after PT began.",
    "Flat tire on the way to PT  - tow truck required, notified cadre immediately.",
    "Vacation, wedding, out of town  - pre-approved family event per prior coordination.",
    "Out of regs  - uniform discrepancy; corrected same day before next formation.",
    "Lack of sleep  - worked overnight shift at hospital, safety concern to participate.",
    "School obligation (change of class time, scholarship requirement, etc.)  - STEM scholarship lab",
    "Other (describe below): Had prior commitment authorized by flight commander in writing.",
]

REASONS_SICKNESS = [
    "Sick without documentation  - 101°F fever, unable to leave housing per CDC guidance.",
    "Sick without documentation  - GI illness overnight, unable to participate safely.",
    "Sick without documentation  - severe migraine, unable to exercise or drive.",
    "Sick without documentation  - upper respiratory infection, contagious, stayed home.",
    "Sick without documentation  - food poisoning, was ill from Sunday night through Monday morning.",
]

REASONS_MEDICAL = [
    "Sick with documentation  - physician visit for strep throat, note attached.",
    "Sick with documentation  - influenza confirmed by rapid test, doctor note attached.",
    "Injury  - sprained ankle during intramural sports, orthopedic note attached.",
    "Injury  - knee pain flare-up, cleared for limited activity by physician, note attached.",
    "Sick with documentation  - ER visit night before for dehydration, discharge paperwork attached.",
    "Sick with documentation  - allergic reaction requiring medical attention, note attached.",
]

FAKE_ATTACHMENTS = [
    [
        {
            "filename": "medical_note_strep.pdf",
            "content_type": "application/pdf",
            "size": 245678,
        }
    ],
    [
        {
            "filename": "dr_visit_receipt.pdf",
            "content_type": "application/pdf",
            "size": 189234,
        }
    ],
    [
        {
            "filename": "ER_discharge_summary.pdf",
            "content_type": "application/pdf",
            "size": 312456,
        }
    ],
    [
        {
            "filename": "orthopedic_clearance.pdf",
            "content_type": "application/pdf",
            "size": 198765,
        }
    ],
    [
        {
            "filename": "physician_note_influenza.pdf",
            "content_type": "application/pdf",
            "size": 156432,
        }
    ],
    [
        {
            "filename": "sick_leave_documentation.pdf",
            "content_type": "application/pdf",
            "size": 278901,
        }
    ],
    [
        {
            "filename": "allergy_physician_note.pdf",
            "content_type": "application/pdf",
            "size": 211345,
        }
    ],
    [
        {
            "filename": "er_discharge.pdf",
            "content_type": "application/pdf",
            "size": 312456,
        },
        {
            "filename": "followup_care_instructions.pdf",
            "content_type": "application/pdf",
            "size": 89012,
        },
    ],
]

COMMENTS_APPROVED = [
    "Waiver approved. Documentation verified and circumstances are valid.",
    "Approved  - cadet has good overall attendance and this is a first offense.",
    "Approved. Military obligation takes priority; no further action required.",
    "Approved with note: please ensure prior coordination with chain of command next time.",
    "Approved  - school obligation is legitimate; cadet coordinated in advance.",
    "Approved. Medical documentation confirms cadet was unable to participate safely.",
    "Approved  - emergency circumstances, cadet notified chain of command promptly.",
    "Approved. Cadet demonstrated good faith by submitting documentation quickly.",
]

COMMENTS_DENIED = [
    "Denied  - reason provided is insufficient without supporting documentation.",
    "Denied. Cadet did not notify chain of command in advance as required.",
    "Denied  - lack of prior coordination. Must notify flight commander 24 hours in advance.",
    "Denied. This is the third similar absence; pattern of behavior is a concern.",
    "Denied  - 'missed alarm' is not excusable per AFROTCI Det attendance policy.",
    "Denied. Cadet failed to follow proper waiver submission procedures (submitted late).",
    "Denied  - absence was for a non-urgent personal matter. PT attendance is mandatory.",
    "Denied. Cadet did not provide any supporting evidence for the stated reason.",
]


def _generate_semester_events() -> list[dict]:
    """16-week spring semester: PT Mon/Tue/Thu, LLAB Fri."""
    events: list[dict] = []
    pt_num = 1
    lab_num = 1
    for week in range(16):
        week_start = SEMESTER_START + timedelta(weeks=week)
        for day_offset in (0, 1, 3):
            d = week_start + timedelta(days=day_offset)
            events.append({"name": f"PT Session {pt_num}", "type": "pt", "date": d})
            pt_num += 1
        d = week_start + timedelta(days=4)
        events.append({"name": f"LLAB Week {lab_num}", "type": "lab", "date": d})
        lab_num += 1
    return events


def populate() -> None:
    db = get_db()
    if db is None:
        print("ERROR: Could not connect to MongoDB. Check MONGODB_URI in .env")
        sys.exit(1)

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
    print("Cleared collections.")

    user_id_by_key: dict[str, object] = {}

    all_user_defs = ADMIN_USERS + CADRE_USERS + FC_USERS
    for flight_cadets in CADETS_BY_FLIGHT.values():
        all_user_defs = all_user_defs + flight_cadets

    for key, first, last, email, roles, _ in all_user_defs:
        result = db["users"].insert_one(
            {
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}",
                "email": email,
                "password": PASSWORD,
                "password_hash": PASSWORD,
                "roles": roles,
                "disabled": False,
                "created_at": NOW,
            }
        )
        user_id_by_key[key] = result.inserted_id

    print(f"Inserted {len(all_user_defs)} users.")

    cadet_id_by_key: dict[str, object] = {}

    all_cadet_defs = FC_USERS[:]
    for flight_cadets in CADETS_BY_FLIGHT.values():
        all_cadet_defs = all_cadet_defs + flight_cadets

    for key, first, last, email, _, rank in all_cadet_defs:
        assert rank is not None
        result = db["cadets"].insert_one(
            {
                "user_id": user_id_by_key[key],
                "rank": rank,
                "level": RANK_TO_LEVEL[rank],
                "first_name": first,
                "last_name": last,
                "email": email,
            }
        )
        cadet_id_by_key[key] = result.inserted_id

    print(f"Inserted {len(all_cadet_defs)} cadet profiles.")

    flight_id_by_name: dict[str, object] = {}

    for flight_name, fc_key in FLIGHT_FC_MAP.items():
        result = db["flights"].insert_one(
            {
                "name": flight_name,
                "commander_cadet_id": cadet_id_by_key[fc_key],
            }
        )
        flight_id_by_name[flight_name] = result.inserted_id

    for flight_name, fc_key in FLIGHT_FC_MAP.items():
        fid = flight_id_by_name[flight_name]
        db["cadets"].update_one(
            {"_id": cadet_id_by_key[fc_key]},
            {"$set": {"flight_id": fid}},
        )
        for key, *_ in CADETS_BY_FLIGHT[flight_name]:
            db["cadets"].update_one(
                {"_id": cadet_id_by_key[key]},
                {"$set": {"flight_id": fid}},
            )

    print(f"Inserted {len(FLIGHT_FC_MAP)} flights.")

    semester_events = _generate_semester_events()
    creator_cycle = ["henderson", "torres", "washington"]

    event_meta: list[tuple] = []
    pt_idx = 0
    lab_idx = 0

    for i, ev in enumerate(semester_events):
        is_past = ev["date"] < TODAY
        hour = 6 if ev["type"] == "pt" else 13
        start_dt = datetime.combine(ev["date"], time(hour, 0), tzinfo=timezone.utc)
        duration = timedelta(hours=1.5 if ev["type"] == "pt" else 2.0)

        result = db["events"].insert_one(
            {
                "event_name": ev["name"],
                "event_type": ev["type"],
                "start_date": start_dt,
                "end_date": start_dt + duration,
                "created_by_user_id": user_id_by_key[creator_cycle[i % 3]],
                "created_at": NOW,
            }
        )

        cur_idx = pt_idx if ev["type"] == "pt" else lab_idx
        event_meta.append((result.inserted_id, ev["type"], is_past, cur_idx))

        if ev["type"] == "pt":
            pt_idx += 1
        else:
            lab_idx += 1

    past_count = sum(1 for _, _, is_past, _ in event_meta if is_past)
    print(
        f"Inserted {len(semester_events)} events ({past_count} past, {len(semester_events) - past_count} upcoming)."
    )

    all_cadet_keys = [key for key, *_ in FC_USERS]
    for flight_cadets in CADETS_BY_FLIGHT.values():
        all_cadet_keys += [key for key, *_ in flight_cadets]

    cadre_recorder_id = user_id_by_key["henderson"]

    absent_records: list[tuple] = []
    rec_count = 0

    for event_id, event_type, is_past, type_idx in event_meta:
        if not is_past:
            continue
        for cadet_key in all_cadet_keys:
            status = _gen_status(cadet_key, event_type, type_idx)
            result = db["attendance_records"].insert_one(
                {
                    "event_id": event_id,
                    "cadet_id": cadet_id_by_key[cadet_key],
                    "status": status,
                    "recorded_by_user_id": cadre_recorder_id,
                    "created_at": NOW,
                }
            )
            rec_count += 1
            if status == "absent":
                absent_records.append(
                    (
                        result.inserted_id,
                        cadet_key,
                        event_type,
                        cadet_id_by_key[cadet_key],
                    )
                )

    absence_count = len(absent_records)
    print(f"Inserted {rec_count} attendance records ({absence_count} absences).")

    waiver_count = 0
    approval_count = 0

    had_sickness_waiver: set[str] = set()

    for record_id, cadet_key, event_type, cadet_mongo_id in absent_records:
        if rng.random() > 0.38:
            continue

        user_id = user_id_by_key.get(cadet_key)
        if user_id is None:
            continue

        r_type = rng.random()
        if r_type < 0.60:
            wtype = "non-medical"
            reason = rng.choice(REASONS_NON_MEDICAL)
            attachments: list = []
            cadre_only = False
        elif r_type < 0.80:
            wtype = "sickness"
            reason = rng.choice(REASONS_SICKNESS)
            attachments = []
            cadre_only = False
        else:
            wtype = "medical"
            reason = rng.choice(REASONS_MEDICAL)
            attachments = rng.choice(FAKE_ATTACHMENTS)
            cadre_only = True

        auto_approved_sickness = False
        if wtype == "sickness" and cadet_key not in had_sickness_waiver:
            status = "approved"
            auto_approved_sickness = True
            had_sickness_waiver.add(cadet_key)
        else:
            r_status = rng.random()
            if r_status < 0.30:
                status = "approved"
            elif r_status < 0.55:
                status = "denied"
            elif r_status < 0.85:
                status = "pending"
            else:
                status = "withdrawn"

        days_ago_submitted = rng.randint(1, 70)
        w_result = db["waivers"].insert_one(
            {
                "attendance_record_id": record_id,
                "reason": reason,
                "status": status,
                "submitted_by_user_id": user_id,
                "waiver_type": wtype,
                "cadre_only": cadre_only or bool(attachments),
                "attachments": attachments,
                "auto_denied": False,
                "created_at": NOW - timedelta(days=days_ago_submitted),
            }
        )
        waiver_id = w_result.inserted_id
        waiver_count += 1

        if auto_approved_sickness:
            db["waiver_approvals"].insert_one(
                {
                    "waiver_id": waiver_id,
                    "approver_id": None,
                    "decision": "approved",
                    "comments": "Auto-approved: first sickness waiver.",
                    "created_at": NOW - timedelta(days=days_ago_submitted - 1),
                }
            )
            approval_count += 1
        elif status in ("approved", "denied"):
            approver_key = rng.choice(["henderson", "torres", "washington"])
            comments = (
                rng.choice(COMMENTS_APPROVED)
                if status == "approved"
                else rng.choice(COMMENTS_DENIED)
            )
            db["waiver_approvals"].insert_one(
                {
                    "waiver_id": waiver_id,
                    "approver_id": user_id_by_key[approver_key],
                    "decision": status,
                    "comments": comments,
                    "created_at": NOW
                    - timedelta(days=max(0, days_ago_submitted - rng.randint(1, 5))),
                }
            )
            approval_count += 1

    print(f"Inserted {waiver_count} waivers, {approval_count} approvals.")

    create_indexes()
    print("Indexes created.")

    print()
    print("Done! All demo users have password: password")
    print()
    print("-" * 55)
    print(f"{'Account':<38} {'Role'}")
    print("-" * 55)
    print(f"{'admin@rollcall.local':<38} admin")
    for key, first, last, email, _, _ in CADRE_USERS:
        print(f"{email:<38} cadre")
    for flight_name, fc_key in FLIGHT_FC_MAP.items():
        fc_email = next(e for k, _, _, e, _, _ in FC_USERS if k == fc_key)
        print(f"{fc_email:<38} flight_commander ({flight_name})")
    print()
    print("Cadet sample logins (all flights):")
    for flight_name, cadets in CADETS_BY_FLIGHT.items():
        key, first, last, email, _, rank = cadets[0]
        print(f"  {email:<40} rank {rank}")
    print("-" * 55)
    print()
    print("At-risk cadets:")
    print("  ashley.foster   - 9 PT absences (AT threshold)")
    print("  destiny.santos  - 7 PT absences (near threshold)")
    print("  olivia.duncan   - 2 LLAB absences (AT threshold)")
    print("  megan.obrien    - 2 LLAB absences (AT threshold)")


if __name__ == "__main__":
    populate()
