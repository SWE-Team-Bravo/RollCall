import hashlib
import time

import streamlit as st
import pandas as pd

from utils.audit_log import log_data_change
from utils.auth import get_current_user, require_role
from utils.db_schema_crud import (
    update_cadet,
    delete_cadet,
    update_user,
    get_user_by_id,
    get_user_by_email,
    get_cadet_by_id,
)

from services.cadets import (
    DEFAULT_ROSTER_IMPORT_ACTIONS,
    VALID_ROSTER_IMPORT_ACTIONS,
    add_cadet_for_user,
    get_all_cadets,
    validate_cadet_input,
    get_cadet_export_df,
    import_cadets_from_roster,
    parse_roster_xlsx,
    analyze_roster_for_import,
    RANK_OPTIONS,
    RANK_TO_LEVEL,
)

from services.account_settings import build_profile_updates

from utils.export import to_excel
from utils.names import format_full_name
from utils.pagination import (
    init_pagination_state,
    paginate_list,
    render_pagination_controls,
    sync_pagination_state,
)


require_role("admin", "cadre")


def add_cadet():
    if st.session_state.show_form:
        with st.form("add_cadet"):
            cadet_name = st.text_input("Name")
            cadet_lastname = st.text_input("Last Name")
            cadet_email = st.text_input("Email (must match an existing user account)")
            cadet_rank = st.selectbox("Rank", RANK_OPTIONS)

            col1, col2, spacer = st.columns([2, 2, 10])
            with col1:
                submit_button = st.form_submit_button("Submit")
            with col2:
                cancel_button = st.form_submit_button("Cancel", type="secondary")

        if cancel_button:
            st.session_state.show_form = False
            st.rerun()

        if submit_button:
            check, msg = validate_cadet_input(cadet_name, cadet_lastname, cadet_email)
            if check:
                if add_cadet_for_user(
                    cadet_email, cadet_rank, cadet_name, cadet_lastname
                ):
                    st.session_state.show_form = False
                    st.session_state.success_msg = "New cadet added successfully!"
                    st.session_state.success_time = time.time()
                    st.rerun()
                else:
                    st.error("User not found!")
            else:
                st.error(msg)


def edit_cadet(cadet):
    current_rank = str(cadet.get("rank", ""))
    rank_index = RANK_OPTIONS.index(current_rank) if current_rank in RANK_OPTIONS else 0
    cadet_id = str(cadet["_id"])

    user_doc = None
    try:
        user_id = cadet.get("user_id")
        if user_id is not None:
            user_doc = get_user_by_id(user_id)
    except Exception:
        user_doc = None

    source = user_doc or cadet

    new_first = st.text_input(
        "First Name", source.get("first_name", ""), key=f"first_{cadet_id}"
    )
    new_last = st.text_input(
        "Last Name", source.get("last_name", ""), key=f"last_{cadet_id}"
    )
    new_email = st.text_input("Email", source.get("email", ""), key=f"email_{cadet_id}")
    new_rank = st.selectbox(
        "Rank", RANK_OPTIONS, index=rank_index, key=f"rank_{cadet_id}"
    )

    col1, col2, spacer = st.columns([2, 2, 10])
    if col1.button("Save", key=f"save_{cadet_id}"):
        check, msg = validate_cadet_input(new_first, new_last, new_email)
        if check:
            before_cadet = dict(cadet)
            current_user = get_current_user()
            actor_email = (
                str(current_user.get("email", "") or "").strip()
                if current_user
                else None
            )

            if user_doc is not None:
                user_updates, errors = build_profile_updates(
                    user_doc=user_doc,
                    first_name=new_first,
                    last_name=new_last,
                    email=new_email,
                    lookup_user_by_email=get_user_by_email,
                )
                if errors:
                    for field, message in errors.items():
                        st.error(f"{field.replace('_', ' ').capitalize()}: {message}")
                    return

                update_user(user_doc["_id"], user_updates)

                # Transitional: keep cadet fields in sync for any pages that still
                # read from the cadets collection.
                update_cadet(
                    cadet_id,
                    {
                        "first_name": user_updates["first_name"],
                        "last_name": user_updates["last_name"],
                        "email": user_updates["email"],
                        "rank": new_rank,
                        "level": RANK_TO_LEVEL.get(new_rank, "freshman"),
                    },
                )
            else:
                # Fallback: if the linked user record can't be loaded, edit the cadet
                # doc directly (legacy behavior).
                update_cadet(
                    cadet_id,
                    {
                        "first_name": new_first,
                        "last_name": new_last,
                        "email": new_email,
                        "rank": new_rank,
                    },
                )

            after_cadet = get_cadet_by_id(cadet_id)
            target_label = format_full_name(
                {"first_name": new_first, "last_name": new_last},
                default=(user_doc.get("email") if user_doc else "Cadet"),
            )
            log_data_change(
                source="cadet_management",
                action="update",
                target_collection="cadets",
                target_id=cadet_id,
                actor_email=actor_email,
                target_label=target_label,
                before=before_cadet,
                after=after_cadet,
            )

            st.session_state.selected_cadet_id = cadet_id
            st.session_state.editing_id = None
            st.rerun()
        else:
            st.error(msg)

    if col2.button("Cancel", key=f"cancel_{cadet_id}"):
        st.session_state.editing_id = None
        st.rerun()


