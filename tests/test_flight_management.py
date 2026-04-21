from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest

from utils.db_schema_crud import (
    unassign_cadet_from_flight,
    assign_cadet_to_flight,
    unassign_all_cadets_from_flight,
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
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    cadet_id = ObjectId()
    existing_flight_id = ObjectId()
    new_flight_id = ObjectId()

    mock_collection.find_one.return_value = {
        "_id": cadet_id,
        "flight_id": existing_flight_id,
    }

    with pytest.raises(ValueError, match="already assigned"):
        assign_cadet_to_flight(cadet_id, new_flight_id)

    mock_collection.update_one.assert_not_called()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_flight_succeeds_when_unassigned(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    cadet_id = ObjectId()
    flight_id = ObjectId()

    mock_collection.find_one.return_value = {"_id": cadet_id}

    assign_cadet_to_flight(cadet_id, flight_id)

    mock_collection.update_one.assert_called_once()


@patch("utils.db_schema_crud.get_collection")
def test_assign_cadet_to_same_flight_is_allowed(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    cadet_id = ObjectId()
    flight_id = ObjectId()

    mock_collection.find_one.return_value = {"_id": cadet_id, "flight_id": flight_id}

    assign_cadet_to_flight(cadet_id, flight_id)

    mock_collection.update_one.assert_called_once()


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
