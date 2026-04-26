import io
from unittest.mock import MagicMock, patch

import openpyxl

from services.cadets import (
    CLASS_TO_RANK,
    DEFAULT_ROSTER_IMPORT_ACTIONS,
    VALID_ROSTER_IMPORT_ACTIONS,
    import_cadets_from_roster,
    parse_roster_xlsx,
    analyze_roster_for_import,
)


def _make_roster_xlsx(rows: list[dict]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Roster"
    ws.append([2])  # row 0: matches real template structure
    ws.append(["Total Cadets:", len(rows)])  # row 1: metadata
    ws.append(
        [
            "Class",
            "Rank",
            "Last Name",
            "First Name",
            "MI",
            "Kent Email",
            "Crosstown Email",
        ]
    )  # row 2: header
    for r in rows:
        ws.append(
            [
                r.get("Class", ""),
                r.get("Rank", ""),
                r.get("Last Name", ""),
                r.get("First Name", ""),
                r.get("MI", ""),
                r.get("Kent Email", ""),
                r.get("Crosstown Email", ""),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# -- parse_roster_xlsx tests


def test_parse_valid_row():
    f = _make_roster_xlsx(
        [
            {
                "Class": "AS100",
                "First Name": "John",
                "Last Name": "Doe",
                "Kent Email": "jdoe@kent.edu",
            }
        ]
    )
    cadets, errors = parse_roster_xlsx(f)
    assert len(cadets) == 1
    assert cadets[0]["first_name"] == "John"
    assert cadets[0]["last_name"] == "Doe"
    assert cadets[0]["email"] == "jdoe@kent.edu"
    assert cadets[0]["rank"] == "100/150 (freshman)"
    assert errors == []


def test_parse_uses_crosstown_when_no_kent_email():
    f = _make_roster_xlsx(
        [
            {
                "Class": "AS200",
                "First Name": "Jane",
                "Last Name": "Smith",
                "Crosstown Email": "jsmith@ua.edu",
            }
        ]
    )
    cadets, errors = parse_roster_xlsx(f)
    assert len(cadets) == 1
    assert cadets[0]["email"] == "jsmith@ua.edu"
    assert cadets[0]["rank"] == "200/250/500 (sophomore)"


def test_parse_skips_row_with_no_email():
    f = _make_roster_xlsx(
        [{"Class": "AS100", "First Name": "No", "Last Name": "Email"}]
    )
    cadets, errors = parse_roster_xlsx(f)
    assert cadets == []
    assert len(errors) == 1
    assert "No Email" in errors[0]


def test_parse_skips_row_with_invalid_email():
    f = _make_roster_xlsx(
        [
            {
                "Class": "AS100",
                "First Name": "Bad",
                "Last Name": "Email",
                "Kent Email": "not-an-email",
            }
        ]
    )
    cadets, errors = parse_roster_xlsx(f)
    assert cadets == []
    assert len(errors) == 1


def test_parse_skips_empty_rows():
    f = _make_roster_xlsx(
        [
            {
                "Class": "AS100",
                "First Name": "John",
                "Last Name": "Doe",
                "Kent Email": "jdoe@kent.edu",
            },
            {},
        ]
    )
    cadets, errors = parse_roster_xlsx(f)
    assert len(cadets) == 1


def test_parse_unknown_class_defaults_to_freshman():
    f = _make_roster_xlsx(
        [
            {
                "Class": "UNKNOWN",
                "First Name": "X",
                "Last Name": "Y",
                "Kent Email": "xy@kent.edu",
            }
        ]
    )
    cadets, _ = parse_roster_xlsx(f)
    assert cadets[0]["rank"] == "100/150 (freshman)"


def test_parse_returns_error_on_bad_file():
    buf = io.BytesIO(b"not an excel file")
    cadets, errors = parse_roster_xlsx(buf)
    assert cadets == []
    assert len(errors) == 1
    assert "Failed to read" in errors[0]


def test_class_to_rank_mapping_complete():
    for key in [
        "AS100",
        "AS150",
        "AS200",
        "AS250",
        "AS300",
        "AS400",
        "AS500",
        "AS700",
        "AS800",
        "AS900",
    ]:
        assert key in CLASS_TO_RANK


# -- import_cadets_from_roster tests


@patch("services.cadets.get_user_by_email")
@patch("services.cadets.create_cadet")
@patch("utils.db_schema_crud.get_cadet_by_user_id")
def test_import_skips_existing_user(mock_get_cadet, mock_create_cadet, mock_get_user):
    from bson import ObjectId

    existing_id = ObjectId()
    mock_get_user.return_value = {"_id": existing_id}
    mock_get_cadet.return_value = {"_id": ObjectId(), "user_id": existing_id}
    result = import_cadets_from_roster(
        [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "jdoe@kent.edu",
                "rank": "100/150 (freshman)",
            }
        ]
    )
    assert len(result["skipped"]) == 1
    assert result["created"] == []
    mock_create_cadet.assert_not_called()


@patch("services.cadets.get_user_by_email")
@patch("services.cadets.create_cadet")
@patch("services.cadets.get_cadet_by_id")
@patch("services.cadets.get_user_by_id")
@patch("services.cadets.log_data_change")
@patch("utils.db_schema_crud.create_user")
def test_import_creates_user_and_cadet(
    mock_create_user,
    mock_log_data_change,
    mock_get_user_by_id,
    mock_get_cadet_by_id,
    mock_create_cadet,
    mock_get_user,
):
    mock_get_user.return_value = None
    inserted = MagicMock()
    inserted.inserted_id = MagicMock()
    created_cadet_result = MagicMock()
    created_cadet_result.inserted_id = MagicMock()
    mock_create_cadet.return_value = created_cadet_result
    mock_create_user.return_value = inserted
    mock_get_user_by_id.return_value = {
        "_id": inserted.inserted_id,
        "email": "jdoe@kent.edu",
    }
    mock_get_cadet_by_id.return_value = {
        "_id": created_cadet_result.inserted_id,
        "email": "jdoe@kent.edu",
    }
    result = import_cadets_from_roster(
        [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "jdoe@kent.edu",
                "rank": "100/150 (freshman)",
            }
        ]
    )
    assert len(result["created"]) == 1
    assert result["created"][0]["email"] == "jdoe@kent.edu"
    assert "temp_password" in result["created"][0]
    assert result["skipped"] == []
    assert result["errors"] == []
    assert mock_log_data_change.call_count == 2


@patch("services.cadets.get_user_by_email")
@patch("utils.db_schema_crud.create_user")
def test_import_handles_db_error(mock_create_user, mock_get_user):
    mock_get_user.return_value = None
    mock_create_user.side_effect = Exception("DB error")
    result = import_cadets_from_roster(
        [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "jdoe@kent.edu",
                "rank": "100/150 (freshman)",
            }
        ]
    )
    assert len(result["errors"]) == 1
    assert "DB error" in result["errors"][0]["reason"]


