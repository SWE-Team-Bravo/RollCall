from datetime import datetime, timezone
from typing import Any
import pandas as pd

from utils.db_schema_crud import (
    get_all_cadets,
    get_attendance_by_events,
    get_events_by_type,
    get_users_by_ids,
    get_waivers_by_attendance_records,
)
from utils.names import format_full_name


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_semester_data() -> dict | None:
    cadets = get_all_cadets()
    if not cadets:
        return None

    user_ids = [c["user_id"] for c in cadets]
    users = get_users_by_ids(user_ids)

    year = datetime.now(timezone.utc).year
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    all_events = get_events_by_type("pt") + get_events_by_type("lab")
    events = [
        e
        for e in all_events
        if isinstance(e.get("start_date"), datetime)
        and start <= _ensure_utc(e["start_date"]) <= end
    ]
    if not events:
        return None

    records = get_attendance_by_events([e["_id"] for e in events])

    waivers = [
        w
        for w in get_waivers_by_attendance_records([r["_id"] for r in records])
        if w.get("status") == "approved"
    ]

    return {
        "cadets": cadets,
        "users": users,
        "events": events,
        "records": records,
        "waivers": waivers,
    }


def get_semester_df() -> pd.DataFrame | str:
    data = get_semester_data()
    if data is None:
        return "No data found."

    cadets = data["cadets"]
    users = data["users"]
    events = data["events"]
    records = data["records"]
    waivers = data["waivers"]

    name_by_user_id = {u["_id"]: format_full_name(u, "Unknown") for u in users}
    name_by_cadet = {
        c["_id"]: name_by_user_id.get(c["user_id"], "Unknown") for c in cadets
    }

    status_map: dict[tuple, str] = {
        (r["event_id"], r["cadet_id"]): (r.get("status") or "absent").lower()
        for r in records
    }
    pair_to_record: dict[tuple, Any] = {
        (r["event_id"], r["cadet_id"]): r["_id"] for r in records
    }
    waived_record_ids = {w["attendance_record_id"] for w in waivers}

    cadets_sorted = sorted(
        cadets, key=lambda c: name_by_cadet.get(c["_id"], "").lower()
    )

    rows = []
    for c in cadets_sorted:
        cid = c["_id"]
        row: dict[str, Any] = {"Cadet": name_by_cadet.get(cid, "Unknown")}
        pt_absences = llab_absences = approved_waivers = 0

        for e in events:
            eid = e["_id"]
            sd = e.get("start_date")
            col_label = f"{sd.strftime('%m/%d') if isinstance(sd, datetime) else ''} {e.get('event_type', '').upper()}".strip()

            rid = pair_to_record.get((eid, cid))
            if rid in waived_record_ids:
                val = "Waived"
            else:
                raw = status_map.get((eid, cid), "absent")
                val = {
                    "present": "Present",
                    "absent": "Absent",
                    "excused": "Excused",
                }.get(raw, "Absent")

            row[col_label] = val

            if val == "Absent":
                if e.get("event_type") == "pt":
                    pt_absences += 1
                elif e.get("event_type") == "lab":
                    llab_absences += 1

            if rid in waived_record_ids:
                approved_waivers += 1

        row["PT Absences"] = pt_absences
        row["LLAB Absences"] = llab_absences
        row["Approved Waivers"] = approved_waivers
        rows.append(row)

    return pd.DataFrame(rows)
