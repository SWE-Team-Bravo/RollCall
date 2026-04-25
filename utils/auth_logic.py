def build_credentials_from_docs(
    docs: list[dict],
) -> tuple[dict, dict]:
    """Transform raw user documents into streamlit-authenticator credentials format.

    Returns (credentials, raw) where:
    - credentials is the dict expected by stauth.Authenticate
    - raw preserves the full doc keyed by email for later user lookup
    """
    raw: dict = {"usernames": {}}
    credentials: dict = {"usernames": {}}
    for doc in docs:
        email = doc["email"]
        raw["usernames"][email.lower()] = doc
        if bool(doc.get("disabled", False)):
            # Keep the user in raw lookup for admin views/history, but do not
            # add credentials so disabled accounts cannot log in.
            continue
        credentials["usernames"][email.lower()] = {
            "email": email,
            "name": f"{doc['first_name']} {doc['last_name']}".strip(),
            "password": doc["password_hash"],
        }
    return credentials, raw


def extract_user_from_raw(email: str | None, raw: dict) -> dict | None:
    """Build a user info dict from the raw users store given an email.

    Returns None if email is missing or not found.
    """
    if not email:
        return None
    user_info = raw.get("usernames", {}).get(email)
    if not user_info:
        return None
    return {
        "email": str(email),
        "first_name": str(user_info.get("first_name", "")),
        "last_name": str(user_info.get("last_name", "")),
        "roles": list(user_info.get("roles", [])),
        "disabled": bool(user_info.get("disabled", False)),
    }


def user_has_any_role(user: dict | None, roles: list[str] | tuple[str, ...]) -> bool:
    """Return True if user holds at least one of the required roles."""
    if user is None:
        return False
    return bool(set(user.get("roles", [])) & set(roles))
