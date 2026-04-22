from typing import Any, Mapping


def format_full_name(user: Mapping[str, Any] | None, default: str = "") -> str:
    if not user:
        return default

    first = str(user.get("first_name", "") or "").strip()
    last = str(user.get("last_name", "") or "").strip()
    return f"{first} {last}".strip() or default
