from datetime import datetime
from typing import Any


def normalize_status(status: str | None) -> str:
    """Normalize a raw attendance status string to P/A/E."""
    if not status:
        return "A"
    s = status.strip().lower()
    if s == "present":
        return "P"
    if s == "absent":
        return "A"
    if s in ("excused", "waived"):
        return "E"
    return "A"


def format_event_row_label(event: dict[str, Any]) -> str:
    """Format an event document into a display label: 'YYYY-MM-DD — Event Name'."""
    sd = event.get("start_date")
    if isinstance(sd, datetime):
        date_str = sd.strftime("%Y-%m-%d")
    else:
        date_str = str(sd)[:10] if sd else "Unknown date"
    name = event.get("event_name") or event.get("name") or ""
    return f"{date_str} — {name}" if name else date_str


def build_attendance_grid(
    cadet_docs: list[dict],
    user_docs: list[dict],
    event_docs: list[dict],
    record_docs: list[dict],
) -> tuple[list[str], list[str], list[list[str]]]:
    """Build the attendance grid data for the dashboard.

    Returns:
        (event_row_labels, cadet_name_columns, grid_rows)
        where grid_rows[i][j] is the P/A/E status for event i and cadet j.
    """
    name_by_user_id = {
        u["_id"]: f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "Unknown"
        for u in user_docs
    }

    cadet_name_by_id = {
        c["_id"]: name_by_user_id.get(c.get("user_id"), "Unknown")
        for c in cadet_docs
    }

    cadet_pairs = sorted(cadet_name_by_id.items(), key=lambda x: x[1].lower())
    cadet_ids_sorted = [cid for cid, _ in cadet_pairs]
    cadet_names_sorted = [nm for _, nm in cadet_pairs]

    def event_sort_key(e: dict) -> Any:
        sd = e.get("start_date")
        return sd if isinstance(sd, datetime) else str(sd or "")

    event_docs_sorted = sorted(event_docs, key=event_sort_key, reverse=True)
    event_ids_sorted = [e["_id"] for e in event_docs_sorted]
    event_row_labels = [format_event_row_label(e) for e in event_docs_sorted]

    status_by_pair: dict[tuple, str] = {}
    for r in record_docs:
        key = (r.get("event_id"), r.get("cadet_id"))
        status_by_pair[key] = normalize_status(r.get("status"))

    grid_rows: list[list[str]] = []
    for ev_id in event_ids_sorted:
        row = [status_by_pair.get((ev_id, cid), "A") for cid in cadet_ids_sorted]
        grid_rows.append(row)

    return event_row_labels, cadet_names_sorted, grid_rows
