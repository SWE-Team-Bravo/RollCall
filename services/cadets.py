import re

from utils.db import get_collection
from utils.db_schema_crud import create_cadet, get_user_by_email, get_user_by_id


def get_all_cadets() -> list[dict]:
    col = get_collection("cadets")
    if col is None:
        return []
    return list(col.find())


def get_cadets_by_flight(flight_id) -> list[dict]:
    from bson import ObjectId
    col = get_collection("cadets")
    if col is None:
        return []
    return list(col.find({"flight_id": ObjectId(flight_id)}))


def build_cadet_display_map() -> dict[str, str]:
    """Returns {"First Last (rank)": "cadet_id_string", ...}"""
    cadets = get_all_cadets()
    display_map = {}
    for cadet in cadets:
        user = get_user_by_id(cadet["user_id"])
        if user:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            rank = cadet.get("rank", "")
            display_map[f"{name} ({rank})"] = str(cadet["_id"])
    return display_map


def validate_cadet_input(first_name: str, last_name: str, email: str) -> tuple[bool, str]:
    names_pattern = r"[A-Za-z'-]+(?: [A-Za-z'-]+)*"
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    if not first_name or not last_name or not email:
        return False, "Please fill all the fields!"
    if not re.fullmatch(names_pattern, first_name):
        return False, "Please enter a valid first name! First name can only contain letters, apostrophes, and hyphens."
    if not re.fullmatch(names_pattern, last_name):
        return False, "Please enter a valid last name! Last name can only contain letters, apostrophes, and hyphens."
    if not re.fullmatch(email_pattern, email):
        return False, "Please enter a valid email!"
    return True, ""


def add_cadet_for_user(email: str, rank: str, first_name: str, last_name: str) -> bool:
    """Look up user by email and create a cadet profile. Returns True on success."""
    user = get_user_by_email(email)
    if user is None:
        return False
    create_cadet(user["_id"], rank, first_name, last_name)
    return True
