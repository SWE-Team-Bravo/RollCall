from bson import ObjectId
import secrets
from typing import Any

import pandas as pd

from utils.audit_log import log_data_change, serialize_doc_for_audit
from utils.db import get_collection
from utils.db_schema_crud import (
    assign_cadet_to_flight as db_assign_cadet_to_flight,
    create_cadet,
    get_cadet_by_id,
    get_user_by_email,
    get_user_by_id,
    get_all_cadets,
    update_user,
    update_cadet,
    get_users_by_emails,
    get_users_by_names,
    get_cadets_by_user_ids_map,
)
from utils.names import format_full_name
from utils.validators import is_valid_email, is_valid_name
from utils.password_reset_email import send_temporary_password_email
from services.email_templates import get_email_template, get_content

RANK_OPTIONS = ("100", "150", "200", "250", "300", "400", "500", "700", "800", "900")

RANK_TO_LEVEL = {
    "100": "freshman",
    "150": "freshman",
    "200": "sophomore",
    "250": "sophomore",
    "300": "junior",
    "400": "senior",
    "500": "sophomore",
    "700": "super senior",
    "800": "super senior",
    "900": "super senior",
}

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
    if not first_name or not last_name or not email:
        return False, "Please fill all the fields!"
    if not is_valid_name(first_name):
        return (
            False,
            "Please enter a valid first name! First name can only contain letters, apostrophes, and hyphens.",
        )
    if not is_valid_name(last_name):
        return (
            False,
            "Please enter a valid last name! Last name can only contain letters, apostrophes, and hyphens.",
        )
    if not is_valid_email(email):
        return False, "Please enter a valid email!"
    return True, ""


def add_cadet_for_user(email: str, rank: str, first_name: str, last_name: str) -> bool:
    user = get_user_by_email(email)
    if user is None:
        return False
    create_cadet(
        user["_id"],
        rank,
        first_name,
        last_name,
        email,
    )
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
                "Level": (RANK_TO_LEVEL.get(str(cadet.get("rank")), "")).capitalize(),
            }
        )

    return pd.DataFrame(
        rows,
        columns=pd.Index(["No.", "First Name", "Last Name", "Email", "Rank", "Level"]),
    )


def parse_roster_xlsx(file) -> tuple[list[dict], list[str]]:
    try:
        df = pd.read_excel(file, sheet_name="Roster", header=2)
    except Exception as e:
        return [], [f"Failed to read Excel file: {e}"]
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
        if not email or email.lower() == "nan" or not is_valid_email(email):
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


def analyze_roster_for_import(cadets_data: list[dict]) -> list[dict]:
    """Cross-reference parsed roster rows against the DB and flag conflicts.

    Returns a list of dicts with added keys:
      - conflict_type: "none" | "email_exists" | "name_exists" | "intra_file_duplicate"
      - existing_user: the matched user doc (or None)
      - existing_cadet: the matched cadet doc (or None)
    """
    from collections import Counter

    email_counts: dict[str, int] = Counter(
        c["email"].lower().strip() for c in cadets_data
    )

    non_dup_emails = [
        e
        for e in {c["email"].lower().strip() for c in cadets_data}
        if email_counts.get(e, 0) <= 1
    ]
    users_by_email: dict[str, dict] = get_users_by_emails(non_dup_emails)

    name_lookup_keys = set()
    for c in cadets_data:
        email = c["email"].lower().strip()
        if email not in users_by_email and email_counts.get(email, 0) <= 1:
            name_lookup_keys.add((c["first_name"], c["last_name"]))
    users_by_name: dict[tuple[str, str], dict] = get_users_by_names(
        list(name_lookup_keys)
    )

    all_matched_user_ids = []
    for c in cadets_data:
        email = c["email"].lower().strip()
        existing_user = users_by_email.get(email)
        if not existing_user and email_counts.get(email, 0) <= 1:
            name_key = (c["first_name"].lower().strip(), c["last_name"].lower().strip())
            existing_user = users_by_name.get(name_key)
        if existing_user:
            all_matched_user_ids.append(existing_user["_id"])
    cadets_by_uid: dict[str, dict] = get_cadets_by_user_ids_map(all_matched_user_ids)

    results = []
    for c in cadets_data:
        email = c["email"].lower().strip()

        if email_counts.get(email, 0) > 1:
            results.append(
                {
                    **c,
                    "conflict_type": "intra_file_duplicate",
                    "existing_user": None,
                    "existing_cadet": None,
                }
            )
            continue

        existing_user = users_by_email.get(email)
        if existing_user:
            results.append(
                {
                    **c,
                    "conflict_type": "email_exists",
                    "existing_user": existing_user,
                    "existing_cadet": cadets_by_uid.get(str(existing_user["_id"])),
                }
            )
            continue

        name_key = (c["first_name"].lower().strip(), c["last_name"].lower().strip())
        existing_user = users_by_name.get(name_key)
        if existing_user:
            results.append(
                {
                    **c,
                    "conflict_type": "name_exists",
                    "existing_user": existing_user,
                    "existing_cadet": cadets_by_uid.get(str(existing_user["_id"])),
                }
            )
            continue

        results.append(
            {
                **c,
                "conflict_type": "none",
                "existing_user": None,
                "existing_cadet": None,
            }
        )

    return results


