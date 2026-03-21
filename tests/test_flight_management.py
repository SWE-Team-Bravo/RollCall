import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db_schema_crud import unassign_cadet_from_flight
from utils.db import get_collection
from bson import ObjectId


def test_unassign_cadet_from_flight():
    cadets = get_collection("cadets")

    test_cadet = cadets.insert_one({
        "user_id": ObjectId(),
        "rank": "100",
        "flight_id": ObjectId()
    })

    cadet_id = test_cadet.inserted_id

    unassign_cadet_from_flight(cadet_id)

    updated = cadets.find_one({"_id": cadet_id})

    assert "flight_id" not in updated


def test_unassign_cadet_without_flight():
    cadets = get_collection("cadets")

    test_cadet = cadets.insert_one({
        "user_id": ObjectId(),
        "rank": "200"
    })

    cadet_id = test_cadet.inserted_id

    unassign_cadet_from_flight(cadet_id)

    updated = cadets.find_one({"_id": cadet_id})

    assert "flight_id" not in updated



def test_unassign_invalid_id():
    with pytest.raises(Exception):
        unassign_cadet_from_flight("invalid_id")