def remove_cadet(cadet):
    cadet_id = str(cadet["_id"])
    st.warning(
        f"Are you sure you want to delete {cadet.get('first_name', '')} {cadet.get('last_name', '')}?"
    )
    col1, col2, spacer = st.columns([2, 2, 10])

    if col1.button("Yes", key=f"confirm_{cadet_id}"):
        result = delete_cadet(cadet_id)
        if result and result.deleted_count > 0:
            st.session_state.pop("selected_cadet_id", None)
            st.session_state.confirm_delete_id = None
            st.session_state.success_msg = "Cadet deleted successfully!"
            st.session_state.success_time = time.time()
            st.rerun()
        else:
            st.error("Failed to delete cadet.")

    if col2.button("Cancel", key=f"canceldelete_{cadet_id}"):
        st.session_state.confirm_delete_id = None
        st.rerun()


def show_cadets():
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None
    if "selected_cadet_id" not in st.session_state:
        st.session_state.selected_cadet_id = None

    cadets = get_all_cadets()
    if not cadets:
        st.warning("No cadets found.")
        return

    if st.session_state.success_time:
        if time.time() - st.session_state.success_time < 3:
            st.success(st.session_state.success_msg)
        else:
            st.session_state.success_time = None
            st.session_state.success_msg = None

    st.subheader(f"Total Number of Cadets: {len(cadets)}")

    rows: list[dict[str, str | int]] = []
    cadet_by_id: dict[str, dict] = {}
    cadet_ids: list[str] = []
    for i, cadet in enumerate(cadets):
        cid = str(cadet.get("_id"))
        cadet_by_id[cid] = cadet
        cadet_ids.append(cid)

        user_doc = None
        try:
            user_id = cadet.get("user_id")
            if user_id is not None:
                user_doc = get_user_by_id(user_id)
        except Exception:
            user_doc = None

        source = user_doc or cadet
        rows.append(
            {
                "No.": i + 1,
                "First Name": str(source.get("first_name", "") or ""),
                "Last Name": str(source.get("last_name", "") or ""),
                "Email": str(source.get("email", "") or ""),
                "Rank": str(cadet.get("rank", "") or ""),
                "Level": (RANK_TO_LEVEL.get(str(cadet.get("rank")), "")).capitalize(),
            }
        )

    cadet_page, cadet_page_size = init_pagination_state(
        "cadet_management",
        reset_token=str(len(cadets)),
    )
    paginated_rows = paginate_list(
        rows,
        page=cadet_page,
        page_size=cadet_page_size,
    )
    sync_pagination_state("cadet_management", paginated_rows)
    page_rows = list(paginated_rows["items"])
    page_ids = cadet_ids[
        paginated_rows["skip"] : paginated_rows["skip"] + paginated_rows["page_size"]
    ]

    df = pd.DataFrame(
        page_rows,
        columns=pd.Index(["No.", "First Name", "Last Name", "Email", "Rank", "Level"]),
    )
    st.dataframe(df, hide_index=True, width="stretch")
    render_pagination_controls("cadet_management", paginated_rows)

    st.divider()

    def _cadet_label(cadet_id: str) -> str:
        c = cadet_by_id.get(cadet_id, {})
        user_doc = None
        try:
            user_id = c.get("user_id")
            if user_id is not None:
                user_doc = get_user_by_id(user_id)
        except Exception:
            user_doc = None

        source = user_doc or c
        first = str(source.get("first_name", "") or "").strip()
        last = str(source.get("last_name", "") or "").strip()
        email = str(source.get("email", "") or "").strip()
        name = f"{first} {last}".strip() or "Unknown"
        return f"{name} ({email})".strip()

    if not page_ids:
        return

    # Keep selection stable across reruns.
    if st.session_state.selected_cadet_id not in page_ids:
        st.session_state.selected_cadet_id = page_ids[0]

    cadet_labels = {cid: _cadet_label(cid) for cid in cadet_ids}
    selected_index = cadet_ids.index(st.session_state.selected_cadet_id)
    selected_id = st.selectbox(
        "Select cadet",
        options=cadet_ids,
        format_func=lambda cid: cadet_labels.get(cid, cid),
        index=selected_index,
    )
    st.session_state.selected_cadet_id = selected_id

    action_col1, action_col2, _ = st.columns([2, 2, 10])
    with action_col1:
        if st.button("Edit", key="edit_selected_cadet"):
            st.session_state.editing_id = str(selected_id)
            st.session_state.confirm_delete_id = None
            st.rerun()
    with action_col2:
        if st.button("Delete", key="delete_selected_cadet"):
            st.session_state.confirm_delete_id = str(selected_id)
            st.session_state.editing_id = None
            st.rerun()

    if st.session_state.editing_id in cadet_by_id:
        st.divider()
        edit_cadet(cadet_by_id[st.session_state.editing_id])

    if st.session_state.confirm_delete_id in cadet_by_id:
        st.divider()
        remove_cadet(cadet_by_id[st.session_state.confirm_delete_id])


