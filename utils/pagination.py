from __future__ import annotations

from math import ceil
from typing import Any, Mapping

import streamlit as st

PAGE_SIZE_OPTIONS: tuple[int, ...] = (25, 50, 100)
DEFAULT_PAGE_SIZE = PAGE_SIZE_OPTIONS[0]


def _coerce_page_size(value: Any, *, default: int = DEFAULT_PAGE_SIZE) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        return default
    return page_size if page_size > 0 else default


def normalize_page(value: Any) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def normalize_page_size(
    value: Any,
    *,
    allowed: tuple[int, ...] = PAGE_SIZE_OPTIONS,
    default: int = DEFAULT_PAGE_SIZE,
) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        return default
    return page_size if page_size in allowed else default


def build_pagination_metadata(
    *,
    page: Any,
    page_size: Any,
    total_count: Any,
) -> dict[str, int]:
    normalized_page_size = _coerce_page_size(page_size)
    normalized_total_count = max(int(total_count or 0), 0)
    total_pages = max(1, ceil(normalized_total_count / normalized_page_size))
    normalized_page = min(normalize_page(page), total_pages)
    skip = (normalized_page - 1) * normalized_page_size

    return {
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total_count": normalized_total_count,
        "total_pages": total_pages,
        "skip": skip,
    }


def paginate_list(
    items: list[dict[str, Any]],
    *,
    page: Any,
    page_size: Any,
) -> dict[str, Any]:
    pagination = build_pagination_metadata(
        page=page,
        page_size=page_size,
        total_count=len(items),
    )
    start = pagination["skip"]
    end = start + pagination["page_size"]
    return {**pagination, "items": items[start:end]}


def init_pagination_state(
    prefix: str,
    *,
    reset_token: str | None = None,
    default_page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[int, int]:
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    reset_key = f"{prefix}_reset_token"

    if page_size_key not in st.session_state:
        st.session_state[page_size_key] = normalize_page_size(default_page_size)
    else:
        st.session_state[page_size_key] = normalize_page_size(
            st.session_state[page_size_key]
        )

    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    else:
        st.session_state[page_key] = normalize_page(st.session_state[page_key])

    if reset_token is not None and st.session_state.get(reset_key) != reset_token:
        st.session_state[reset_key] = reset_token
        st.session_state[page_key] = 1

    return st.session_state[page_key], st.session_state[page_size_key]


def sync_pagination_state(prefix: str, pagination: Mapping[str, Any]) -> None:
    st.session_state[f"{prefix}_page"] = int(pagination.get("page", 1) or 1)
    st.session_state[f"{prefix}_page_size"] = normalize_page_size(
        pagination.get("page_size", DEFAULT_PAGE_SIZE)
    )


def render_pagination_controls(
    prefix: str,
    pagination: Mapping[str, Any],
    *,
    rerun_scope: str | None = None,
) -> None:
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    page_value = int(pagination.get("page", 1) or 1)
    total_pages = max(int(pagination.get("total_pages", 1) or 1), 1)
    total_count = max(int(pagination.get("total_count", 0) or 0), 0)

    def _reset_to_first_page() -> None:
        st.session_state[page_key] = 1

    def _go_to_page(next_page: int) -> None:
        st.session_state[page_key] = min(max(int(next_page), 1), total_pages)

    summary_col, page_col, page_size_col, prev_col, next_col = st.columns(
        [3, 1, 1, 1, 1]
    )
    summary_col.caption(f"Page {page_value} of {total_pages} • {total_count} total")
    page_col.selectbox(
        "Page",
        options=list(range(1, total_pages + 1)),
        key=page_key,
        label_visibility="collapsed",
    )
    page_size_col.selectbox(
        "Page size",
        options=list(PAGE_SIZE_OPTIONS),
        key=page_size_key,
        label_visibility="collapsed",
        on_change=_reset_to_first_page,
    )

    prev_col.button(
        "Previous",
        key=f"{prefix}_prev",
        disabled=page_value <= 1,
        width="stretch",
        on_click=_go_to_page,
        args=(page_value - 1,),
    )

    next_col.button(
        "Next",
        key=f"{prefix}_next",
        disabled=page_value >= total_pages,
        width="stretch",
        on_click=_go_to_page,
        args=(page_value + 1,),
    )
