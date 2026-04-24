from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

import services.audit_log_viewer as viewer


class _FakeCollection:
    def __init__(self, docs: list[dict[str, Any]]):
        self.docs = [dict(d) for d in docs]

    def count_documents(self, query: dict):
        return len(list(self.find(query)))

    def find(self, query: dict | None = None, projection: dict | None = None):
        if query is None:
            matched = [dict(d) for d in self.docs]
        else:
            matched = [dict(d) for d in self.docs if self._matches(d, query)]
        return _FakeCursor(matched)

    def distinct(self, field: str):
        values: set[Any] = set()
        for doc in self.docs:
            if field in doc:
                values.add(doc[field])
        return sorted(values)

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            if key == "$and":
                if not all(self._matches(doc, sub) for sub in expected):
                    return False
                continue
            if key == "$or":
                if not any(self._matches(doc, sub) for sub in expected):
                    return False
                continue

            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                    return False
                if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$regex" in expected:
                    import re

                    pattern = re.compile(
                        expected["$regex"],
                        re.I if expected.get("$options") == "i" else 0,
                    )
                    if actual is None or not pattern.search(str(actual)):
                        return False
                continue
            if actual != expected:
                return False
        return True


class _FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = docs
        self._sort_key: str | None = None
        self._sort_dir: int = 1

    def sort(self, key: str, direction: int):
        self._sort_key = key
        self._sort_dir = direction
        return self

    def skip(self, n: int):
        return _FakeCursor(self._docs[n:])

    def limit(self, n: int):
        return _FakeCursor(self._docs[:n])

    def __iter__(self):
        docs = list(self._docs)
        if self._sort_key:
            reverse = self._sort_dir == -1
            docs.sort(key=lambda d: d.get(self._sort_key, "") or "", reverse=reverse)
        return iter(docs)


def _patch_collections(
    monkeypatch,
    audit_docs: list[dict[str, Any]],
    *,
    users: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    cadets: list[dict[str, Any]] | None = None,
) -> dict[str, _FakeCollection]:
    collections = {
        "audit_log": _FakeCollection(audit_docs),
        "users": _FakeCollection(users or []),
        "events": _FakeCollection(events or []),
        "cadets": _FakeCollection(cadets or []),
    }

    monkeypatch.setattr(viewer, "get_collection", lambda name: collections.get(name))
    monkeypatch.setattr(
        viewer,
        "get_users_by_ids",
        lambda ids: [
            user for user in collections["users"].docs if user.get("_id") in ids
        ],
    )
    monkeypatch.setattr(
        viewer,
        "get_cadets_by_ids",
        lambda ids: [
            cadet for cadet in collections["cadets"].docs if cadet.get("_id") in ids
        ],
    )
    return collections


def _make_audit_doc(
    *,
    source: str = "user_management",
    action: str = "update",
    actor_user_id: Any = None,
    actor_email: str = "",
    target_collection: str = "users",
    target_id: Any = None,
    target_label: str = "",
    created_at: datetime | None = None,
    changes: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "_id": ObjectId(),
        "source": source,
        "action": action,
        "actor_user_id": actor_user_id or ObjectId(),
        "actor_email": actor_email,
        "target_collection": target_collection,
        "target_id": target_id or ObjectId(),
        "target_label": target_label,
        "created_at": created_at
        or datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        "actor_roles": ["admin"],
        "before": None,
        "after": None,
        "changes": changes or {},
    }
    if metadata:
        doc["metadata"] = metadata
    doc.update(extra)
    return doc


def _person_doc(
    person_id: ObjectId,
    first_name: str,
    last_name: str,
    *,
    email: str = "",
    name: str = "",
) -> dict[str, Any]:
    doc = {"_id": person_id, "first_name": first_name, "last_name": last_name}
    if email:
        doc["email"] = email
    if name:
        doc["name"] = name
    return doc


