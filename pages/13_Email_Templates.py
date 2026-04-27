import streamlit as st
from utils.auth import require_role
from services.email_templates import (
    get_email_template,
    save_email_template,
    _DEFAULT_TEMPLATES,
)

TEMPLATE_KEYS = list(_DEFAULT_TEMPLATES.keys())

TEMPLATE_LABELS = {
    "waiver_decision": "Waiver Decision (approved/denied)",
    "waiver_reminder": "Waiver Pending Reminder",
    "at_risk_cadre": "At-Risk Report (cadre/FC)",
    "at_risk_student": "At-Risk Alert (cadet)",
    "test_email": "Test Email",
    "roster_temp_password": "Temporary Password",
}

TEMPLATE_VARIABLES = {
    "waiver_decision": "{status}, {event_name}, {event_date}, {comments}",
    "waiver_reminder": "{cadet_name}, {event_name}, {event_date}, {days_pending}, {waiver_id}",
    "at_risk_cadre": "{recipient_name}, {pt_threshold}, {llab_threshold}, {table}",
    "at_risk_student": "{message}",
    "test_email": "no variables",
    "roster_temp_password": "{temporary_password}",
}


require_role("admin")


st.title("Email Templates")
st.caption(
    "Customize email subjects and body text. Use {variable} placeholders for dynamic content."
)

selected_key = st.selectbox(
    "Select template",
    options=TEMPLATE_KEYS,
    format_func=lambda k: TEMPLATE_LABELS.get(k, k),
)

st.markdown(f"Available variables: `{TEMPLATE_VARIABLES.get(selected_key, '')}`")

template = get_email_template(selected_key)
default = _DEFAULT_TEMPLATES[selected_key]

if st.button("Reset to Default"):
    save_email_template(selected_key, default["subject"], default["body"])
    st.session_state.pop(f"subject_{selected_key}", None)
    st.session_state.pop(f"body_{selected_key}", None)
    st.rerun()

subject = st.text_input(
    "Subject",
    value=template["subject"],
    key=f"subject_{selected_key}",
)

body = st.text_area(
    "Body",
    value=template["body"],
    height=300,
    key=f"body_{selected_key}",
)

if st.button("Save Template"):
    if not subject.strip():
        st.error("Subject cannot be empty.")
    elif not body.strip():
        st.error("Body cannot be empty.")
    else:
        if save_email_template(selected_key, subject.strip(), body.strip()):
            st.session_state.template_saved = True
            st.rerun()
        else:
            st.error("Database unavailable — could not save template.")

if st.session_state.get("template_saved"):
    st.success("Template saved.")
    st.session_state.template_saved = False
