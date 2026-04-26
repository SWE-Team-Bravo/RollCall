from utils.attendance_status import (
    NO_RECORD_STATUS_LABEL,
    get_attendance_status_cell_style,
    get_attendance_status_label,
    get_effective_attendance_status,
)


def test_effective_attendance_status_marks_approved_absence_as_waived():
    assert get_effective_attendance_status("absent", "approved") == "waived"


def test_attendance_status_label_maps_waived_to_excused():
    assert get_attendance_status_label("absent", "approved") == "Excused"


def test_attendance_status_label_uses_default_for_unknown_status():
    assert get_attendance_status_label("unknown", default="Absent") == "Absent"


def test_attendance_status_label_uses_no_record_default_for_missing_status():
    assert (
        get_attendance_status_label(None, default=NO_RECORD_STATUS_LABEL)
        == NO_RECORD_STATUS_LABEL
    )


def test_attendance_status_cell_style_matches_no_record():
    style = get_attendance_status_cell_style(NO_RECORD_STATUS_LABEL)

    assert "background-color: #D9DDE6" in style
    assert "font-weight: 700" in style


def test_attendance_status_cell_style_matches_present():
    style = get_attendance_status_cell_style("Present")

    assert "background-color: #7FE08A" in style
    assert "font-weight: 700" in style


def test_attendance_status_cell_style_matches_absent():
    style = get_attendance_status_cell_style("Absent")

    assert "background-color: #E07F7F" in style
    assert "font-weight: 700" in style


def test_attendance_status_cell_style_returns_empty_for_unknown_status():
    assert get_attendance_status_cell_style("Unknown") == ""
