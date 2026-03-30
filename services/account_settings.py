from __future__ import annotations

from typing import Any, Dict, Tuple

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
