import json

import pytest

from utils import user_preferences as prefs


@pytest.fixture(autouse=True)
def appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return tmp_path


def settings_file(appdata):
    return appdata / "MiBudsClient" / "settings.json"


def test_defaults_when_nothing_is_saved():
    assert prefs.get_low_latency_mode() == "off"
    assert prefs.get_low_latency_hold_until_app_close() is True
    assert "chrome.exe" in prefs.get_low_latency_exceptions("windows")
    assert prefs.get_low_latency_includes("windows") == []


def test_mode_round_trip_and_invalid_values_are_ignored():
    prefs.set_low_latency_mode("auto")
    assert prefs.get_low_latency_mode() == "auto"
    prefs.set_low_latency_mode("turbo")
    assert prefs.get_low_latency_mode() == "auto"


def test_legacy_include_mode_reads_as_auto(appdata):
    settings_file(appdata).parent.mkdir(parents=True)
    settings_file(appdata).write_text(json.dumps({"low_latency_mode": "include"}), encoding="utf-8")
    assert prefs.get_low_latency_mode() == "auto"


def test_lists_are_lowercased_stripped_and_deduplicated():
    prefs.set_low_latency_includes([" Game.EXE ", "game.exe", "", "Other.exe"], "windows")
    assert prefs.get_low_latency_includes("windows") == ["game.exe", "other.exe"]


def test_platforms_keep_separate_lists():
    prefs.set_low_latency_exceptions(["a.exe"], "windows")
    prefs.set_low_latency_exceptions(["b"], "linux")
    assert prefs.get_low_latency_exceptions("windows") == ["a.exe"]
    assert prefs.get_low_latency_exceptions("linux") == ["b"]


def test_legacy_exceptions_are_split_by_platform(appdata):
    settings_file(appdata).parent.mkdir(parents=True)
    settings_file(appdata).write_text(
        json.dumps({"low_latency_exceptions": ["Chrome.exe", "firefox"]}), encoding="utf-8"
    )
    assert prefs.get_low_latency_exceptions("windows") == ["chrome.exe"]
    assert prefs.get_low_latency_exceptions("linux") == ["firefox"]


def test_corrupt_settings_file_falls_back_to_defaults(appdata):
    settings_file(appdata).parent.mkdir(parents=True)
    settings_file(appdata).write_text("{not json", encoding="utf-8")
    assert prefs.get_low_latency_mode() == "off"


def test_update_notification_is_skipped_only_for_the_chosen_version():
    assert prefs.should_show_update_notification("v1.0.0") is True
    prefs.suppress_update_notification("v1.0.0")
    assert prefs.should_show_update_notification("v1.0.0") is False
    assert prefs.should_show_update_notification("v1.1.0") is True


def test_failed_save_does_not_destroy_the_previous_settings(appdata):
    prefs.set_low_latency_mode("on")
    prefs._save_settings({"low_latency_mode": object()})
    assert json.loads(settings_file(appdata).read_text(encoding="utf-8")) == {"low_latency_mode": "on"}


def test_save_leaves_no_temporary_files(appdata):
    prefs.set_low_latency_mode("on")
    assert [p.name for p in settings_file(appdata).parent.iterdir()] == ["settings.json"]
