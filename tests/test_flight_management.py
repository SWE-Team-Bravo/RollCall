from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest

from utils.db_schema_crud import (
    create_flight,
    unassign_cadet_from_flight,
    assign_cadet_to_flight,
    unassign_all_cadets_from_flight,
)
from services.cadets import assign_cadet_to_flight as assign_cadet_to_flight_service


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