_DEFAULT_ACTION = {
    "none": "Create",
    "email_exists": "Update",
    "name_exists": "Skip",
    "intra_file_duplicate": "Skip",
}

_VALID_ACTIONS = {
    "none": ["Create"],
    "email_exists": ["Skip", "Update"],
    "name_exists": ["Skip", "Update", "Create as New"],
    "intra_file_duplicate": ["Skip"],
}

DEFAULT_ROSTER_IMPORT_ACTIONS = dict(_DEFAULT_ACTION)
VALID_ROSTER_IMPORT_ACTIONS = {
    conflict: list(actions) for conflict, actions in _VALID_ACTIONS.items()
}


def _log_roster_import_change(
    *,
    action: str,
    target_collection: str,
    target_id: Any,
    target_label: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor_user: dict[str, Any] | None,
) -> None:
    log_data_change(
        source="cadet_management",
        action=action,
        target_collection=target_collection,
        target_id=target_id,
        actor_user_id=actor_user.get("_id") if actor_user else None,
        actor_email=str(actor_user.get("email", "") or "").strip() or None
        if actor_user
        else None,
        actor_roles=list(actor_user.get("roles", [])) if actor_user else [],
        target_label=target_label,
        before=serialize_doc_for_audit(before),
        after=serialize_doc_for_audit(after),
        metadata={"workflow": "roster_import"},
    )


