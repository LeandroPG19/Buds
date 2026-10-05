import subprocess

import pytest

from bluetooth import os_battery


@pytest.mark.parametrize(
    "text, expected",
    [
        ("60", 60),
        ("  100\r\n", 100),
        ("0", 0),
        ("", None),
        ("abc", None),
        ("101", None),
        ("-5", None),
    ],
)
def test_parse_windows_output(text, expected):
    assert os_battery.parse_windows_output(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("\tBattery Percentage: 0x3c (60)\n", 60),
        ("Name: Buds\n\tBattery Percentage: 0x64 (100)\nPaired: yes", 100),
        ("Name: Buds\nPaired: yes", None),
        ("Battery Percentage: 0xff (255)", None),
    ],
)
def test_parse_bluetoothctl_output(text, expected):
    assert os_battery.parse_bluetoothctl_output(text) == expected


def test_windows_query_uses_only_the_hex_of_the_address(monkeypatch):
    seen = {}

    def fake_check_output(cmd, **kwargs):
        seen["script"] = cmd[-1]
        return "60"

    monkeypatch.setattr(os_battery.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    assert os_battery.read_battery("AA:BB:CC:DD:EE:01") == 60
    assert "AABBCCDDEE01" in seen["script"]
    assert "AA:BB" not in seen["script"]


def test_an_address_that_is_not_a_mac_is_rejected_before_it_reaches_powershell(monkeypatch):
    called = []
    monkeypatch.setattr(os_battery.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: called.append(1) or "60")
    assert os_battery.read_battery("x'; Remove-Item C:\\ -Recurse; '") is None
    assert called == []


def test_a_failing_query_gives_none_instead_of_raising(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("powershell", 1)

    monkeypatch.setattr(os_battery.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "check_output", boom)
    assert os_battery.read_battery("AA:BB:CC:DD:EE:01") is None


def test_linux_reads_bluetoothctl(monkeypatch):
    monkeypatch.setattr(os_battery.sys, "platform", "linux")
    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **k: "Name: Buds\n\tBattery Percentage: 0x32 (50)\n"
    )
    assert os_battery.read_battery("AA:BB:CC:DD:EE:01") == 50
