from datetime import datetime, timezone

from utils.datetime_utils import ensure_utc
from utils.db_schema_crud import (
    get_attendance_by_cadet,
    get_events_by_ids,
    get_flight_by_id,
    get_standing_waivers_by_user,
    get_waivers_by_attendance_records,
)
from utils.attendance_status import get_effective_attendance_status
from services.attendance_merge import merge_attendance_records


def load_attendance_db(
    cadet_id: str, user_id=None
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    records = get_attendance_by_cadet(cadet_id)
    if not records:
        return [], [], [], []

    event_ids = list({r["event_id"] for r in records})
    record_ids = [r["_id"] for r in records]

    events = get_events_by_ids(event_ids)
    waivers = get_waivers_by_attendance_records(record_ids)
    standing_waivers = (
        get_standing_waivers_by_user(user_id) if user_id is not None else []
    )

    return records, events, waivers, standing_waivers


def _covering_standing_waiver(event: dict, standing_waivers: list[dict]) -> dict | None:
    """Return the approved standing waiver that covers this event, if any."""
    start = event.get("start_date")
    if not isinstance(start, datetime):
        return None
    start = ensure_utc(start)
    event_type = (event.get("event_type") or "").lower()

    for waiver in standing_waivers:
        if (waiver.get("status") or "").lower() != "approved":
            continue
        w_start = waiver.get("start_date")
        w_end = waiver.get("end_date")
        if not (isinstance(w_start, datetime) and isinstance(w_end, datetime)):
            continue
        if not (ensure_utc(w_start) <= start <= ensure_utc(w_end)):
            continue
        types = {t.lower() for t in (waiver.get("event_types") or ["pt", "lab"])}
        if event_type and event_type not in types:
            continue
        return waiver
    return None


def load_cadet_flights(cadet: dict) -> list[dict]:
    if not cadet.get("flight_id"):
        return []
    flight = get_flight_by_id(cadet["flight_id"])
    return [flight] if flight else []


def count_absences(rows: list[dict], event_type: str) -> int:
    return sum(
        1
        for r in rows
        if r["event_type"].lower() == event_type.lower()
        and get_effective_attendance_status(
            r.get("status"),
            r.get("waiver_status"),
        )
        == "absent"
    )


def cadet_attendance(
    records: list[dict],
    events: list[dict],
    waivers: list[dict],
    standing_waivers: list[dict] | None = None,
) -> list[dict]:
    records = merge_attendance_records(records, key_fields=("event_id", "cadet_id"))
    event_map = {e["_id"]: e for e in events}
    waiver_map = {w["attendance_record_id"]: w for w in waivers}
    standing = standing_waivers or []

    rows = []
    for record in records:
        event = event_map.get(record.get("event_id"))
        waiver = waiver_map.get(record.get("_id"))

        if not event:
            continue

        waiver_status = (waiver.get("status") or "").lower() if waiver else None
        if waiver_status is None and standing:
            covering = _covering_standing_waiver(event, standing)
            if covering is not None:
                waiver_status = "approved"
        status = get_effective_attendance_status(
            record.get("status") or "—",
            waiver_status,
        )

        rows.append(
            {
                "record_id": str(record.get("_id", "")),
                "event_name": event.get("event_name", "—"),
                "event_type": (event.get("event_type") or "—").upper(),
                "start_date": event.get("start_date"),
                "status": status,
                "waiver_status": waiver_status,
                "waiver_eligible": (event.get("event_type") or "").lower()
                in ("pt", "lab"),
            }
        )
    rows.sort(
        key=lambda r: r["start_date"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return rows


def filter_rows(rows: list[dict], filter_status: str, filter_type: str) -> list[dict]:
    filtered = rows
    if filter_status != "All":
        if filter_status.lower() == "excused":
            filtered = [
                r
                for r in filtered
                if get_effective_attendance_status(
                    r.get("status"),
                    r.get("waiver_status"),
                )
                in ("excused", "waived")
            ]
        else:
            filtered = [
                r
                for r in filtered
                if get_effective_attendance_status(
                    r.get("status"),
                    r.get("waiver_status"),
                )
                == filter_status.lower()
            ]
    if filter_type != "All":
        filter_type = "LAB" if filter_type == "LLAB" else filter_type
        filtered = [r for r in filtered if r["event_type"] == filter_type]
    return filtered


def get_cadet_flight_label(cadet: dict, flights: list[dict]) -> str:
    if not cadet.get("flight_id"):
        return "—"
    for flight in flights:
        if flight["_id"] == cadet["flight_id"]:
            return flight.get("name", "—")
    return "—"


def get_attendance_rate(rows: list[dict], event_type: str) -> int:
    attended_llab = sum(
        1
        for r in rows
        if (
            r["status"] in ("present", "excused", "waived")
            and r["event_type"] == event_type
        )
    )
    llab_records = sum(1 for r in rows if r["event_type"] == event_type)
    attendance_rate_llab = (
        round(attended_llab / llab_records * 100) if llab_records else 0
    )

    return attendance_rate_llab