def import_cadets_from_roster(
    cadets_data: list[dict],
    actions: list[str] | None = None,
    *,
    actor_user: dict[str, Any] | None = None,
    email_temp_passwords: bool = False,
) -> dict:
    from utils.db_schema_crud import create_user

    created: list[dict] = []
    updated: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    email_failures: list[dict] = []

    for i, cadet in enumerate(cadets_data):
        # Backward-compatible: raw dicts without analysis get the old behavior
        if "conflict_type" not in cadet:
            from utils.db_schema_crud import (
                get_cadet_by_user_id as _get_cadet_by_user_id,
            )

            email = cadet["email"]
            first_name = cadet["first_name"]
            last_name = cadet["last_name"]
            rank = cadet["rank"]
            existing_user = get_user_by_email(email)
            full_name = format_full_name(cadet)
            if existing_user:
                existing_cadet = _get_cadet_by_user_id(existing_user["_id"])
                if existing_cadet:
                    skipped.append(
                        {
                            "name": full_name,
                            "email": email,
                            "reason": "User already exists",
                        }
                    )
                    continue
                try:
                    create_cadet(
                        existing_user["_id"], rank, first_name, last_name, email
                    )
                    created.append(
                        {
                            "name": full_name,
                            "email": email,
                            "rank": rank,
                            "temp_password": "(existing account)",
                        }
                    )
                except Exception as e:
                    errors.append(
                        {
                            "name": full_name,
                            "email": email,
                            "reason": str(e),
                        }
                    )
                continue
            # No existing user - fall through to normal creation below
            cadet["existing_user"] = None
            cadet["existing_cadet"] = None
            cadet["conflict_type"] = "none"

        conflict = cadet.get("conflict_type", "none")
        action = (
            actions[i].strip()
            if actions and i < len(actions)
            else _DEFAULT_ACTION.get(conflict, "Skip")
        )
        if action not in _VALID_ACTIONS.get(conflict, ["Skip"]):
            action = _DEFAULT_ACTION.get(conflict, "Skip")

        email = cadet["email"]
        first_name = cadet["first_name"]
        last_name = cadet["last_name"]
        full_name = format_full_name(cadet)
        rank = cadet["rank"]
        existing_user = cadet.get("existing_user")
        existing_cadet = cadet.get("existing_cadet")

        if action == "Skip":
            skipped.append(
                {
                    "name": full_name,
                    "email": email,
                    "reason": "Skipped by user",
                }
            )
            continue

        # --- Update existing record ---
        if action == "Update" and existing_user is not None:
            try:
                before_user = get_user_by_id(existing_user["_id"])
                update_user(
                    existing_user["_id"],
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "name": format_full_name(cadet),
                        "email": email,
                    },
                )
                after_user = get_user_by_id(existing_user["_id"])
                target_label = format_full_name(cadet, default=email)
                _log_roster_import_change(
                    action="update",
                    target_collection="users",
                    target_id=existing_user["_id"],
                    target_label=target_label,
                    before=before_user,
                    after=after_user,
                    actor_user=actor_user,
                )
                if existing_cadet:
                    before_cadet = get_cadet_by_id(existing_cadet["_id"])
                    update_cadet(
                        existing_cadet["_id"],
                        {
                            "first_name": first_name,
                            "last_name": last_name,
                            "email": email,
                            "rank": rank,
                        },
                    )
                    after_cadet = get_cadet_by_id(existing_cadet["_id"])
                    _log_roster_import_change(
                        action="update",
                        target_collection="cadets",
                        target_id=existing_cadet["_id"],
                        target_label=target_label,
                        before=before_cadet,
                        after=after_cadet,
                        actor_user=actor_user,
                    )
                else:
                    cadet_result = create_cadet(
                        existing_user["_id"], rank, first_name, last_name, email
                    )
                    created_cadet = (
                        get_cadet_by_id(cadet_result.inserted_id)
                        if cadet_result is not None
                        else None
                    )
                    _log_roster_import_change(
                        action="create",
                        target_collection="cadets",
                        target_id=created_cadet.get("_id") if created_cadet else None,
                        target_label=target_label,
                        before=None,
                        after=created_cadet,
                        actor_user=actor_user,
                    )
                updated.append(
                    {
                        "name": full_name,
                        "email": email,
                        "rank": rank,
                    }
                )
            except Exception as e:
                errors.append(
                    {
                        "name": full_name,
                        "email": email,
                        "reason": f"Failed to update account: {e}",
                    }
                )
            continue

        # --- Create as New ---
        if existing_user and get_user_by_email(email):
            errors.append(
                {
                    "name": full_name,
                    "email": email,
                    "reason": "Email already in use — cannot create a new account with this email.",
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
            update_user(user_result.inserted_id, {"force_password_change": True})
            created_user = get_user_by_id(user_result.inserted_id)
            target_label = format_full_name(cadet, default=email)
            _log_roster_import_change(
                action="create",
                target_collection="users",
                target_id=user_result.inserted_id,
                target_label=target_label,
                before=None,
                after=created_user,
                actor_user=actor_user,
            )
            cadet_result = create_cadet(
                user_result.inserted_id, rank, first_name, last_name, email
            )
            created_cadet = (
                get_cadet_by_id(cadet_result.inserted_id)
                if cadet_result is not None
                else None
            )
            _log_roster_import_change(
                action="create",
                target_collection="cadets",
                target_id=created_cadet.get("_id") if created_cadet else None,
                target_label=target_label,
                before=None,
                after=created_cadet,
                actor_user=actor_user,
            )
            created.append(
                {
                    "name": full_name,
                    "email": email,
                    "rank": rank,
                    "temp_password": temp_password,
                    "emailed": False,
                }
            )
            if email_temp_passwords:
                template = get_email_template("roster_temp_password")
                subject, body = get_content(
                    template, temporary_password=temp_password
                )
                sent = send_temporary_password_email(
                    to_email=email,
                    temporary_password=temp_password,
                    subject=subject,
                    body=body,
                )
                if sent:
                    created[-1]["emailed"] = True
                else:
                    email_failures.append(
                        {
                            "name": full_name,
                            "email": email,
                            "reason": "Failed to send temporary password email",
                        }
                    )
        except Exception as e:
            errors.append(
                {
                    "name": full_name,
                    "email": email,
                    "reason": f"Failed to create account: {e}",
                }
            )

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "email_failures": email_failures,
    }


def send_temp_passwords_to_created_cadets(
    created: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Email temporary passwords to created cadets that haven't been emailed yet.

    Mutates each dict in *created* to set ``emailed`` to ``True`` on success.

    Returns ``(pending, failures)`` where *pending* is the subset of *created*
    still not emailed and *failures* describes the send attempts that failed.
    """
    failures: list[dict] = []
    template = get_email_template("roster_temp_password")
    for c in created:
        if c.get("emailed"):
            continue
        subject, body = get_content(template, temporary_password=c["temp_password"])
        sent = send_temporary_password_email(
            to_email=c["email"],
            temporary_password=c["temp_password"],
            subject=subject,
            body=body,
        )
        if sent:
            c["emailed"] = True
        else:
            failures.append(
                {
                    "name": c["name"],
                    "email": c["email"],
                    "reason": "Failed to send temporary password email",
                }
            )
    pending = [c for c in created if not c.get("emailed")]
    return pending, failures
