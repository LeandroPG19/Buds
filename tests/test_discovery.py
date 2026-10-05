import json
import subprocess

from bluetooth.discovery import BluetoothDevice, BluetoothDiscovery
from bluetooth.profiles import PROFILE_REDMI_BUDS_5_PRO, PROFILE_REDMI_BUDS_6_PLAY, PROFILE_XIAOMI_FAMILY


def test_windows_script_timeout_leaves_room_for_a_slow_pc(monkeypatch):
    # Measured 4.5 s on a healthy PC; the old 5 s limit turned slowness into "no Buds found".
    seen = {}

    def fake_check_output(cmd, **kwargs):
        seen.update(kwargs)
        return "[]"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    BluetoothDiscovery._run_discovery_script_win()
    assert seen["timeout"] >= 15


def test_parse_windows_output_keeps_every_device_with_an_address():
    output = json.dumps(
        [
            {"Name": "Mouse", "Address": "aa-bb-cc-dd-ee-ff"},
            {"Name": "Redmi Buds 5 Pro", "Address": "AA:BB:CC:DD:EE:01"},
            {"Name": "Redmi Buds 5 Pro Avrcp Transport", "Address": ""},
        ]
    )
    devices = BluetoothDiscovery._parse_devices_win(output)
    assert devices == [
        BluetoothDevice("Mouse", "AA:BB:CC:DD:EE:FF"),
        BluetoothDevice("Redmi Buds 5 Pro", "AA:BB:CC:DD:EE:01"),
    ]


def test_parse_windows_output_accepts_a_single_object():
    output = json.dumps({"Name": "Redmi Buds 6 Play", "Address": "112233445566"})
    assert BluetoothDiscovery._parse_devices_win(output) == [
        BluetoothDevice("Redmi Buds 6 Play", "11:22:33:44:55:66")
    ]


def test_parse_windows_output_empty_or_broken_gives_no_devices():
    assert BluetoothDiscovery._parse_devices_win("") == []
    assert BluetoothDiscovery._parse_devices_win("not json") == []


def test_select_ignores_non_buds_devices():
    devices = [BluetoothDevice("Logitech MX", "AA:AA:AA:AA:AA:AA")]
    assert BluetoothDiscovery.select_device(devices) is None


def test_select_prefers_a_model_with_its_own_profile_over_the_family_match():
    devices = [
        BluetoothDevice("Redmi Buds 4 Active", "11:11:11:11:11:11"),
        BluetoothDevice("Redmi Buds 6 Play", "22:22:22:22:22:22"),
    ]
    device, profile = BluetoothDiscovery.select_device(devices)
    assert device.address == "22:22:22:22:22:22"
    assert profile is PROFILE_REDMI_BUDS_6_PLAY


def test_select_picks_the_buds_5_pro_with_its_own_profile():
    devices = [
        BluetoothDevice("Logitech MX", "AA:AA:AA:AA:AA:AA"),
        BluetoothDevice("Redmi Buds 5 Pro", "11:11:11:11:11:11"),
    ]
    device, profile = BluetoothDiscovery.select_device(devices)
    assert device.name == "Redmi Buds 5 Pro"
    assert profile is PROFILE_REDMI_BUDS_5_PRO


def test_select_picks_another_family_model_when_it_is_the_only_one():
    devices = [
        BluetoothDevice("Logitech MX", "AA:AA:AA:AA:AA:AA"),
        BluetoothDevice("Redmi Buds 4 Active", "11:11:11:11:11:11"),
    ]
    device, profile = BluetoothDiscovery.select_device(devices)
    assert device.name == "Redmi Buds 4 Active"
    assert profile is PROFILE_XIAOMI_FAMILY


def test_select_with_nothing_connected_returns_none():
    assert BluetoothDiscovery.select_device([]) is None
