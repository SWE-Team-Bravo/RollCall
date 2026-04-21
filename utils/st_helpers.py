import streamlit as st
from typing import TypeVar


T = TypeVar("T")


def require(val: T | None, message: str) -> T:
    if val is None:
        st.error(message)
        st.stop()
        raise RuntimeError("Unreachable")
    return val

def confirm_destructive_action(confirmation_input: str) -> bool:
    """Return True only when the exact DELETE keyword is entered."""
    return (confirmation_input or "").strip() == "DELETE"