@patch("services.cadets.get_user_by_email")
@patch("utils.db_schema_crud.create_user")
def test_import_returns_none_user_goes_to_errors(mock_create_user, mock_get_user):
    mock_get_user.return_value = None
    mock_create_user.return_value = None
    result = import_cadets_from_roster(
        [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "jdoe@kent.edu",
                "rank": "100/150 (freshman)",
            }
        ]
    )
    assert len(result["errors"]) == 1


# -- analyze_roster_for_import tests


@patch("services.cadets.get_cadets_by_user_ids_map")
@patch("services.cadets.get_users_by_names")
@patch("services.cadets.get_users_by_emails")
def test_analyze_flags_email_conflict(mock_get_emails, mock_get_names, mock_get_cadets):
    from bson import ObjectId

    existing_id = ObjectId()
    mock_get_emails.return_value = {"jdoe@kent.edu": {"_id": existing_id}}
    mock_get_names.return_value = {}
    mock_get_cadets.return_value = {
        str(existing_id): {"_id": ObjectId(), "user_id": existing_id}
    }
    result = analyze_roster_for_import(
        [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "jdoe@kent.edu",
                "rank": "100",
            }
        ]
    )
    assert len(result) == 1
    assert result[0]["conflict_type"] == "email_exists"
    assert result[0]["existing_user"]["_id"] == existing_id


@patch("services.cadets.get_cadets_by_user_ids_map")
@patch("services.cadets.get_users_by_names")
@patch("services.cadets.get_users_by_emails")
def test_analyze_flags_name_conflict(mock_get_emails, mock_get_names, mock_get_cadets):
    from bson import ObjectId

    existing_id = ObjectId()
    mock_get_emails.return_value = {}
    mock_get_names.return_value = {("jane", "smith"): {"_id": existing_id}}
    mock_get_cadets.return_value = {str(existing_id): None}
    result = analyze_roster_for_import(
        [
            {
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@kent.edu",
                "rank": "200",
            }
        ]
    )
    assert len(result) == 1
    assert result[0]["conflict_type"] == "name_exists"
    assert result[0]["existing_user"]["_id"] == existing_id


def test_analyze_flags_intra_file_duplicate():
    result = analyze_roster_for_import(
        [
            {
                "first_name": "A",
                "last_name": "B",
                "email": "dup@kent.edu",
                "rank": "100",
            },
            {
                "first_name": "C",
                "last_name": "D",
                "email": "dup@kent.edu",
                "rank": "200",
            },
        ]
    )
    assert result[0]["conflict_type"] == "intra_file_duplicate"
    assert result[1]["conflict_type"] == "intra_file_duplicate"


