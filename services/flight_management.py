import pandas as pd

from services.cadets import assign_cadet_to_flight, get_all_cadets
from utils.db import get_collection
from utils.db_schema_crud import (
    get_all_flights,
    get_cadet_by_id,
    get_user_by_id,
    unassign_cadet_from_flight,
)
from utils.names import format_full_name


def get_flight_commander_details(flight: dict) -> tuple[str, str]:
    commander = get_cadet_by_id(flight["commander_cadet_id"])
    if commander is None:
        return "-", ""

    user = get_user_by_id(commander["user_id"])
    if user is None:
        return "-", commander.get("rank", "")

    return format_full_name(user), commander.get("rank", "")


def get_flight_management_cadet_rows() -> list[dict[str, str | bool]]:
    commander_cadet_ids = _get_commander_cadet_ids()
    flight_name_by_id = {
        str(flight["_id"]): flight.get("name", "Unnamed flight")
        for flight in get_all_flights()
        if flight.get("_id")
    }
    rows = []

    for cadet in get_all_cadets():
        cadet_id = str(cadet["_id"])
        if cadet_id in commander_cadet_ids:
            continue

        user = get_user_by_id(cadet["user_id"])
        if user is None:
            continue

        current_flight_id = str(cadet["flight_id"]) if cadet.get("flight_id") else ""
        rows.append(
            {
                "cadet_id": cadet_id,
                "name": format_full_name(user),
                "rank": cadet.get("rank", ""),
                "email": user.get("email", ""),
                "current_flight_id": current_flight_id,
                "current_flight": flight_name_by_id.get(current_flight_id, "")
                if current_flight_id
                else "",
                "is_assigned": bool(current_flight_id),
            }
        )

    return sorted(rows, key=lambda row: (row["name"], row["rank"], row["email"]))


def get_cadet_rows_by_id(
    cadet_rows: list[dict[str, str | bool]],
) -> dict[str, dict[str, str | bool]]:
    return {str(row["cadet_id"]): row for row in cadet_rows}


