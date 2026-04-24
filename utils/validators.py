import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_NAME_RE = re.compile(r"[A-Za-z'-]+(?: [A-Za-z'-]+)*")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def is_valid_name(name: str) -> bool:
    return bool(_NAME_RE.fullmatch(name))
