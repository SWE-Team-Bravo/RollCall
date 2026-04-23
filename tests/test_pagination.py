from utils.pagination import build_pagination_metadata, normalize_page_size, paginate_list


def test_normalize_page_size_rejects_unsupported_values():
    assert normalize_page_size(10) == 25
    assert normalize_page_size("50") == 50


def test_build_pagination_metadata_clamps_page_to_last_page():
    pagination = build_pagination_metadata(page=99, page_size=25, total_count=40)

    assert pagination["page"] == 2
    assert pagination["page_size"] == 25
    assert pagination["total_pages"] == 2
    assert pagination["skip"] == 25


def test_paginate_list_returns_slice_and_metadata():
    paginated = paginate_list(
        [{"value": value} for value in range(6)],
        page=2,
        page_size=25,
    )

    assert paginated["page"] == 1
    assert paginated["page_size"] == 25
    assert paginated["total_count"] == 6
    assert [item["value"] for item in paginated["items"]] == list(range(6))
