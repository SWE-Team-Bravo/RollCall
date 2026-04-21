from unittest.mock import patch, MagicMock
from bson import ObjectId
import pandas as pd
import pytest

from utils.db_schema_crud import (
    create_flight,
    unassign_cadet_from_flight,
    assign_cadet_to_flight,
    unassign_all_cadets_from_flight,
)
from services.cadets import assign_cadet_to_flight as assign_cadet_to_flight_service
from services.flight_management import (
    assign_selected_cadets_to_flight,
    get_assignment_table,
    get_cadet_rows_by_id,
    get_commander_member_table,
    get_flight_commander_details,
    get_flight_management_cadet_rows,
    get_flight_member_table,
    get_selectable_member_ids,
    has_selected_assigned_cadets,
    get_member_selection_table,
    get_selected_cadet_ids,
    unassign_selected_cadets,
)


@patch("utils.db_schema_crud.get_collection")
def test_unassign_cadet_from_flight(mock_get_collection):
    # Create mock collection
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    cadet_id = ObjectId()

    # Call function
    unassign_cadet_from_flight(cadet_id)

    # Check if update_one was called correctly
    mock_collection.update_one.assert_called_once_with(
        {"_id": cadet_id},
        {"$unset": {"flight_id": ""}},
    )


@patch("utils.db_schema_crud.get_collection")
def test_unassign_cadet_without_flight(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    cadet_id = ObjectId()

    unassign_cadet_from_flight(cadet_id)

    mock_collection.update_one.assert_called_once()


@patch("utils.db_schema_crud.get_collection")
def test_unassign_invalid_id(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    with pytest.raises(Exception):
        unassign_cadet_from_flight("invalid_id")


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_flight_raises_if_already_in_different_flight(
    mock_get_collection,
):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    cadet_id = ObjectId()
    existing_flight_id = ObjectId()
    new_flight_id = ObjectId()

    cadets_collection.find_one.return_value = {
        "_id": cadet_id,
        "flight_id": existing_flight_id,
    }
    flights_collection.find_one.side_effect = [
        {"_id": existing_flight_id, "name": "Alpha Flight"},
    ]

    with pytest.raises(
        ValueError,
        match=r"already assigned to Alpha Flight\. Unassign them first\.",
    ):
        assign_cadet_to_flight(cadet_id, new_flight_id)

    cadets_collection.update_one.assert_not_called()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_flight_succeeds_when_unassigned(mock_get_collection):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    cadet_id = ObjectId()
    flight_id = ObjectId()

    cadets_collection.find_one.return_value = {"_id": cadet_id}
    flights_collection.find_one.return_value = None

    assign_cadet_to_flight(cadet_id, flight_id)

    cadets_collection.update_one.assert_called_once()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_same_flight_is_allowed(mock_get_collection):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    cadet_id = ObjectId()
    flight_id = ObjectId()

    cadets_collection.find_one.return_value = {"_id": cadet_id, "flight_id": flight_id}
    flights_collection.find_one.return_value = None

    assign_cadet_to_flight(cadet_id, flight_id)

    cadets_collection.update_one.assert_called_once()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_flight_raises_if_commanding_different_flight(mock_get_collection):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    cadet_id = ObjectId()
    commanded_flight_id = ObjectId()
    new_flight_id = ObjectId()

    cadets_collection.find_one.return_value = {"_id": cadet_id}
    flights_collection.find_one.return_value = {
        "_id": commanded_flight_id,
        "name": "Bravo Flight",
        "commander_cadet_id": cadet_id,
    }

    with pytest.raises(
        ValueError,
        match=r"already commanding Bravo Flight\. Remove them as commander first\.",
    ):
        assign_cadet_to_flight(cadet_id, new_flight_id)

    cadets_collection.update_one.assert_not_called()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_same_flight_is_allowed_when_commanding_it(mock_get_collection):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    cadet_id = ObjectId()
    flight_id = ObjectId()

    cadets_collection.find_one.return_value = {"_id": cadet_id}

    def find_flight(query):
        if query == {"commander_cadet_id": cadet_id, "_id": {"$ne": flight_id}}:
            return None
        return {"_id": flight_id, "commander_cadet_id": cadet_id}

    flights_collection.find_one.side_effect = find_flight

    assign_cadet_to_flight(cadet_id, flight_id)

    cadets_collection.update_one.assert_called_once()


@patch("utils.db_schema_crud.get_collection")
def test_create_flight_raises_if_commander_already_assigned_to_other_flight(
    mock_get_collection,
):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    commander_cadet_id = ObjectId()

    cadets_collection.find_one.return_value = {
        "_id": commander_cadet_id,
        "flight_id": ObjectId(),
    }
    cadets_existing_flight_id = cadets_collection.find_one.return_value["flight_id"]
    flights_collection.find_one.return_value = {
        "_id": cadets_existing_flight_id,
        "name": "Alpha Flight",
    }

    with pytest.raises(
        ValueError,
        match=r"already assigned to Alpha Flight\. Unassign them first\.",
    ):
        create_flight("Charlie Flight", commander_cadet_id)

    flights_collection.insert_one.assert_not_called()


@patch("utils.db_schema_crud.get_collection")
def test_create_flight_raises_if_commander_already_commands_other_flight(
    mock_get_collection,
):
    cadets_collection = MagicMock()
    flights_collection = MagicMock()
    mock_get_collection.side_effect = lambda name: {
        "cadets": cadets_collection,
        "flights": flights_collection,
    }[name]

    commander_cadet_id = ObjectId()

    cadets_collection.find_one.return_value = {"_id": commander_cadet_id}
    flights_collection.find_one.return_value = {
        "_id": ObjectId(),
        "name": "Bravo Flight",
        "commander_cadet_id": commander_cadet_id,
    }

    with pytest.raises(
        ValueError,
        match=r"already commanding Bravo Flight\. Remove them as commander first\.",
    ):
        create_flight("Charlie Flight", commander_cadet_id)

    flights_collection.insert_one.assert_not_called()


@patch("utils.db_schema_crud.get_collection")
def test_unassign_all_cadets_from_flight(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    flight_id = ObjectId()

    unassign_all_cadets_from_flight(flight_id)

    mock_collection.update_many.assert_called_once_with(
        {"flight_id": ObjectId(flight_id)},
        {"$unset": {"flight_id": ""}},
    )


@patch("utils.db_schema_crud.get_collection")
def test_unassign_all_cadets_from_flight_no_cadets(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    flight_id = ObjectId()

    unassign_all_cadets_from_flight(flight_id)

    mock_collection.update_many.assert_called_once()


@patch("services.cadets.db_assign_cadet_to_flight")
@patch("services.cadets.get_cadet_by_id")
def test_assign_cadet_to_flight_service_raises_if_already_in_same_flight(
    mock_get_cadet_by_id, mock_db_assign_cadet_to_flight
):
    cadet_id = ObjectId()
    flight_id = ObjectId()

    mock_get_cadet_by_id.return_value = {"_id": cadet_id, "flight_id": flight_id}

    with pytest.raises(ValueError, match="already in this flight"):
        assign_cadet_to_flight_service(cadet_id, flight_id)

    mock_db_assign_cadet_to_flight.assert_not_called()


@patch("services.cadets.db_assign_cadet_to_flight")
@patch("services.cadets.get_cadet_by_id")
def test_assign_cadet_to_flight_service_calls_db_for_new_assignment(
    mock_get_cadet_by_id, mock_db_assign_cadet_to_flight
):
    cadet_id = ObjectId()
    current_flight_id = ObjectId()
    new_flight_id = ObjectId()

    mock_get_cadet_by_id.return_value = {"_id": cadet_id, "flight_id": current_flight_id}

    assign_cadet_to_flight_service(cadet_id, new_flight_id)

    mock_db_assign_cadet_to_flight.assert_called_once_with(cadet_id, new_flight_id)


@patch("services.flight_management.get_user_by_id")
@patch("services.flight_management.get_cadet_by_id")
def test_get_flight_commander_details_returns_name_and_rank(
    mock_get_cadet_by_id,
    mock_get_user_by_id,
):
    commander_id = ObjectId()
    user_id = ObjectId()

    mock_get_cadet_by_id.return_value = {"_id": commander_id, "user_id": user_id, "rank": "300"}
    mock_get_user_by_id.return_value = {
        "first_name": "Taylor",
        "last_name": "Smith",
    }

    name, rank = get_flight_commander_details({"commander_cadet_id": commander_id})

    assert name == "Taylor Smith"
    assert rank == "300"


@patch("services.flight_management.get_user_by_id")
@patch("services.flight_management.get_all_cadets")
@patch("services.flight_management.get_all_flights")
@patch("services.flight_management.get_collection")
def test_get_flight_management_cadet_rows_excludes_commanders_and_adds_flight_info(
    mock_get_collection,
    mock_get_all_flights,
    mock_get_all_cadets,
    mock_get_user_by_id,
):
    commander_id = ObjectId()
    assigned_cadet_id = ObjectId()
    unassigned_cadet_id = ObjectId()
    assigned_flight_id = ObjectId()

    flights_collection = MagicMock()
    flights_collection.find.return_value = [{"commander_cadet_id": commander_id}]
    mock_get_collection.return_value = flights_collection
    mock_get_all_flights.return_value = [{"_id": assigned_flight_id, "name": "Bravo Flight"}]
    mock_get_all_cadets.return_value = [
        {"_id": commander_id, "user_id": ObjectId(), "rank": "300"},
        {
            "_id": assigned_cadet_id,
            "user_id": ObjectId(),
            "rank": "200",
            "flight_id": assigned_flight_id,
        },
        {
            "_id": unassigned_cadet_id,
            "user_id": ObjectId(),
            "rank": "100",
        }
    ]
    mock_get_user_by_id.side_effect = [
        {"first_name": "Taylor", "last_name": "Smith", "email": "tsmith@test.local"},
        {"first_name": "Jordan", "last_name": "Lee", "email": "jlee@test.local"},
    ]

    rows = get_flight_management_cadet_rows()

    assert rows == [
        {
            "cadet_id": str(unassigned_cadet_id),
            "name": "Jordan Lee",
            "rank": "100",
            "email": "jlee@test.local",
            "current_flight_id": "",
            "current_flight": "",
            "is_assigned": False,
        },
        {
            "cadet_id": str(assigned_cadet_id),
            "name": "Taylor Smith",
            "rank": "200",
            "email": "tsmith@test.local",
            "current_flight_id": str(assigned_flight_id),
            "current_flight": "Bravo Flight",
            "is_assigned": True,
        },
    ]


def test_get_cadet_rows_by_id_returns_lookup_map():
    rows = [{"cadet_id": "cadet-1", "name": "Taylor Smith"}]

    rows_by_id = get_cadet_rows_by_id(rows)

    assert rows_by_id == {"cadet-1": {"cadet_id": "cadet-1", "name": "Taylor Smith"}}


def test_get_assignment_table_defaults_to_unassigned_and_keeps_selected_assigned_rows():
    cadet_rows = [
        {
            "cadet_id": "cadet-unassigned",
            "name": "Jordan Lee",
            "rank": "100",
            "email": "jlee@test.local",
            "current_flight_id": "",
            "current_flight": "",
            "is_assigned": False,
        },
        {
            "cadet_id": "cadet-assigned",
            "name": "Taylor Smith",
            "rank": "200",
            "email": "tsmith@test.local",
            "current_flight_id": "flight-bravo",
            "current_flight": "Bravo Flight",
            "is_assigned": True,
        },
    ]

    table, cadet_ids = get_assignment_table(
        cadet_rows,
        target_flight_id="flight-alpha",
        selected_cadet_ids=["cadet-assigned"],
    )

    assert cadet_ids == ["cadet-assigned", "cadet-unassigned"]
    assert table.to_dict("records") == [
        {
            "Assign": True,
            "Cadet": "Taylor Smith",
            "Rank": "200",
            "Email": "tsmith@test.local",
            "Current Flight": "Bravo Flight",
        },
        {
            "Assign": False,
            "Cadet": "Jordan Lee",
            "Rank": "100",
            "Email": "jlee@test.local",
            "Current Flight": "Unassigned",
        },
    ]


def test_get_assignment_table_searches_all_candidates_except_current_flight():
    cadet_rows = [
        {
            "cadet_id": "cadet-alpha",
            "name": "Already Here",
            "rank": "100",
            "email": "alpha@test.local",
            "current_flight_id": "flight-alpha",
            "current_flight": "Alpha Flight",
            "is_assigned": True,
        },
        {
            "cadet_id": "cadet-bravo",
            "name": "Taylor Smith",
            "rank": "200",
            "email": "tsmith@test.local",
            "current_flight_id": "flight-bravo",
            "current_flight": "Bravo Flight",
            "is_assigned": True,
        },
    ]

    table, cadet_ids = get_assignment_table(
        cadet_rows,
        target_flight_id="flight-alpha",
        selected_cadet_ids=[],
        search_term="taylor",
    )

    assert cadet_ids == ["cadet-bravo"]
    assert table.to_dict("records") == [
        {
            "Assign": False,
            "Cadet": "Taylor Smith",
            "Rank": "200",
            "Email": "tsmith@test.local",
            "Current Flight": "Bravo Flight",
        }
    ]


def test_get_assignment_table_show_assigned_includes_other_flights_without_search():
    cadet_rows = [
        {
            "cadet_id": "cadet-unassigned",
            "name": "Jordan Lee",
            "rank": "100",
            "email": "jlee@test.local",
            "current_flight_id": "",
            "current_flight": "",
            "is_assigned": False,
        },
        {
            "cadet_id": "cadet-assigned",
            "name": "Taylor Smith",
            "rank": "200",
            "email": "tsmith@test.local",
            "current_flight_id": "flight-bravo",
            "current_flight": "Bravo Flight",
            "is_assigned": True,
        },
    ]

    table, cadet_ids = get_assignment_table(
        cadet_rows,
        target_flight_id="flight-alpha",
        selected_cadet_ids=[],
        show_assigned=True,
    )

    assert cadet_ids == ["cadet-unassigned", "cadet-assigned"]
    assert table.to_dict("records") == [
        {
            "Assign": False,
            "Cadet": "Jordan Lee",
            "Rank": "100",
            "Email": "jlee@test.local",
            "Current Flight": "Unassigned",
        },
        {
            "Assign": False,
            "Cadet": "Taylor Smith",
            "Rank": "200",
            "Email": "tsmith@test.local",
            "Current Flight": "Bravo Flight",
        },
    ]


def test_has_selected_assigned_cadets_detects_reassignment():
    rows_by_id = {
        "cadet-1": {"is_assigned": False},
        "cadet-2": {"is_assigned": True},
    }

    assert has_selected_assigned_cadets(["cadet-1"], rows_by_id) is False
    assert has_selected_assigned_cadets(["cadet-2"], rows_by_id) is True


def test_get_flight_member_table_builds_member_rows_without_commander():
    table, cadet_ids = get_flight_member_table(
        [
            {
                "cadet_id": "cadet-1",
                "name": "Jordan Lee",
                "rank": "100",
                "email": "jlee@test.local",
                "current_flight_id": "flight-alpha",
                "current_flight": "Alpha Flight",
                "is_assigned": True,
            },
            {
                "cadet_id": "cadet-2",
                "name": "Taylor Smith",
                "rank": "200",
                "email": "tsmith@test.local",
                "current_flight_id": "flight-bravo",
                "current_flight": "Bravo Flight",
                "is_assigned": True,
            },
        ],
        {
            "_id": "flight-alpha",
            "name": "Alpha Flight",
            "commander_cadet_id": "000000000000000000000001",
        },
    )

    assert cadet_ids == ["cadet-1"]
    assert table.to_dict("records") == [
        {
            "Cadet": "Jordan Lee",
            "Role": "Cadet",
            "Rank": "100",
            "Email": "jlee@test.local",
            "Current Flight": "Alpha Flight",
        },
    ]


@patch("services.flight_management.get_user_by_id")
@patch("services.flight_management.get_cadet_by_id")
def test_get_commander_member_table_builds_commander_row(
    mock_get_cadet_by_id,
    mock_get_user_by_id,
):
    mock_get_cadet_by_id.return_value = {
        "_id": ObjectId("000000000000000000000001"),
        "user_id": ObjectId(),
        "rank": "300",
    }
    mock_get_user_by_id.return_value = {
        "first_name": "Commander",
        "last_name": "One",
        "email": "commander@test.local",
    }

    table = get_commander_member_table(
        {
            "_id": "flight-alpha",
            "name": "Alpha Flight",
            "commander_cadet_id": "000000000000000000000001",
        }
    )

    assert table.to_dict("records") == [
        {
            "Cadet": "Commander One",
            "Role": "Commander",
            "Rank": "300",
            "Email": "commander@test.local",
            "Current Flight": "Alpha Flight",
        }
    ]


def test_get_member_selection_table_marks_selected_rows():
    member_table = MagicMock()
    member_table.copy.return_value = member_table
    member_table.empty = False

    get_member_selection_table(member_table, ["cadet-2"], ["cadet-1", "cadet-2"])

    member_table.insert.assert_called_once_with(0, "Unassign", [False, True])


def test_get_selectable_member_ids_returns_all_member_ids():
    assert get_selectable_member_ids(["cadet-1", "cadet-2"]) == [
        "cadet-1",
        "cadet-2",
    ]


def test_get_selected_cadet_ids_returns_checked_rows_only():
    edited_table = MagicMock()
    edited_table.iterrows.return_value = iter(
        [
            (0, {"Assign": None}),
            (1, {"Assign": True}),
            (2, {"Assign": True}),
        ]
    )

    selected_ids = get_selected_cadet_ids(
        edited_table,
        [None, "cadet-2", "cadet-3"],
        "Assign",
    )

    assert selected_ids == ["cadet-2", "cadet-3"]


def test_get_selected_cadet_ids_handles_pandas_bool_values():
    edited_table = pd.DataFrame({"Assign": [True, True, False]})

    selected_ids = get_selected_cadet_ids(
        edited_table,
        [None, "cadet-2", "cadet-3"],
        "Assign",
    )

    assert selected_ids == ["cadet-2"]


@patch("services.flight_management.assign_cadet_to_flight")
@patch("services.flight_management.unassign_cadet_from_flight")
def test_assign_selected_cadets_to_flight_returns_partial_warning(
    mock_unassign_cadet_from_flight,
    mock_assign_cadet_to_flight,
):
    mock_assign_cadet_to_flight.side_effect = [None, ValueError("Database unavailable")]

    level, message = assign_selected_cadets_to_flight(
        ["cadet-1", "cadet-2"],
        "flight-1",
        {
            "cadet-1": {"name": "Jordan Lee", "current_flight_id": "flight-bravo"},
            "cadet-2": {"name": "Taylor Smith", "current_flight_id": ""},
        },
    )

    mock_unassign_cadet_from_flight.assert_called_once_with("cadet-1")
    assert level == "warning"
    assert "Assigned 1 cadet(s)." in message
    assert "Reassigned 1 from a previous flight." in message
    assert "Taylor Smith: Database unavailable" in message


def test_assign_selected_cadets_to_flight_warns_when_nothing_selected():
    level, message = assign_selected_cadets_to_flight([], "flight-1", {})

    assert level == "warning"
    assert message == "Select at least one cadet."


@patch("services.flight_management.unassign_cadet_from_flight")
def test_unassign_selected_cadets_returns_success(mock_unassign_cadet_from_flight):
    level, message = unassign_selected_cadets(["cadet-1"], {"cadet-1": {"name": "Jordan Lee"}})

    mock_unassign_cadet_from_flight.assert_called_once_with("cadet-1")
    assert level == "success"
    assert message == "Unassigned 1 cadet(s)."
