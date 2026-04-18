def get_effective_attendance_status(
    status: str | None,
    waiver_status: str | None = None,
) -> str:
    normalized_status = (status or "").strip().lower()
    normalized_waiver_status = (waiver_status or "").strip().lower()

    if normalized_status == "absent" and normalized_waiver_status == "approved":
        return "waived"

    return normalized_status
