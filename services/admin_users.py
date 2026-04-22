from __future__ import annotations

from typing import Any, Dict, List, Tuple
from utils.st_helpers import confirm_destructive_action


def summarize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    # Return a normalized summary for admin user listing.

    # id
    raw_id = user.get("_id")
    user_id = str(raw_id) if raw_id is not None else ""

    # email
    email = str(user.get("email", "") or "").strip()

    # name: prefer first/last (so edits show immediately), fallback to explicit name
    first = str(user.get("first_name", "") or "").strip()
    last = str(user.get("last_name", "") or "").strip()
    full = f"{first} {last}".strip()
    explicit_name = str(user.get("name", "") or "").strip()

    if full:
        name = full
    elif explicit_name:
        name = explicit_name
    elif email:
        name = email.split("@", 1)[0]
    else:
        name = "Unknown user"

    # role: prefer roles list, then single role field
    roles = user.get("roles") or []
    primary_role = ""
    if isinstance(roles, (list, tuple)) and roles:
        primary_role = str(roles[0])
    else:
        primary_role = str(user.get("role", "") or "")

    all_roles = roles if isinstance(roles, (list, tuple)) else []
    waiver_reviewer = "waiver_reviewer" in all_roles

    return {
        "id": user_id,
        "email": email,
        "name": name,
        "role": primary_role,
        "waiver_reviewer": waiver_reviewer,
    }


def list_users_for_admin(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Return normalized user summaries for the admin users page.

    summaries = [summarize_user(user) for user in users]

    # Sort by email (case-insensitive) so listing order is predictable.
    summaries.sort(key=lambda s: (s["email"].lower(), s["id"]))
    return summaries


ALLOWED_ROLES = {"admin", "cadre", "flight_commander", "cadet"}
DELETE_SUCCESS_MESSAGES = {
    "flight": "Flight deleted successfully.",
    "user": "User deleted successfully.",
    "waiver": "Waiver withdrawn successfully.",
}


def validate_new_user_data(
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    role: str,
    existing_emails: set[str],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Validate and normalize input for creating a new user.

    Returns (payload, errors). On success, errors is an empty dict and
    payload is suitable to pass to create_user (with a single role
    mapped to the roles list).
    """

    errors: Dict[str, str] = {}

    first = (first_name or "").strip()
    last = (last_name or "").strip()

    raw_email = (email or "").strip()
    if not raw_email:
        errors["email"] = "Email is required."
    elif "@" not in raw_email or "." not in raw_email.split("@", 1)[-1]:
        errors["email"] = "Email looks invalid."
    elif raw_email.lower() in {e.lower() for e in existing_emails}:
        errors["email"] = "A user with this email already exists."

    raw_password = password or ""
    if not raw_password:
        errors["password"] = "Password is required."
    elif len(raw_password) < 8:
        errors["password"] = "Password must be at least 8 characters long."

    raw_role = (role or "").strip()
    if not raw_role:
        errors["role"] = "Role is required."
    elif raw_role not in ALLOWED_ROLES:
        errors["role"] = "Invalid role selected."

    if errors:
        return {}, errors

    payload: Dict[str, Any] = {
        "first_name": first,
        "last_name": last,
        "email": raw_email,
        "password": raw_password,
        "roles": [raw_role],
    }

    return payload, {}


def build_update_user_payload(
    *,
    existing_user: Dict[str, Any],
    new_first_name: str,
    new_last_name: str,
    new_email: str,
    new_role: str,
    other_emails: set[str],
    waiver_reviewer: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Build an update dict for an existing user with validation.

    - If a field is left blank, the existing value is kept.
    - Email uniqueness is checked against other_emails (emails of all
      *other* users), so keeping the same email is allowed.
    - Role is validated against ALLOWED_ROLES.
    Returns (updates, errors). On success, errors is empty and updates
    can be passed directly to update_user.
    """

    errors: Dict[str, str] = {}

    # Start with existing values
    first = (new_first_name or existing_user.get("first_name", "")) or ""
    last = (new_last_name or existing_user.get("last_name", "")) or ""

    # Email: if new_email provided, validate; else keep existing
    existing_email = str(existing_user.get("email", "") or "").strip()
    raw_email = (new_email or existing_email).strip()

    if not raw_email:
        errors["email"] = "Email is required."
    elif "@" not in raw_email or "." not in raw_email.split("@", 1)[-1]:
        errors["email"] = "Email looks invalid."
    elif raw_email.lower() in {e.lower() for e in other_emails}:
        errors["email"] = "A user with this email already exists."

    # Role: if new_role provided, validate; else keep existing primary role
    existing_roles_value = existing_user.get("roles") or []
    if isinstance(existing_roles_value, (list, tuple)):
        existing_roles_seq = list(existing_roles_value)
    elif existing_roles_value:
        existing_roles_seq = [existing_roles_value]
    else:
        existing_roles_seq = []

    # Normalize existing roles to a list of unique, non-empty strings
    normalized_roles: list[str] = []
    for r in existing_roles_seq:
        s = str(r).strip()
        if s and s not in normalized_roles:
            normalized_roles.append(s)

    existing_primary_role = normalized_roles[0] if normalized_roles else ""
    raw_role = (new_role or existing_primary_role).strip()
    if not raw_role:
        errors["role"] = "Role is required."
    elif raw_role not in ALLOWED_ROLES:
        errors["role"] = "Invalid role selected."

    if errors:
        return {}, errors

    # Preserve secondary roles while updating primary role:
    # - Move the chosen role to the front
    # - Keep any other existing roles after it, without duplicates
    # - Add or remove "waiver_reviewer" based on the checkbox
    secondary = [
        r for r in normalized_roles if r != raw_role and r != "waiver_reviewer"
    ]
    updated_roles = [raw_role] + secondary
    if waiver_reviewer:
        updated_roles.append("waiver_reviewer")

    updates: Dict[str, Any] = {
        "first_name": first.strip(),
        "last_name": last.strip(),
        # Keep legacy/display name field in sync so admin listings update immediately.
        "name": f"{first.strip()} {last.strip()}".strip(),
        "email": raw_email,
        "roles": updated_roles,
    }

    return updates, {}


def confirm_delete_user(confirmation_input: str) -> bool:
    """Return True only if the admin has confirmed deletion.

    The current policy is that the admin must type the exact keyword
    "DELETE" (case-insensitive, ignoring surrounding whitespace).
    """

    return confirm_destructive_action(confirmation_input)


def get_delete_success_message(item_type: str) -> str:
    """Return a consistent success message for delete-style actions."""
    return DELETE_SUCCESS_MESSAGES.get(item_type, "Deleted successfully.")
