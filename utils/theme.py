import streamlit as st

from config.settings import HTML_THEME_OVERRIDE_COLORS


def _theme_overrides_css() -> str:
    colors = HTML_THEME_OVERRIDE_COLORS
    primary_disabled_text = (
        f"light-dark({colors['primary_button_disabled_text_light']}, "
        f"{colors['primary_button_disabled_text_dark']})"
    )
    return f"""
<style>
button[kind*="primary"]:not(:disabled) {{
    color: {colors["primary_button_enabled_text"]} !important;
}}
button[kind*="primary"]:not(:disabled) * {{
    color: {colors["primary_button_enabled_text"]} !important;
}}
button[kind*="primary"]:disabled {{
    color: {colors["primary_button_disabled_text_light"]} !important;
    color: {primary_disabled_text} !important;
}}
button[kind*="primary"]:disabled * {{
    color: {colors["primary_button_disabled_text_light"]} !important;
    color: {primary_disabled_text} !important;
}}

.stMultiSelect [data-baseweb="select"] [data-baseweb="tag"] {{
    color: {colors["multiselect_tag_text"]} !important;
}}

.stMultiSelect [data-baseweb="select"] [data-baseweb="tag"] svg {{
    color: currentColor !important;
    fill: currentColor !important;
}}

[data-testid="stExpander"] {{
    border-color: {colors["expander_border"]} !important;
}}

[data-testid="stExpander"] details {{
    background-color: transparent !important;
}}

[data-testid="stExpander"] details > summary {{
    background-color: {colors["expander_summary_background"]} !important;
}}

[data-testid="stExpander"] details > summary:hover {{
    background-color: {colors["expander_summary_hover_background"]} !important;
}}
</style>
"""


def apply_theme_overrides() -> None:
    st.markdown(_theme_overrides_css(), unsafe_allow_html=True)