def get_assignment_table(
    cadet_rows: list[dict[str, str | bool]],
    target_flight_id: str,
    selected_cadet_ids: list[str],
    search_term: str = "",
    show_assigned: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    target_flight_id = str(target_flight_id)
    selected_set = set(selected_cadet_ids)
    normalized_search = search_term.strip().lower()
    candidate_rows = [
        row
        for row in cadet_rows
        if str(row["current_flight_id"] or "") != target_flight_id
    ]

    if normalized_search:
        base_rows = [
            row
            for row in candidate_rows
            if normalized_search in _assignment_haystack(row)
        ]
    elif show_assigned:
        base_rows = candidate_rows
    else:
        base_rows = [row for row in candidate_rows if not row["is_assigned"]]

    visible_rows = {str(row["cadet_id"]): row for row in base_rows}
    for row in candidate_rows:
        cadet_id = str(row["cadet_id"])
        if cadet_id in selected_set:
            visible_rows[cadet_id] = row

    ordered_rows = sorted(
        visible_rows.values(),
        key=lambda row: (
            str(row["cadet_id"]) not in selected_set,
            row["name"],
            row["rank"],
            row["email"],
        ),
    )
    return _build_cadet_table(ordered_rows, selected_set), [
        str(row["cadet_id"]) for row in ordered_rows
    ]


def has_selected_assigned_cadets(
    selected_cadet_ids: list[str],
    cadet_rows_by_id: dict[str, dict[str, str | bool]],
) -> bool:
    for cadet_id in selected_cadet_ids:
        row = cadet_rows_by_id.get(cadet_id)
        if row and row["is_assigned"]:
            return True
    return False


def get_flight_member_table(
    cadet_rows: list[dict[str, str | bool]],
    flight: dict,
) -> tuple[pd.DataFrame, list[str]]:
    flight_id = str(flight["_id"])
    rows = [
        row | {"role": "Cadet", "selectable": True}
        for row in cadet_rows
        if str(row["current_flight_id"] or "") == flight_id
    ]

    return _build_member_table(rows, set()), [str(row["cadet_id"]) for row in rows]


def get_commander_member_table(flight: dict) -> pd.DataFrame:
    commander_row = _get_commander_member_row(flight)
    if commander_row is None:
        return _build_member_table([], set())

    return _build_member_table([commander_row], set())


def get_selected_cadet_ids(
    edited_table: pd.DataFrame,
    cadet_ids: list[str],
    selection_column: str,
) -> list[str]:
    return [
        cadet_ids[idx]
        for idx, (_, row) in enumerate(edited_table.iterrows())
        if pd.notna(row[selection_column]) and bool(row[selection_column])
    ]


def assign_selected_cadets_to_flight(
    cadet_ids: list[str],
    flight_id: str,
    cadet_rows_by_id: dict[str, dict[str, str | bool]],
) -> tuple[str, str]:
    if not cadet_ids:
        return "warning", "Select at least one cadet."

    assigned_count = 0
    reassigned_count = 0
    errors = []
    target_flight_id = str(flight_id)

    for cadet_id in cadet_ids:
        row = cadet_rows_by_id.get(cadet_id)
        cadet_name = row["name"] if row else cadet_id
        current_flight_id = str(row["current_flight_id"] or "") if row else ""

        if current_flight_id == target_flight_id:
            errors.append(f"{cadet_name}: Cadet is already in this flight.")
            continue

        try:
            if current_flight_id:
                unassign_cadet_from_flight(cadet_id)
            assign_cadet_to_flight(cadet_id, flight_id)
            assigned_count += 1
            if current_flight_id:
                reassigned_count += 1
        except Exception as e:
            errors.append(f"{cadet_name}: {e}")

    return _build_assign_feedback(assigned_count, reassigned_count, errors)


def unassign_selected_cadets(
    cadet_ids: list[str],
    cadet_rows_by_id: dict[str, dict[str, str | bool]],
) -> tuple[str, str]:
    if not cadet_ids:
        return "warning", "Select at least one cadet."

    unassigned_count = 0
    errors = []

    for cadet_id in cadet_ids:
        row = cadet_rows_by_id.get(cadet_id)
        cadet_name = row["name"] if row else cadet_id
        try:
            unassign_cadet_from_flight(cadet_id)
            unassigned_count += 1
        except Exception as e:
            errors.append(f"{cadet_name}: {e}")

    if unassigned_count and not errors:
        return "success", f"Unassigned {unassigned_count} cadet(s)."

    if unassigned_count:
        return (
            "warning",
            "Unassigned "
            f"{unassigned_count} cadet(s). Could not unassign {len(errors)} cadet(s): "
            + "; ".join(errors),
        )

    return "error", f"No cadets were unassigned. {'; '.join(errors)}"


def get_member_selection_table(
    member_table: pd.DataFrame,
    selected_cadet_ids: list[str],
    member_cadet_ids: list[str],
) -> pd.DataFrame:
    selected_set = set(selected_cadet_ids)
    table = member_table.copy()
    if table.empty:
        return table

    table.insert(
        0,
        "Unassign",
        [cadet_id in selected_set for cadet_id in member_cadet_ids],  # type: ignore
    )
    return table


def get_selectable_member_ids(member_cadet_ids: list[str]) -> list[str]:
    return member_cadet_ids


def _get_commander_cadet_ids() -> set[str]:
    flights_col = get_collection("flights")
    if flights_col is None:
        return set()

    return {
        str(flight["commander_cadet_id"])
        for flight in flights_col.find({}, {"commander_cadet_id": 1})
        if flight.get("commander_cadet_id")
    }


def _build_cadet_table(
    rows: list[dict[str, str | bool]],
    selected_cadet_ids: set[str],
    include_selection: bool = True,
) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        table_row = {
            "Cadet": row["name"],
            "Rank": row["rank"],
            "Email": row["email"],
            "Current Flight": row["current_flight"] or "Unassigned",
        }
        if include_selection:
            table_row["Assign"] = str(row["cadet_id"]) in selected_cadet_ids
        table_rows.append(table_row)

    column_order = ["Assign", "Cadet", "Rank", "Email", "Current Flight"]
    if not include_selection:
        column_order = ["Cadet", "Rank", "Email", "Current Flight"]

    return pd.DataFrame(table_rows, columns=list(column_order))  # type: ignore


def _build_member_table(
    rows: list[dict[str, str | bool]],
    selected_cadet_ids: set[str],
) -> pd.DataFrame:
    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "Cadet": row["name"],
                "Role": row.get("role", "Cadet"),
                "Rank": row["rank"],
                "Email": row["email"],
                "Current Flight": row["current_flight"] or "Unassigned",
            }
        )

    return pd.DataFrame(
        table_rows,
        columns=["Cadet", "Role", "Rank", "Email", "Current Flight"],  # type: ignore
    )


def _get_commander_member_row(flight: dict) -> dict[str, str | bool] | None:
    commander = get_cadet_by_id(flight["commander_cadet_id"])
    if commander is None:
        return None

    user = get_user_by_id(commander["user_id"])
    if user is None:
        return None

    return {
        "cadet_id": str(commander["_id"]),
        "name": format_full_name(user),
        "role": "Commander",
        "rank": commander.get("rank", ""),
        "email": user.get("email", ""),
        "current_flight": flight.get("name", ""),
    }


def _assignment_haystack(row: dict[str, str | bool]) -> str:
    return (
        f"{row['name']} {row['email']} {row['rank']} {row['current_flight']}"
    ).lower()


def _build_assign_feedback(
    assigned_count: int,
    reassigned_count: int,
    errors: list[str],
) -> tuple[str, str]:
    if assigned_count and not errors:
        if reassigned_count:
            return (
                "success",
                f"Assigned {assigned_count} cadet(s). Reassigned {reassigned_count} from a previous flight.",
            )
        return "success", f"Assigned {assigned_count} cadet(s)."

    if assigned_count:
        message = f"Assigned {assigned_count} cadet(s)."
        if reassigned_count:
            message += f" Reassigned {reassigned_count} from a previous flight."
        message += f" Could not assign {len(errors)} cadet(s): {'; '.join(errors)}"
        return "warning", message

    return "error", f"No cadets were assigned. {'; '.join(errors)}"
