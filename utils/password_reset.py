from __future__ import annotations

import secrets
import string
import time
from datetime import datetime
from typing import Any

import jwt

from utils.password import hash_password


def _to_int_timestamp(value: Any | None) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, datetime):
        return int(value.timestamp())

    return None


def generate_temp_password(length: int = 12) -> str:
    """Generate a temporary password suitable for one-time admin resets.

    - Avoid whitespace
    - Ensure at least one lowercase, uppercase, and digit
    """

    if length < 12:
        length = 12

    alphabet = string.ascii_letters + string.digits

    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not any(c.islower() for c in candidate):
            continue
        if not any(c.isupper() for c in candidate):
            continue
        if not any(c.isdigit() for c in candidate):
            continue
        return candidate


def build_password_updates(
    temp_password: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (updates, plaintext_temp_password).

    The updates payload is suitable to pass to `update_user`.
    """

    password = temp_password or generate_temp_password()
    updates = {
        "password_hash": hash_password(password),
        # store as unix seconds to keep comparisons simple and portable
        "password_changed_at": int(time.time()),
    }
    return updates, password


def generate_password_reset_token(
    *,
    email: str,
    secret: str,
    expires_in_seconds: int = 30 * 60,
    password_changed_at: Any | None,
) -> str:
    """Generate a signed, time-limited password reset token.

    `password_changed_at` is embedded so tokens are invalidated once the password changes.
    """

    now = int(time.time())
    payload: dict[str, Any] = {
        "email": (email or "").strip().lower(),
        "iat": now,
        "exp": now + int(expires_in_seconds),
    }

    pwd_ts = _to_int_timestamp(password_changed_at)
    if pwd_ts is not None:
        payload["pwd_ts"] = pwd_ts

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def validate_password_reset_token(
    *,
    token: str,
    secret: str,
    expected_email: str | None,
    current_password_changed_at: Any | None,
) -> dict[str, Any] | None:
    """Validate a reset token.

    Returns decoded claims on success, else None.

    Security properties:
    - Enforces `exp`
    - Optionally checks the token email matches the expected email
    - If the token carries a `pwd_ts` claim, requires it to match the user's current
      `password_changed_at` timestamp, so tokens become invalid after a reset.
    """

    if not token or not secret:
        return None

    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        return None

    token_email = str(claims.get("email", "") or "").strip().lower()
    if not token_email:
        return None

    if expected_email is not None:
        if token_email != (expected_email or "").strip().lower():
            return None

    token_pwd_ts = _to_int_timestamp(claims.get("pwd_ts"))
    if token_pwd_ts is not None:
        current_pwd_ts = _to_int_timestamp(current_password_changed_at)
        # If we can’t compute current pwd ts, treat as invalid.
        if current_pwd_ts is None or current_pwd_ts != token_pwd_ts:
            return None

    return claims
