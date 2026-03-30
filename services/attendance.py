import secrets


def generate_attendance_password() -> str:
    """Generate a random 6-digit numeric attendance password."""
    return f"{secrets.randbelow(1000000):06}"


def is_already_checked_in(
    event_id: str,
    cadet_id: str,
    existing_records: list[dict],
) -> bool:
    return any(
        str(r.get("event_id")) == str(event_id)
        and str(r.get("cadet_id")) == str(cadet_id)
        for r in existing_records
    )
