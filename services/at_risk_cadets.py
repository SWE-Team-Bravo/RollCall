import pandas as pd

from utils.at_risk_email import get_at_risk_cadets
from utils.db_schema_crud import (
    get_all_cadets,
    get_approved_waivers_by_user,
    get_user_by_id,
)

WAIVER_FLAG_THRESHOLD = 3


def get_waiver_flagged_cadets() -> list[dict]:
    """Return cadets with WAIVER_FLAG_THRESHOLD or more approved waivers."""
    flagged = []
    for cadet in get_all_cadets():
        user_id = cadet.get("user_id")
        if user_id is None:
            continue
        approved = get_approved_waivers_by_user(user_id)
        count = len(approved)
        if count >= WAIVER_FLAG_THRESHOLD:
            user = get_user_by_id(user_id)
            flagged.append({"cadet": cadet, "user": user, "waiver_count": count})
    return sorted(flagged, key=lambda x: x["waiver_count"], reverse=True)


def get_waiver_flag_df() -> pd.DataFrame | str:
    flagged = get_waiver_flagged_cadets()
    if not flagged:
        return "No cadets flagged."
    rows = []
    for i, entry in enumerate(flagged):
        user = entry["user"] or {}
        rows.append(
            {
                "No.": i + 1,
                "First Name": str(user.get("first_name", "") or ""),
                "Last Name": str(user.get("last_name", "") or ""),
                "Approved Waivers": entry["waiver_count"],
            }
        )
    return pd.DataFrame(
        rows,
        columns=pd.Index(["No.", "First Name", "Last Name", "Approved Waivers"]),
    )


def filter_cadets(flight_id=None) -> list[dict]:
    cadets = get_at_risk_cadets()
    if flight_id is not None:
        cadets = [c for c in cadets if c["cadet"].get("flight_id") == flight_id]
    return sorted(
        cadets, key=lambda c: c["pt_absences"] + c["llab_absences"], reverse=True
    )


def get_df(flight_id=None) -> pd.DataFrame | str:
    cadets = filter_cadets(flight_id=flight_id)
    if not cadets:
        return "No cadets found."

    rows: list[dict[str, str | int]] = []
    for i, cadet in enumerate(cadets):
        rows.append(
            {
                "No.": i + 1,
                "First Name": str(cadet["cadet"].get("first_name", "") or ""),
                "Last Name": str(cadet["cadet"].get("last_name", "") or ""),
                "PT Absences": cadet["pt_absences"],
                "LLAB Absences": cadet["llab_absences"],
            }
        )

    return pd.DataFrame(
        rows,
        columns=pd.Index(
            ["No.", "First Name", "Last Name", "PT Absences", "LLAB Absences"]
        ),
    )
