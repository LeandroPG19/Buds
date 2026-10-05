from utils.game_monitor import _extract_int, _extract_wm_class


def test_wm_class_uses_the_last_name():
    assert _extract_wm_class('WM_CLASS(STRING) = "steam_app_730", "Steam"') == "steam"


def test_wm_class_without_value_is_empty():
    assert _extract_wm_class("WM_CLASS:  not found.") == ""
    assert _extract_wm_class("WM_CLASS(STRING) = ") == ""


def test_extract_int_reads_negative_numbers():
    assert _extract_int("Absolute upper-left X:  -12", r"Absolute upper-left X:\s+(-?\d+)") == -12


def test_extract_int_without_match_is_none():
    assert _extract_int("nothing here", r"Width:\s+(\d+)") is None
