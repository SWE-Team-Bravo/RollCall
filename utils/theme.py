import streamlit as st

THEME_OVERRIDES_CSS = """
<style>
button[kind*="primary"]:not(:disabled) {
    color: #000000 !important;
}
button[kind*="primary"]:not(:disabled) * {
    color: #000000 !important;
}
button[kind*="primary"]:disabled {
    color: #f2f2f2 !important;
}
button[kind*="primary"]:disabled * {
    color: #f2f2f2 !important;
}

.stMultiSelect [data-baseweb="select"] [data-baseweb="tag"] {
    color: #000000 !important;
}

.stMultiSelect [data-baseweb="select"] [data-baseweb="tag"] svg {
    color: currentColor !important;
    fill: currentColor !important;
}

[data-testid="stExpander"] {
    border-color: rgba(242, 242, 242, 0.18) !important;
}

[data-testid="stExpander"] details {
    background-color: #001F4D !important;
}

.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    background-color: #001F4D !important;
}

.stSelectbox [data-baseweb="select"]:hover > div,
.stMultiSelect [data-baseweb="select"]:hover > div {
    background-color: #00173A !important;
}
</style>
"""


def apply_theme_overrides() -> None:
    st.markdown(THEME_OVERRIDES_CSS, unsafe_allow_html=True)