@patch("services.cadets.get_cadets_by_user_ids_map")
@patch("services.cadets.get_users_by_names")
@patch("services.cadets.get_users_by_emails")
def test_analyze_no_conflict(mock_get_emails, mock_get_names, mock_get_cadets):
    mock_get_emails.return_value = {}
    mock_get_names.return_value = {}
    mock_get_cadets.return_value = {}
    result = analyze_roster_for_import(
        [
            {
                "first_name": "New",
                "last_name": "User",
                "email": "new@kent.edu",
                "rank": "100",
            }
        ]
    )
    assert result[0]["conflict_type"] == "none"
    assert result[0]["existing_user"] is None


# -- import with explicit actions


@patch("services.cadets.update_user")
@patch("services.cadets.update_cadet")
@patch("services.cadets.get_cadet_by_id")
@patch("services.cadets.get_user_by_id")
@patch("services.cadets.log_data_change")
def test_import_update_existing(
    mock_log_data_change,
    mock_get_user_by_id,
    mock_get_cadet_by_id,
    mock_update_cadet,
    mock_update_user,
):
    from bson import ObjectId

    existing_id = ObjectId()
    cadet_id = ObjectId()
    mock_get_user_by_id.side_effect = [
        {"_id": existing_id, "email": "old@kent.edu"},
        {"_id": existing_id, "email": "jdoe@kent.edu"},
    ]
    mock_get_cadet_by_id.side_effect = [
        {"_id": cadet_id, "user_id": existing_id, "rank": "100/150 (freshman)"},
        {"_id": cadet_id, "user_id": existing_id, "rank": "200/250/500 (sophomore)"},
    ]
    row = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@kent.edu",
        "rank": "200/250/500 (sophomore)",
        "conflict_type": "email_exists",
        "existing_user": {"_id": existing_id},
        "existing_cadet": {"_id": cadet_id, "user_id": existing_id},
    }
    result = import_cadets_from_roster([row], actions=["Update"])
    assert len(result["updated"]) == 1
    assert result["updated"][0]["email"] == "jdoe@kent.edu"
    mock_update_user.assert_called_once()
    mock_update_cadet.assert_called_once()
    assert mock_log_data_change.call_count == 2


@patch("services.cadets.create_cadet")
@patch("services.cadets.update_user")
@patch("services.cadets.get_cadet_by_id")
@patch("services.cadets.get_user_by_id")
@patch("services.cadets.log_data_change")
def test_import_update_existing_user_no_cadet(
    mock_log_data_change,
    mock_get_user_by_id,
    mock_get_cadet_by_id,
    mock_update_user,
    mock_create_cadet,
):
    from bson import ObjectId

    existing_id = ObjectId()
    created_cadet_id = ObjectId()
    mock_get_user_by_id.side_effect = [
        {"_id": existing_id, "email": "old@kent.edu"},
        {"_id": existing_id, "email": "jdoe@kent.edu"},
    ]
    mock_create_cadet.return_value = MagicMock(inserted_id=created_cadet_id)
    mock_get_cadet_by_id.return_value = {
        "_id": created_cadet_id,
        "user_id": existing_id,
        "rank": "100/150 (freshman)",
    }
    row = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@kent.edu",
        "rank": "100/150 (freshman)",
        "conflict_type": "email_exists",
        "existing_user": {"_id": existing_id},
        "existing_cadet": None,
    }
    result = import_cadets_from_roster([row], actions=["Update"])
    assert len(result["updated"]) == 1
    mock_create_cadet.assert_called_once()
    assert mock_log_data_change.call_count == 2


def test_import_skip_via_action():
    from bson import ObjectId

    existing_id = ObjectId()
    row = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "jdoe@kent.edu",
        "rank": "100/150 (freshman)",
        "conflict_type": "email_exists",
        "existing_user": {"_id": existing_id},
        "existing_cadet": {"_id": ObjectId(), "user_id": existing_id},
    }
    result = import_cadets_from_roster([row], actions=["Skip"])
    assert len(result["skipped"]) == 1
    assert result["updated"] == []
    assert result["created"] == []


def test_roster_import_action_config_exports():
    assert DEFAULT_ROSTER_IMPORT_ACTIONS["none"] == "Create"
    assert DEFAULT_ROSTER_IMPORT_ACTIONS["email_exists"] == "Update"
    assert VALID_ROSTER_IMPORT_ACTIONS["name_exists"] == [
        "Skip",
        "Update",
        "Create as New",
    ]
