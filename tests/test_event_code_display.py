from __future__ import annotations

from services.event_code_display import (
    build_code_panel_html,
    build_fullscreen_code_html,
)


def test_build_code_panel_html_contains_code():
    html = build_code_panel_html("123456")
    assert "123456" in html


def test_build_code_panel_html_different_codes():
    html_a = build_code_panel_html("000001")
    html_b = build_code_panel_html("999999")
    assert "000001" in html_a
    assert "999999" in html_b
    assert "000001" not in html_b
    assert "999999" not in html_a


def test_build_code_panel_html_has_code_element_id():
    html = build_code_panel_html("123456")
    assert "id=" in html


def test_build_code_panel_html_returns_string():
    result = build_code_panel_html("000000")
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_fullscreen_code_html_contains_code():
    html = build_fullscreen_code_html("654321")
    assert "654321" in html


def test_build_fullscreen_code_html_different_codes():
    html_a = build_fullscreen_code_html("111111")
    html_b = build_fullscreen_code_html("222222")
    assert "111111" in html_a
    assert "222222" in html_b
    assert "111111" not in html_b
    assert "222222" not in html_a


def test_build_fullscreen_code_html_larger_font_than_panel():
    panel_html = build_code_panel_html("123456")
    fullscreen_html = build_fullscreen_code_html("123456")
    panel_size = int(
        "".join(
            c for c in panel_html.split("font-size")[1].split(";")[0] if c.isdigit()
        )
    )
    fullscreen_size = int(
        "".join(
            c
            for c in fullscreen_html.split("font-size")[1].split(";")[0]
            if c.isdigit()
        )
    )
    assert fullscreen_size > panel_size


def test_build_fullscreen_code_html_returns_string():
    result = build_fullscreen_code_html("000000")
    assert isinstance(result, str)
    assert len(result) > 0
