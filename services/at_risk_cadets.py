from utils.at_risk_email import get_at_risk_cadets
import pandas as pd


def filter_cadets() -> list[dict]:
    cadets = get_at_risk_cadets()
    return sorted(
        cadets, key=lambda c: c["pt_absences"] + c["llab_absences"], reverse=True
    )


def get_df() -> pd.DataFrame | str:
    cadets = filter_cadets()
    if not cadets:
        return "No cadets found."

    rows: list[dict[str, str | int]] = []
    cadet_by_id: dict[str, dict] = {}
    for i, cadet in enumerate(cadets):
        cid = str(cadet.get("_id"))
        cadet_by_id[cid] = cadet
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