def _attendance_doc(
    event_id: ObjectId,
    cadet_id: ObjectId,
    *,
    outcome: str = "applied",
    user_id: ObjectId | None = None,
    created_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = {
        "_id": ObjectId(),
        "source": "attendance_modification",
        "outcome": outcome,
        "event_id": event_id,
        "cadet_id": cadet_id,
        "created_at": created_at
        or datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        "metadata": metadata or {"old_status": None, "new_status": "absent"},
    }
    if user_id is not None:
        doc["user_id"] = user_id
    return doc


def test_query_returns_paginated_results(monkeypatch):
    docs = [
        _make_audit_doc(
            action="create",
            created_at=datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        ),
        _make_audit_doc(
            action="update",
            created_at=datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc),
        ),
        _make_audit_doc(
            action="delete",
            created_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(page=1, page_size=2)

    assert len(result["items"]) == 2
    assert result["total_count"] == 3
    assert result["total_pages"] == 2
    assert result["items"][0]["action"] == "create"


def test_query_filters_by_activity(monkeypatch):
    docs = [
        _make_audit_doc(source="user_management"),
        _make_audit_doc(source="event_management"),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(activities=["Users created or updated"])

    assert len(result["items"]) == 1
    assert result["items"][0]["source"] == "user_management"


def test_query_filters_by_multiple_activities(monkeypatch):
    docs = [
        _make_audit_doc(source="event_management", action="create"),
        _make_audit_doc(
            source="waiver_review",
            action="approve",
            target_collection="waivers",
        ),
        _make_audit_doc(source="user_management", action="reset_password"),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(
        activities=["Events created or updated", "Waivers approved or denied"]
    )

    assert len(result["items"]) == 2
    assert {row["source"] for row in result["items"]} == {
        "event_management",
        "waiver_review",
    }


def test_empty_activity_filter_returns_everything(monkeypatch):
    docs = [
        _make_audit_doc(source="user_management"),
        _make_audit_doc(source="event_management"),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(activities=[])

    assert len(result["items"]) == 2


def test_query_filters_by_date_range(monkeypatch):
    docs = [
        _make_audit_doc(
            created_at=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        ),
        _make_audit_doc(
            created_at=datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)
        ),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(
        start_date=datetime(2026, 4, 21, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )

    assert len(result["items"]) == 1
    assert result["items"][0]["timestamp"].day == 25


def test_query_filters_by_actor_search_email(monkeypatch):
    docs = [
        _make_audit_doc(actor_email="admin@example.com"),
        _make_audit_doc(actor_email="other@example.com"),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(actor_search="admin")

    assert len(result["items"]) == 1
    assert result["items"][0]["actor_email"] == "admin@example.com"


def test_query_filters_by_actor_search_name_and_id(monkeypatch):
    actor_id = ObjectId()
    other_id = ObjectId()
    docs = [
        _make_audit_doc(actor_user_id=actor_id),
        _make_audit_doc(actor_user_id=other_id),
    ]
    _patch_collections(
        monkeypatch,
        docs,
        users=[
            _person_doc(
                actor_id,
                "Admin",
                "User",
                name="Admin User",
                email="admin@example.com",
            ),
            _person_doc(
                other_id,
                "Other",
                "User",
                name="Other User",
                email="other@example.com",
            ),
        ],
    )

    by_name = viewer.query_audit_log(actor_search="Admin User")
    by_id = viewer.query_audit_log(actor_search=str(actor_id))

    assert len(by_name["items"]) == 1
    assert by_name["items"][0]["actor_id"] == actor_id
    assert len(by_id["items"]) == 1
    assert by_id["items"][0]["actor_id"] == actor_id


def test_hydration_maps_user_ids_to_names(monkeypatch):
    actor_id = ObjectId()
    target_id = ObjectId()

    docs = [
        _make_audit_doc(
            actor_user_id=actor_id,
            actor_email="admin@example.com",
            target_collection="users",
            target_id=target_id,
            target_label="fallback",
        ),
    ]
    _patch_collections(
        monkeypatch,
        docs,
        users=[
            _person_doc(actor_id, "John", "Admin", email="admin@example.com"),
            _person_doc(target_id, "Jane", "User", email="jane@example.com"),
        ],
    )

    result = viewer.query_audit_log()

    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["actor_name"] == "John Admin"
    assert row["target_label"] == "Jane User"


def test_legacy_attendance_entry_normalized(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    actor_id = ObjectId()

    docs = [
        _attendance_doc(
            event_id,
            cadet_id,
            user_id=actor_id,
            metadata={"old_status": "absent", "new_status": "present"},
        )
    ]
    _patch_collections(
        monkeypatch,
        docs,
        users=[_person_doc(actor_id, "Admin", "User", email="admin@example.com")],
        events=[{"_id": event_id, "event_name": "Week 3 PT"}],
        cadets=[_person_doc(cadet_id, "Tyler", "Brooks")],
    )

    result = viewer.query_audit_log()

    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["source"] == "attendance_modification"
    assert row["action"] == "applied"
    assert row["activity_label"] == "Saved Attendance"
    assert row["target_label"] == "Week 3 PT"
    assert row["cadet_label"] == "Tyler Brooks"
    assert row["summary"] == "From Absent to Present"


def test_attendance_undo_summary_includes_transition(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()

    docs = [
        _attendance_doc(
            event_id,
            cadet_id,
            outcome="undo",
            metadata={"old_status": "present", "new_status": "absent"},
        )
    ]
    _patch_collections(
        monkeypatch,
        docs,
        events=[{"_id": event_id, "event_name": "Week 3 PT"}],
        cadets=[_person_doc(cadet_id, "Kevin", "Nguyen")],
    )

    result = viewer.query_audit_log()

    row = result["items"][0]
    assert row["target_label"] == "Week 3 PT"
    assert row["cadet_label"] == "Kevin Nguyen"
    assert row["activity_label"] == "Undid Attendance Change"
    assert row["summary"] == "Undo from Present back to Absent"


def test_attendance_detail_rows_are_standardized(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()

    docs = [
        _attendance_doc(
            event_id,
            cadet_id,
            metadata={
                "old_status": None,
                "new_status": "absent",
                "batch_id": "internal-batch",
            },
        )
    ]
    _patch_collections(
        monkeypatch,
        docs,
        events=[{"_id": event_id, "event_name": "Week 5 PT"}],
        cadets=[_person_doc(cadet_id, "Ashley", "Foster")],
    )

    row = viewer.query_audit_log()["items"][0]
    overview = viewer.build_audit_overview_row(row)
    details = viewer.build_audit_detail_rows(row)
    details_by_name = {detail["Detail"]: detail for detail in details}

    assert overview["Target"] == "Week 5 PT"
    assert overview["Cadet"] == "Ashley Foster"
    assert overview["Summary"] == "From No Record to Absent"
    assert "Actor Email" not in overview
    assert details_by_name["Attendance Status"]["Before"] == "No Record"
    assert details_by_name["Attendance Status"]["After"] == "Absent"
    assert "Target" not in details_by_name
    assert "Cadet" not in details_by_name
    assert "Summary" not in details_by_name
    assert "Batch Id" not in details_by_name


def test_overview_row_includes_email_only_when_present():
    row = {
        "timestamp": datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        "actor_name": "Admin User",
        "actor_email": "admin@example.com",
        "source_label": "Event Config",
        "action_label": "Updated",
        "activity_label": "Updated Event Schedule",
        "target_label": "Event Schedule Configuration",
        "cadet_label": "",
        "summary": "Updated Event Schedule",
    }

    overview = viewer.build_audit_overview_row(row)

    assert overview == {
        "Timestamp": "2026-04-24 12:00 UTC",
        "Actor": "Admin User",
        "Actor Email": "admin@example.com",
        "Activity": "Updated Event Schedule",
        "Target": "Event Schedule Configuration",
        "Summary": "Updated Event Schedule",
    }


def test_detail_rows_flatten_changes_and_user_metadata():
    row = {
        "timestamp": datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        "actor_name": "System",
        "actor_email": "",
        "source": "waiver_review",
        "source_label": "Waiver Review",
        "action_label": "Denied",
        "target_label": "PT",
        "cadet_label": "",
        "summary": "Denied — PT",
        "raw_doc": {
            "changes": {"status": {"from": None, "to": "denied"}},
            "metadata": {"comments": "Missing documentation", "waiver_id": "abc123"},
        },
    }

    details = viewer.build_audit_detail_rows(row)
    details_by_name = {detail["Detail"]: detail for detail in details}

    assert details_by_name["Status"]["Before"] == ""
    assert details_by_name["Status"]["After"] == "denied"
    assert details_by_name["Comments"]["Value"] == "Missing documentation"
    assert "Waiver Id" not in details_by_name
    assert "Actor Email" not in details_by_name


def test_checkin_entry_normalized(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()

    docs = [
        {
            "_id": ObjectId(),
            "source": "checkin",
            "outcome": "success",
            "event_id": event_id,
            "cadet_id": cadet_id,
            "created_at": datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        },
    ]
    _patch_collections(
        monkeypatch,
        docs,
        events=[{"_id": event_id, "event_name": "Week 4 LLAB"}],
    )

    result = viewer.query_audit_log()

    assert len(result["items"]) == 1
    row = result["items"][0]
    assert row["source"] == "checkin"
    assert row["action"] == "success"
    assert "Week 4 LLAB" in row["target_label"]


def test_generic_entry_shows_changes(monkeypatch):
    docs = [
        _make_audit_doc(
            action="disable",
            target_collection="users",
            changes={"disabled": {"from": False, "to": True}},
        ),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log()

    assert result["items"][0]["has_details"] is True


def test_redacted_values_not_exposed(monkeypatch):
    docs = [
        _make_audit_doc(
            action="reset_password",
            metadata={"temp_password": "[REDACTED]"},
        ),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log()

    raw = result["items"][0]["raw_doc"]
    assert raw.get("metadata", {}).get("temp_password") == "[REDACTED]"


def test_target_search_matches_label_and_id(monkeypatch):
    target_id = ObjectId()
    docs = [
        _make_audit_doc(target_label="Week 3 PT", target_id=target_id),
        _make_audit_doc(target_label="Week 4 LLAB", target_id=ObjectId()),
    ]
    _patch_collections(monkeypatch, docs)

    result = viewer.query_audit_log(target_search="Week 3")

    assert len(result["items"]) == 1
    assert "Week 3" in result["items"][0]["target_label"]


def test_target_search_matches_attendance_cadet(monkeypatch):
    event_id = ObjectId()
    cadet_id = ObjectId()
    other_cadet_id = ObjectId()
    docs = [
        _attendance_doc(event_id, cadet_id),
        _attendance_doc(
            event_id,
            other_cadet_id,
            created_at=datetime(2026, 4, 24, 12, 1, 0, tzinfo=timezone.utc),
        ),
    ]
    _patch_collections(
        monkeypatch,
        docs,
        events=[{"_id": event_id, "event_name": "Week 3 PT"}],
        cadets=[
            _person_doc(cadet_id, "Ashley", "Foster"),
            _person_doc(other_cadet_id, "Brian", "Lopez"),
        ],
    )

    result = viewer.query_audit_log(target_search="Ashley")

    assert len(result["items"]) == 1
    assert result["items"][0]["cadet_label"] == "Ashley Foster"


def test_target_search_matches_attendance_event_name(monkeypatch):
    event_id = ObjectId()
    other_event_id = ObjectId()
    cadet_id = ObjectId()
    docs = [
        _attendance_doc(event_id, cadet_id),
        _attendance_doc(
            other_event_id,
            cadet_id,
            created_at=datetime(2026, 4, 24, 12, 1, 0, tzinfo=timezone.utc),
        ),
    ]
    _patch_collections(
        monkeypatch,
        docs,
        events=[
            {"_id": event_id, "event_name": "Week 3 PT"},
            {"_id": other_event_id, "event_name": "Week 4 LLAB"},
        ],
        cadets=[_person_doc(cadet_id, "Ashley", "Foster")],
    )

    result = viewer.query_audit_log(target_search="Week 3")

    assert len(result["items"]) == 1
    assert result["items"][0]["target_label"] == "Week 3 PT"


def test_empty_collection_returns_empty(monkeypatch):
    _patch_collections(monkeypatch, [])

    result = viewer.query_audit_log()

    assert result["items"] == []
    assert result["total_count"] == 0


def test_export_returns_dataframe(monkeypatch):
    docs = [
        _make_audit_doc(action="create"),
        _make_audit_doc(action="update"),
    ]
    _patch_collections(monkeypatch, docs)

    df = viewer.export_audit_log_to_df()

    assert df is not None
    assert len(df) == 2
    assert "Timestamp" in df.columns
    assert "Actor" in df.columns
    assert "Activity" in df.columns
    assert "Cadet" in df.columns
    assert "Action" not in df.columns
    assert "Source" not in df.columns


def test_activity_options_are_human_readable():
    options = viewer.get_audit_activity_options()

    assert "Attendance changes" in options
    assert "Waivers approved or denied" in options
    assert all("_" not in option for option in options)
