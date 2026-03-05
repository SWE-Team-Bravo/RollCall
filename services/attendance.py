import secrets


def generate_attendance_password() -> str:
    """Generate a random 6-digit numeric attendance password."""
    return f"{secrets.randbelow(1000000):06}"
