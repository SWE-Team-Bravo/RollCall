import re
from bson import ObjectId
import secrets

import pandas as pd

from utils.db import get_collection
from utils.db_schema_crud import (
    assign_cadet_to_flight as db_assign_cadet_to_flight,
    create_cadet,
    get_cadet_by_id,
    get_user_by_email,
    get_user_by_id,
    get_all_cadets,
)
from utils.names import format_full_name

CLASS_TO_RANK = {
    "AS100": "100/150 (freshman)",
    "AS150": "100/150 (freshman)",
    "AS200": "200/250/500 (sophomore)",
    "AS250": "200/250/500 (sophomore)",
    "AS300": "300 (junior)",
    "AS400": "400 (senior)",
    "AS500": "200/250/500 (sophomore)",
    "AS700": "700/800/900 (super senior)",
    "AS800": "700/800/900 (super senior)",
    "AS900": "700/800/900 (super senior)",
}


def get_cadets_by_flight(flight_id) -> list[dict]:
    cadets_col = get_collection("cadets")
    flights_col = get_collection("flights")
    if cadets_col is None:
        return []

    cadets = list(cadets_col.find({"flight_id": ObjectId(flight_id)}))
    if flights_col is None:
        return cadets

    flight = flights_col.find_one({"_id": ObjectId(flight_id)})
    if not flight or not flight.get("commander_cadet_id"):
        return cadets

    return [cadet for cadet in cadets if cadet["_id"] != flight["commander_cadet_id"]]


def assign_cadet_to_flight(cadet_id, flight_id):
    cadet = get_cadet_by_id(cadet_id)
    if cadet and cadet.get("flight_id") == ObjectId(flight_id):
        raise ValueError("Cadet is already in this flight.")

    return db_assign_cadet_to_flight(cadet_id, flight_id)


def build_cadet_display_map() -> dict[str, str]:
    """Returns {"First Last (rank)": "cadet_id_string", ...}"""
    cadets = get_all_cadets()
    display_map = {}
    for cadet in cadets:
        user = get_user_by_id(cadet["user_id"])
        if user:
            name = format_full_name(user)
            rank = cadet.get("rank", "")
            display_map[f"{name} ({rank})"] = str(cadet["_id"])
    return display_map


def validate_cadet_input(
    first_name: str, last_name: str, email: str
) -> tuple[bool, str]:
    names_pattern = r"[A-Za-z'-]+(?: [A-Za-z'-]+)*"
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    if not first_name or not last_name or not email:
        return False, "Please fill all the fields!"
    if not re.fullmatch(names_pattern, first_name):
        return (
            False,
            "Please enter a valid first name! First name can only contain letters, apostrophes, and hyphens.",
        )
    if not re.fullmatch(names_pattern, last_name):
        return (
            False,
            "Please enter a valid last name! Last name can only contain letters, apostrophes, and hyphens.",
        )
    if not re.fullmatch(email_pattern, email):
        return False, "Please enter a valid email!"
    return True, ""


def add_cadet_for_user(email: str, rank: str, first_name: str, last_name: str) -> bool:
    user = get_user_by_email(email)
    if user is None:
        return False
    create_cadet(user["_id"], rank, first_name, last_name, email)
    return True


def get_cadet_export_df() -> pd.DataFrame | str:
    cadets = get_all_cadets()
    if not cadets:
        return "No cadets found."

    rows = []
    for cadet in cadets:
        user_id = cadet.get("user_id")
        user = get_user_by_id(user_id) if user_id is not None else None
        source = user or cadet
        rows.append(
            {
                "First Name": source.get("first_name", ""),
                "Last Name": source.get("last_name", ""),
                "Email": source.get("email", ""),
                "Rank": cadet.get("rank", ""),
            }
        )

    return pd.DataFrame(rows)


def parse_roster_xlsx(file) -> tuple[list[dict], list[str]]:
    try:
        df = pd.read_excel(file, sheet_name="Roster", header=2)
    except Exception as e:
        return [], [f"Failed to read Excel file: {e}"]
    email_pattern = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    cadets = []
    errors = []
    for _, row in df.iterrows():
        first_name = str(row.get("First Name", "") or "").strip()
        last_name = str(row.get("Last Name", "") or "").strip()
        kent_email = str(row.get("Kent Email", "") or "").strip()
        crosstown_email = str(row.get("Crosstown Email", "") or "").strip()
        class_level = str(row.get("Class", "") or "").strip().upper()
        if not first_name or first_name.lower() in ("nan", "first name"):
            continue
        if not last_name or last_name.lower() in ("nan", "last name"):
            continue
        email = (
            kent_email
            if kent_email and kent_email.lower() != "nan"
            else crosstown_email
        )
        if not email or email.lower() == "nan" or not email_pattern.match(email):
            errors.append(f"{first_name} {last_name}: no valid email, skipping.")
            continue
        rank = CLASS_TO_RANK.get(class_level, "100/150 (freshman)")
        cadets.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "rank": rank,
            }
        )
    return cadets, errors


def import_cadets_from_roster(cadets_data: list[dict]) -> dict:
    from utils.db_schema_crud import create_user, get_cadet_by_user_id

    created = []
    skipped = []
    errors = []
    for cadet in cadets_data:
        email = cadet["email"]
        first_name = cadet["first_name"]
        last_name = cadet["last_name"]
        rank = cadet["rank"]
        existing_user = get_user_by_email(email)
        if existing_user:
            existing_cadet = get_cadet_by_user_id(existing_user["_id"])
            if existing_cadet:
                skipped.append(
                    {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "reason": "User already exists",
                    }
                )
                continue
            try:
                create_cadet(existing_user["_id"], rank, first_name, last_name, email)
                created.append(
                    {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "rank": rank,
                        "temp_password": "(existing account)",
                    }
                )
            except Exception as e:
                errors.append(
                    {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "reason": str(e),
                    }
                )
            continue
        temp_password = secrets.token_urlsafe(10)
        try:
            user_result = create_user(
                first_name, last_name, email, temp_password, ["cadet"]
            )
            if user_result is None:
                errors.append(
                    {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "reason": "Database error creating user",
                    }
                )
                continue
            create_cadet(user_result.inserted_id, rank, first_name, last_name, email)
            created.append(
                {
                    "name": f"{first_name} {last_name}",
                    "email": email,
                    "rank": rank,
                    "temp_password": temp_password,
                }
            )
        except Exception as e:
            errors.append(
                {"name": f"{first_name} {last_name}", "email": email, "reason": str(e)}
            )
    return {"created": created, "skipped": skipped, "errors": errors}
