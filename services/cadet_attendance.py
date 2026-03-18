from datetime import datetime, timezone


def count_absences(rows: list[dict], event_type: str) -> int:
    return sum(
        1
        for r in rows
        if r["event_type"].lower() == event_type.lower() and r["status"] == "absent"
    )


def cadet_attendance(
    records: list[dict],
    events: list[dict],
    waivers: list[dict],
) -> list[dict]:
    event_by_id = {e["_id"]: e for e in events}
    waiver_by_record_id = {w["attendance_record_id"]: w for w in waivers}

    rows = []
    for record in records:
        event = event_by_id.get(record.get("event_id"))
        if not event:
            continue
        waiver = waiver_by_record_id.get(record["_id"])
        rows.append(
            {
                "record_id": str(record["_id"]),
                "event_name": event.get("event_name", "—"),
                "event_type": (event.get("event_type") or "—").upper(),
                "start_date": event.get("start_date"),
                "status": (record.get("status") or "—").lower(),
                "waiver_status": (waiver.get("status") or "").lower()
                if waiver
                else None,
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
            filtered = [r for r in filtered if r["status"] in ("excused", "waived")]
        else:
            filtered = [r for r in filtered if r["status"] == filter_status.lower()]
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
