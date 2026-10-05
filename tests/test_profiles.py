import pytest

from bluetooth.profiles import (
    PROFILES,
    PROFILE_REDMI_BUDS_5_PRO,
    PROFILE_REDMI_BUDS_6_PLAY,
    PROFILE_XIAOMI_FAMILY,
    match_profile,
)


def test_buds_6_play_matches_its_verified_profile():
    profile = match_profile("Redmi Buds 6 Play")
    assert profile is PROFILE_REDMI_BUDS_6_PLAY
    assert profile.verified is True


@pytest.mark.parametrize(
    "name",
    [
        "Redmi Buds 3 Lite",
        "Redmi Buds 4 Active",
        "Xiaomi Buds 4 Pro",
        "Xiaomi Buds 3T Pro",
        "REDMI BUDS 5",
        "redmi buds 6 active",
    ],
)
def test_other_family_models_use_the_unverified_family_profile(name):
    profile = match_profile(name)
    assert profile is PROFILE_XIAOMI_FAMILY
    assert profile.verified is False


@pytest.mark.parametrize("name", ["", "Logitech MX Master 3", "JBL Tune 230NC", "Mi Band 8", "Budsmith"])
def test_unrelated_devices_do_not_match(name):
    assert match_profile(name) is None


@pytest.mark.parametrize("name", ["Redmi Buds 5 Pro", "REDMI BUDS 5 PRO", "Redmi Buds 5 Pro Hands-Free"])
def test_buds_5_pro_has_its_own_authenticated_profile(name):
    assert match_profile(name) is PROFILE_REDMI_BUDS_5_PRO


def test_buds_5_pro_profile_describes_how_to_talk_to_it():
    p = PROFILE_REDMI_BUDS_5_PRO
    assert p.verified is True
    assert p.transport == "spp_auth"
    assert p.service_uuid == "0000fd2d-0000-1000-8000-00805f9b34fb"
    assert p.fallback_ports == (24,)
    assert p.supports_low_latency is False


def test_only_the_5_pro_offers_noise_control():
    assert PROFILE_REDMI_BUDS_5_PRO.supports_anc is True
    assert PROFILE_REDMI_BUDS_6_PLAY.supports_anc is False
    assert PROFILE_XIAOMI_FAMILY.supports_anc is False


def test_the_6_play_keeps_the_legacy_transport_and_latency_support():
    p = PROFILE_REDMI_BUDS_6_PLAY
    assert p.transport == "legacy"
    assert p.supports_low_latency is True


def test_plain_buds_5_is_not_the_pro():
    assert match_profile("Redmi Buds 5") is PROFILE_XIAOMI_FAMILY


def test_specific_profiles_are_tried_before_the_family_one():
    family = PROFILES.index(PROFILE_XIAOMI_FAMILY)
    assert PROFILES.index(PROFILE_REDMI_BUDS_6_PLAY) < family
    assert PROFILES.index(PROFILE_REDMI_BUDS_5_PRO) < family


def test_verified_profile_keeps_the_protocol_values_from_the_hardware_tests():
    p = PROFILE_REDMI_BUDS_6_PLAY
    assert p.rfcomm_port == 6
    assert p.battery_pattern == bytes.fromhex("02020407")
    assert p.battery_request == "fedcbac40200050bffffffffef4f"
    assert p.mode_template == "fedcbac4f20005{counter}03002f{param}ef"
    assert p.counter == 0x90
    assert p.mode_ack_size == 14
    assert p.setup_packets == ("fedcba04510003000301ef",)


def test_profile_keys_are_unique():
    keys = [p.key for p in PROFILES]
    assert len(keys) == len(set(keys))