st.title("Cadet Management")

try:
    get_all_cadets()
except Exception:
    st.warning("Database is not configured as of now.")
    st.stop()

if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "success_time" not in st.session_state:
    st.session_state.success_time = None
if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

tab_manage, tab_import = st.tabs(["Manage Cadets", "Import Roster"])

with tab_manage:
    export_df = get_cadet_export_df()
    col1, col2, col3, spacer = st.columns([2, 2, 2, 10])
    if isinstance(export_df, pd.DataFrame):
        col1.download_button(
            "Export CSV",
            export_df.to_csv(index=False).encode("utf-8"),
            "cadets.csv",
            "text/csv",
        )
        col2.download_button(
            "Export Excel",
            to_excel(export_df),
            "cadets.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if col3.button("Add Cadet"):
        st.session_state.show_form = True
    if st.session_state.show_form or st.session_state.success_time:
        add_cadet()
    show_cadets()

with tab_import:
    st.subheader("Import Cadets from Roster")

    if "import_result" in st.session_state:
        result = st.session_state.pop("import_result")
        if result.get("created"):
            st.success(f"Created {len(result['created'])} account(s).")
            rows = [
                {
                    "Name": c["name"],
                    "Email": c["email"],
                    "Rank": c["rank"],
                    "Temp Password": c["temp_password"],
                }
                for c in result["created"]
            ]
            st.dataframe(rows, hide_index=True, width="stretch")
        if result.get("updated"):
            st.success(f"Updated {len(result['updated'])} account(s).")
            rows = [
                {"Name": c["name"], "Email": c["email"], "Rank": c["rank"]}
                for c in result["updated"]
            ]
            st.dataframe(rows, hide_index=True, width="stretch")
        if result.get("skipped"):
            st.info(f"Skipped {len(result['skipped'])} account(s).")
        if result.get("errors"):
            st.error(f"{len(result['errors'])} error(s):")
            for err in result["errors"]:
                st.write(f"- {err['name']} ({err['email']}): {err['reason']}")

    # ---- Step 1: Upload & preview ----
    uploaded = st.file_uploader("Upload roster (.xlsx)", type=["xlsx"], key="roster_uploader")
    if uploaded:
        cadets, parse_errors = parse_roster_xlsx(uploaded)
        if parse_errors:
            for err in parse_errors:
                st.warning(err)
        if not cadets:
            st.error("No valid cadets found in the roster file.")
        else:
            # Analyze only once per upload and cache in session_state
            file_hash = hashlib.sha256(uploaded.getvalue()).hexdigest()
            if (
                st.session_state.get("roster_upload_key") != file_hash
                or "roster_preview" not in st.session_state
            ):
                st.session_state.roster_upload_key = file_hash
                st.session_state.roster_preview = analyze_roster_for_import(cadets)
                # Initialize per-row action keys to defaults
                for i, r in enumerate(st.session_state.roster_preview):
                    action_key = f"roster_action_{i}"
                    if action_key not in st.session_state:
                        ctype = r["conflict_type"]
                        default = DEFAULT_ROSTER_IMPORT_ACTIONS.get(ctype, "Skip")
                        st.session_state[action_key] = default

            preview = st.session_state.roster_preview

            # Build display dataframe
            conflict_labels = {
                "none": "—",
                "email_exists": "Email exists",
                "name_exists": "Name exists",
                "intra_file_duplicate": "Duplicate in file",
            }
            default_actions = DEFAULT_ROSTER_IMPORT_ACTIONS
            valid_actions = VALID_ROSTER_IMPORT_ACTIONS

            st.write(f"Found **{len(preview)}** cadet(s). Review the preview below before importing.")

            # Conflict resolution: global defaults for each conflict type present
            present_conflicts = {r["conflict_type"] for r in preview if r["conflict_type"] != "none"}
            if present_conflicts:
                st.divider()
                st.write("**Conflict Resolution**")
                st.caption(
                    "- **Skip**: leave the existing record untouched.\n"
                    "- **Update**: overwrite the existing user's name, email, and rank with the spreadsheet values.\n"
                    "- **Create as New**: only available for name matches (different email). Creates a separate account."
                )
                cols = st.columns(len(present_conflicts))
                for col, ctype in zip(cols, sorted(present_conflicts)):
                    with col:
                        label = f"For all {conflict_labels[ctype]}:"
                        options = valid_actions[ctype]
                        global_key = f"roster_global_{ctype}"
                        # Derive global default from the first row of this type
                        first_idx = next(
                            i for i, r in enumerate(preview) if r["conflict_type"] == ctype
                        )
                        current_global = st.session_state.get(
                            global_key, st.session_state.get(f"roster_action_{first_idx}", default_actions[ctype])
                        )
                        if current_global not in options:
                            current_global = options[0]
                        st.session_state[global_key] = current_global
                        chosen = st.selectbox(
                            label,
                            options=options,
                            key=global_key,
                        )
                        # Apply this global choice to every row of this type
                        for i, r in enumerate(preview):
                            if r["conflict_type"] == ctype:
                                st.session_state[f"roster_action_{i}"] = chosen

                # Optional per-row overrides, collapsed by default
                with st.expander("Override individual rows"):
                    for i, row in enumerate(preview):
                        ctype = row["conflict_type"]
                        if ctype == "none":
                            continue
                        label = f"{row['first_name']} {row['last_name']} ({row['email']})"
                        options = valid_actions[ctype]
                        default = st.session_state.get(
                            f"roster_action_{i}", default_actions[ctype]
                        )
                        if default not in options:
                            default = options[0]
                        st.session_state[f"roster_action_{i}"] = default
                        st.selectbox(
                            label,
                            options=options,
                            key=f"roster_action_{i}",
                        )

            # Build preview table including resolved actions
            preview_rows = []
            for i, r in enumerate(preview):
                ctype = r["conflict_type"]
                action = st.session_state.get(
                    f"roster_action_{i}", default_actions[ctype]
                )
                preview_rows.append(
                    {
                        "First Name": r["first_name"],
                        "Last Name": r["last_name"],
                        "Email": r["email"],
                        "Rank": r["rank"],
                        "Conflict": conflict_labels.get(ctype, "—"),
                        "Action": action,
                    }
                )
            preview_df = pd.DataFrame(preview_rows)
            st.dataframe(preview_df, hide_index=True, width="stretch")

            # ---- Step 2: Confirm import ----
            st.divider()
            if st.button("Confirm Import", type="primary"):
                actions = [
                    st.session_state.get(
                        f"roster_action_{i}", default_actions[r["conflict_type"]]
                    )
                    for i, r in enumerate(preview)
                ]
                with st.spinner("Importing cadets..."):
                    result = import_cadets_from_roster(
                        preview,
                        actions,
                        actor_user=get_current_user(),
                    )
                st.session_state.import_result = result
                # Clean up preview state so a fresh upload starts clean
                for key in list(st.session_state.keys()):
                    if key.startswith("roster_"):
                        del st.session_state[key]
                st.rerun()
