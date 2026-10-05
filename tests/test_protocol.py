import pytest

from bluetooth.profiles import PROFILE_REDMI_BUDS_6_PLAY
from bluetooth.protocol import BatteryStatus, BudsProtocol


@pytest.fixture
def protocol():
    return BudsProtocol(PROFILE_REDMI_BUDS_6_PLAY)


def test_low_latency_command_matches_the_hardware_tested_bytes(protocol):
    assert protocol.build_mode_command("low") == bytes.fromhex("fedcbac4f200059003002f01ef")


def test_standard_command_matches_the_hardware_tested_bytes(protocol):
    assert protocol.build_mode_command("std") == bytes.fromhex("fedcbac4f200059003002f00ef")


def test_battery_request_matches_the_hardware_tested_bytes(protocol):
    assert protocol.build_battery_request() == bytes.fromhex("fedcbac40200050bffffffffef4f")


def test_parse_battery_reads_the_three_bytes_after_the_pattern(protocol):
    data = b"\xfe\xdc\xba\xc4" + bytes.fromhex("02020407") + bytes([80, 90, 100]) + b"\xef"
    assert protocol.parse_battery(data) == BatteryStatus(left=80, right=90, case=100)


def test_parse_battery_keeps_the_charging_bit_untouched(protocol):
    data = bytes.fromhex("02020407") + bytes([128 + 50, 70, 0xFF])
    status = protocol.parse_battery(data)
    assert (status.left, status.right, status.case) == (178, 70, 255)


def test_parse_battery_without_pattern_gives_none(protocol):
    assert protocol.parse_battery(b"\x00\x01\x02\x03") is None


def test_parse_battery_truncated_packet_gives_none(protocol):
    assert protocol.parse_battery(bytes.fromhex("02020407") + bytes([80, 90])) is None


def test_battery_packet_detection(protocol):
    assert protocol.is_battery_packet(b"\x00" + bytes.fromhex("02020407") + b"\x00")
    assert not protocol.is_battery_packet(b"\x00\x00")


def test_mode_ack_is_recognised_by_packet_size(protocol):
    assert protocol.is_mode_ack_packet(14)
    assert not protocol.is_mode_ack_packet(15)


def test_mode_names():
    assert BudsProtocol.get_mode_name("low") == "Low latency"
    assert BudsProtocol.get_mode_name("std") == "Standard"
