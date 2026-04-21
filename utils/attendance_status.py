from typing import Any


STATUS_LABELS = {
    "present": "Present",
    "absent": "Absent",
    "excused": "Excused",
    "waived": "Excused",
}


def get_effective_attendance_status(
    status: str | None,
    waiver_status: str | None = None,
) -> str:
    normalized_status = (status or "").strip().lower()
    normalized_waiver_status = (waiver_status or "").strip().lower()

    if normalized_status == "absent" and normalized_waiver_status == "approved":
        return "waived"

    return normalized_status


def get_attendance_status_label(
    status: str | None,
    waiver_status: str | None = None,
    *,
    default: str = "",
) -> str:
    effective_status = get_effective_attendance_status(status, waiver_status)
    return STATUS_LABELS.get(effective_status, default)


def get_attendance_status_cell_style(val: Any) -> str:
    status = str(val or "")
    if status == "Present":
        return "background-color: #7FE08A; color: #0b2e13; font-weight: 700;"
    if status == "Absent":
        return "background-color: #E07F7F; color: #2b0b0b; font-weight: 700;"
    if status == "Excused":
        return "background-color: #E0D27F; color: #2b240b; font-weight: 700;"
    return ""
