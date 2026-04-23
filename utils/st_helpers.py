from typing import TypeVar

import streamlit as st

T = TypeVar("T")


def require(val: T | None, message: str) -> T:
    if val is None:
        st.error(message)
        st.stop()
        raise RuntimeError("Unreachable")
    return val
