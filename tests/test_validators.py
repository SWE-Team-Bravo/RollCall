import pytest

from utils.validators import is_valid_email, is_valid_name


@pytest.mark.parametrize(
    "email",
    [
        "user@example.com",
        "cadet.name@af.mil",
        "first.last+tag@subdomain.example.org",
        "a@b.io",
    ],
)
def test_valid_emails_are_accepted(email: str) -> None:
    assert is_valid_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "notanemail",
        "missing-at-sign.com",
        "@nodomain",
        "user@",
        "user@nodot",
        "user@@double.com",
    ],
)
def test_invalid_emails_are_rejected(email: str) -> None:
    assert is_valid_email(email) is False


@pytest.mark.parametrize(
    "name",
    [
        "Smith",
        "O'Brien",
        "Anne-Marie",
        "Mary Jane",
    ],
)
def test_valid_names_are_accepted(name: str) -> None:
    assert is_valid_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "",
        "123",
        "Smith!",
        "two  spaces",
    ],
)
def test_invalid_names_are_rejected(name: str) -> None:
    assert is_valid_name(name) is False
