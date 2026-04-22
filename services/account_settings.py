from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

from utils.password import hash_password, verify_password


def build_password_change_updates(
    *,
    user_doc: Dict[str, Any],
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Validate a password change request and build an update payload.

    Returns (updates, errors).
    On success: errors is empty and updates contains only {"password_hash": ...}.
    """

    errors: Dict[str, str] = {}

    stored_hash = user_doc.get("password_hash")
    if not stored_hash or not isinstance(stored_hash, str):
        errors["current_password"] = "Account is missing a stored password hash."
        return {}, errors

    raw_current = current_password or ""
    if not raw_current:
        errors["current_password"] = "Current password is required."
    elif not verify_password(raw_current, stored_hash):
        errors["current_password"] = "Current password is incorrect."

    raw_new = new_password or ""
    if not raw_new:
        errors["new_password"] = "New password is required."
    elif len(raw_new) < 8:
        errors["new_password"] = "New password must be at least 8 characters long."

    raw_confirm = confirm_password or ""
    if not raw_confirm:
        errors["confirm_password"] = "Please confirm your new password."
    elif raw_new and raw_confirm != raw_new:
        errors["confirm_password"] = "New passwords do not match."

    if errors:
        return {}, errors

    return {"password_hash": hash_password(raw_new)}, {}


def build_profile_updates(
    *,
    user_doc: Dict[str, Any],
    first_name: str,
    last_name: str,
    email: str,
    lookup_user_by_email: Callable[[str], Dict[str, Any] | None],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Validate a profile update request and build an update payload.

    Validation:
    - first/last name must be non-empty after stripping
    - email must be non-empty and look valid
    - email must be unique (case-insensitive), excluding the current user

    Returns (updates, errors).
    On success: errors is empty and updates contains first_name/last_name/email/name.
    """

    errors: Dict[str, str] = {}

    first = (first_name or "").strip()
    last = (last_name or "").strip()
    raw_email = (email or "").strip()

    if not first:
        errors["first_name"] = "First name is required."
    if not last:
        errors["last_name"] = "Last name is required."

    if not raw_email:
        errors["email"] = "Email is required."
    elif "@" not in raw_email or "." not in raw_email.split("@", 1)[-1]:
        errors["email"] = "Email looks invalid."

    if errors:
        return {}, errors

    existing_email = str(user_doc.get("email", "") or "").strip()
    if raw_email.lower() != existing_email.lower():
        found = lookup_user_by_email(raw_email)
        if found is not None:
            found_id = found.get("_id")
            current_id = user_doc.get("_id")
            if (
                found_id is None
                or current_id is None
                or str(found_id) != str(current_id)
            ):
                return {}, {"email": "A user with this email already exists."}

    updates: Dict[str, Any] = {
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}".strip(),
        "email": raw_email,
    }

    return updates, {}
