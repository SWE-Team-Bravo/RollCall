import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "RollCall"
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "rollcall_db")
AUTH_COOKIE_KEY = os.getenv("AUTH_COOKIE_KEY")

HTML_THEME_OVERRIDE_COLORS = {
    "primary_button_enabled_text": "#000000",
    "primary_button_disabled_text_dark": "#f2f2f2",
    "primary_button_disabled_text_light": "#000000",
    "multiselect_tag_text": "#000000",
    "expander_border": "rgba(0, 0, 0, 0.12)",
    "expander_summary_background": "rgba(0, 0, 0, 0.08)",
    "expander_summary_hover_background": "rgba(0, 0, 0, 0.12)",
}
