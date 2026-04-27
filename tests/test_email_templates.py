from services.email_templates import (
    _DEFAULT_TEMPLATES,
    get_content,
)


def test_roster_temp_password_default_template_exists():
    template = _DEFAULT_TEMPLATES["roster_temp_password"]
    assert "RollCall" in template["subject"]
    assert "{temporary_password}" in template["body"]


def test_get_content_substitutes_temporary_password():
    template = _DEFAULT_TEMPLATES["roster_temp_password"]
    subject, body = get_content(template, temporary_password="abc123")
    assert "RollCall" in subject
    assert "abc123" in body
    assert "{temporary_password}" not in body
    assert "{temporary_password}" not in subject
