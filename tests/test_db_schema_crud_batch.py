from bson import ObjectId
from unittest.mock import patch, MagicMock

from utils.db_schema_crud import (
    delete_cadet,
    delete_user,
    get_cadet_absence_stats,
    get_users_by_emails,
    get_users_by_names,
    get_cadets_by_user_ids_map,
)


def _make_user(uid, first, last, email):
    return {
        "_id": ObjectId(uid),
        "first_name": first,
        "last_name": last,
        "email": email,
    }


def _make_cadet(cid, uid, rank="100"):
    return {"_id": ObjectId(cid), "user_id": ObjectId(uid), "rank": rank}


class TestGetUsersByEmails:
    @patch("utils.db_schema_crud.get_collection")
    def test_returns_matching_users_keyed_by_email(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        users = [
            _make_user("a" * 24, "Alice", "Smith", "alice@example.com"),
            _make_user("b" * 24, "Bob", "Jones", "bob@example.com"),
        ]
        mock_col.find.return_value = users

        result = get_users_by_emails(["alice@example.com", "bob@example.com"])

        assert "alice@example.com" in result
        assert "bob@example.com" in result
        assert result["alice@example.com"]["first_name"] == "Alice"
        assert result["bob@example.com"]["first_name"] == "Bob"

    @patch("utils.db_schema_crud.get_collection")
    def test_empty_list_returns_empty(self, mock_get_col):
        result = get_users_by_emails([])
        assert result == {}
        mock_get_col.assert_not_called()

    @patch("utils.db_schema_crud.get_collection")
    def test_none_collection_returns_empty(self, mock_get_col):
        mock_get_col.return_value = None

        result = get_users_by_emails(["a@b.com"])

        assert result == {}

    @patch("utils.db_schema_crud.get_collection")
    def test_builds_or_regex_query(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.find.return_value = []

        get_users_by_emails(["alice@example.com", "bob@example.com"])

        query = mock_col.find.call_args[0][0]
        assert "$or" in query
        assert len(query["$or"]) == 2

    @patch("utils.db_schema_crud.get_collection")
    def test_no_matching_users_returns_empty(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.find.return_value = []

        result = get_users_by_emails(["nobody@example.com"])

        assert result == {}


class TestGetUsersByNames:
    @patch("utils.db_schema_crud.get_collection")
    def test_returns_matching_users_keyed_by_name_tuple(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        users = [
            _make_user("a" * 24, "Alice", "Smith", "alice@example.com"),
        ]
        mock_col.find.return_value = users

        result = get_users_by_names([("Alice", "Smith")])

        assert ("alice", "smith") in result
        assert result[("alice", "smith")]["first_name"] == "Alice"

    @patch("utils.db_schema_crud.get_collection")
    def test_empty_list_returns_empty(self, mock_get_col):
        result = get_users_by_names([])
        assert result == {}
        mock_get_col.assert_not_called()

    @patch("utils.db_schema_crud.get_collection")
    def test_none_collection_returns_empty(self, mock_get_col):
        mock_get_col.return_value = None

        result = get_users_by_names([("Alice", "Smith")])

        assert result == {}

    @patch("utils.db_schema_crud.get_collection")
    def test_builds_or_regex_query(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.find.return_value = []

        get_users_by_names([("Alice", "Smith"), ("Bob", "Jones")])

        query = mock_col.find.call_args[0][0]
        assert "$or" in query
        assert len(query["$or"]) == 2

    @patch("utils.db_schema_crud.get_collection")
    def test_no_matching_users_returns_empty(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.find.return_value = []

        result = get_users_by_names([("Nobody", "Here")])

        assert result == {}


class TestGetCadetsByUserIdsMap:
    @patch("utils.db_schema_crud.get_collection")
    def test_returns_cadets_keyed_by_user_id_string(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        uid1 = ObjectId()
        uid2 = ObjectId()
        cadets = [
            _make_cadet("c" * 24, str(uid1), "100"),
            _make_cadet("d" * 24, str(uid2), "200"),
        ]
        mock_col.find.return_value = cadets

        result = get_cadets_by_user_ids_map([str(uid1), str(uid2)])

        assert str(uid1) in result
        assert str(uid2) in result
        assert result[str(uid1)]["rank"] == "100"
        assert result[str(uid2)]["rank"] == "200"

    @patch("utils.db_schema_crud.get_collection")
    def test_empty_list_returns_empty(self, mock_get_col):
        result = get_cadets_by_user_ids_map([])
        assert result == {}
        mock_get_col.assert_not_called()

    @patch("utils.db_schema_crud.get_collection")
    def test_none_collection_returns_empty(self, mock_get_col):
        mock_get_col.return_value = None

        result = get_cadets_by_user_ids_map([str(ObjectId())])

        assert result == {}

    @patch("utils.db_schema_crud.get_collection")
    def test_no_matching_cadets_returns_empty(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.find.return_value = []

        result = get_cadets_by_user_ids_map([str(ObjectId())])

        assert result == {}

    @patch("utils.db_schema_crud.get_collection")
    def test_builds_in_query(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        uid1 = ObjectId()
        uid2 = ObjectId()
        mock_col.find.return_value = []

        get_cadets_by_user_ids_map([str(uid1), str(uid2)])

        query = mock_col.find.call_args[0][0]
        assert "user_id" in query
        assert "$in" in query["user_id"]
        assert len(query["user_id"]["$in"]) == 2


class TestGetCadetAbsenceStats:
    @patch("utils.db_schema_crud.get_collection")
    def test_pipeline_excludes_approved_waivers_from_absence_totals(self, mock_get_col):
        mock_col = MagicMock()
        mock_get_col.return_value = mock_col
        mock_col.aggregate.return_value = []

        get_cadet_absence_stats()

        pipeline = mock_col.aggregate.call_args[0][0]
        group_index = next(
            index for index, stage in enumerate(pipeline) if "$group" in stage
        )
        pre_group_stages = pipeline[:group_index]

        assert any(
            {"waiver.status": {"$ne": "approved"}}
            in stage.get("$match", {}).get("$or", [])
            for stage in pre_group_stages
        )


class TestDeleteUserCascade:
    @patch("utils.db_schema_crud.get_collection")
    def test_delete_user_deletes_linked_cadet_and_clears_flight_refs(
        self, mock_get_col
    ):
        user_id = ObjectId()
        cadet_id = ObjectId()
        users_col = MagicMock()
        cadets_col = MagicMock()
        flights_col = MagicMock()
        cadets_col.find_one.return_value = {"_id": cadet_id, "user_id": user_id}

        collections = {
            "users": users_col,
            "cadets": cadets_col,
            "flights": flights_col,
        }
        mock_get_col.side_effect = lambda name: collections[name]

        result = delete_user(user_id)

        assert result == users_col.delete_one.return_value
        cadets_col.update_one.assert_called_once_with(
            {"_id": cadet_id},
            {"$unset": {"flight_id": ""}},
        )
        flights_col.update_many.assert_called_once_with(
            {"commander_cadet_id": cadet_id},
            {"$unset": {"commander_cadet_id": ""}},
        )
        cadets_col.delete_one.assert_called_once_with({"_id": cadet_id})
        users_col.delete_one.assert_called_once_with({"_id": user_id})


class TestDeleteCadetCascade:
    @patch("utils.db_schema_crud.get_collection")
    def test_delete_cadet_clears_flight_references_before_delete(self, mock_get_col):
        cadet_id = ObjectId()
        cadets_col = MagicMock()
        flights_col = MagicMock()

        collections = {
            "cadets": cadets_col,
            "flights": flights_col,
        }
        mock_get_col.side_effect = lambda name: collections[name]

        result = delete_cadet(cadet_id)

        assert result == cadets_col.delete_one.return_value
        cadets_col.update_one.assert_called_once_with(
            {"_id": cadet_id},
            {"$unset": {"flight_id": ""}},
        )
        flights_col.update_many.assert_called_once_with(
            {"commander_cadet_id": cadet_id},
            {"$unset": {"commander_cadet_id": ""}},
        )
        cadets_col.delete_one.assert_called_once_with({"_id": cadet_id})
