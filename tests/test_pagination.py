import pytest  # type: ignore

from utils.pagination import (
    build_pagination_metadata,
    normalize_page_size,
    paginate_list,
)


@pytest.mark.parametrize("page_size", [25, "50", 100])
def test_normalize_page_size_accepts_valid_values(page_size):
    assert normalize_page_size(page_size) == int(page_size)


@pytest.mark.parametrize("page_size", [10, "abc", None, 0, -25])
def test_normalize_page_size_defaults_invalid_values(page_size):
    assert normalize_page_size(page_size) == 25


@pytest.mark.parametrize("page", [0, -1])
def test_build_pagination_metadata_clamps_non_positive_page_to_first_page(page):
    pagination = build_pagination_metadata(page=page, page_size=25, total_count=40)

    assert pagination["page"] == 1
    assert pagination["skip"] == 0


def test_build_pagination_metadata_defaults_non_numeric_page_size():
    pagination = build_pagination_metadata(page=1, page_size="abc", total_count=40)

    assert pagination["page_size"] == 25
    assert pagination["total_pages"] == 2


def test_build_pagination_metadata_clamps_page_to_last_page():
    pagination = build_pagination_metadata(page=99, page_size=25, total_count=40)

    assert pagination["page"] == 2
    assert pagination["page_size"] == 25
    assert pagination["total_pages"] == 2
    assert pagination["skip"] == 25


def test_build_pagination_metadata_returns_normal_page_without_clamping():
    pagination = build_pagination_metadata(page=2, page_size=25, total_count=90)

    assert pagination["page"] == 2
    assert pagination["page_size"] == 25
    assert pagination["total_count"] == 90
    assert pagination["total_pages"] == 4
    assert pagination["skip"] == 25


def test_paginate_list_returns_empty_collection_metadata():
    paginated = paginate_list([], page=2, page_size=25)

    assert paginated["page"] == 1
    assert paginated["page_size"] == 25
    assert paginated["total_count"] == 0
    assert paginated["total_pages"] == 1
    assert paginated["skip"] == 0
    assert paginated["items"] == []


def test_paginate_list_returns_multi_page_slice_and_metadata():
    paginated = paginate_list(
        [{"value": value} for value in range(60)],
        page=2,
        page_size=25,
    )

    assert paginated["page"] == 2
    assert paginated["page_size"] == 25
    assert paginated["total_count"] == 60
    assert paginated["total_pages"] == 3
    assert paginated["skip"] == 25
    assert [item["value"] for item in paginated["items"]] == list(range(25, 50))
