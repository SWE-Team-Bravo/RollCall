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
    border-color: rgba(0, 0, 0, 0.12) !important;
}

[data-testid="stExpander"] details {
    background-color: transparent !important;
}

[data-testid="stExpander"] details > summary {
    background-color: rgba(0, 0, 0, 0.08) !important;
}

[data-testid="stExpander"] details > summary:hover {
    background-color: rgba(0, 0, 0, 0.12) !important;
}
</style>
"""


def apply_theme_overrides() -> None:
    st.markdown(THEME_OVERRIDES_CSS, unsafe_allow_html=True)
