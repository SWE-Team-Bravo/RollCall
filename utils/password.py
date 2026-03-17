import bcrypt
from streamlit_authenticator import Hasher


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return Hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())
