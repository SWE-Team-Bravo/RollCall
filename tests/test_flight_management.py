import sys
import os
from unittest.mock import patch, MagicMock
from bson import ObjectId

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db_schema_crud import unassign_cadet_from_flight


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


import pytest


@patch("utils.db_schema_crud.get_collection")
def test_unassign_invalid_id(mock_get_collection):
    mock_collection = MagicMock()
    mock_get_collection.return_value = mock_collection

    with pytest.raises(Exception):
        unassign_cadet_from_flight("invalid_id")
