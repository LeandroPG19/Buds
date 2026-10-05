"""Per-model protocol profiles for Xiaomi/Redmi Buds."""

import re
from dataclasses import dataclass
from typing import Optional

from .constants import (
    BATTERY_PATTERN,
    BATTERY_REQUEST_PAYLOAD,
    COUNTER_VALUE,
    MODE_COMMAND_TEMPLATE,
    PACKET_SIZE_MODE_ACK,
    RFCOMM_PORT,
    SETUP_PACKET,
)


@dataclass(frozen=True)
class DeviceProfile:
    """Everything that can differ between earbud models.

    `verified` is True only for models whose values were tested on real hardware.
    The rest reuse the same values and are flagged so the app records their traffic.
    """

    key: str
    display_name: str
    name_pattern: str
    verified: bool
    # "legacy": send commands straight away (Redmi Buds 6 Play).
    # "spp_auth": authenticate first with the SAFER+ challenge (Redmi Buds 5 Pro).
    transport: str = "legacy"
    # Control service whose RFCOMM channel is read from the OS SDP records; the ports in
    # `fallback_ports` (or `rfcomm_port` when empty) are tried when the OS has no records.
    service_uuid: Optional[str] = None
    fallback_ports: tuple[int, ...] = ()
    supports_low_latency: bool = True
    # Off / noise cancelling / transparency, verified on a Redmi Buds 5 Pro.
    supports_anc: bool = False
    rfcomm_port: int = RFCOMM_PORT
    battery_pattern: bytes = BATTERY_PATTERN
    battery_request: str = BATTERY_REQUEST_PAYLOAD
    mode_template: str = MODE_COMMAND_TEMPLATE
    counter: int = COUNTER_VALUE
    mode_ack_size: int = PACKET_SIZE_MODE_ACK
    setup_packets: tuple[str, ...] = (SETUP_PACKET,)

    def matches(self, device_name: str) -> bool:
        return re.search(self.name_pattern, device_name or "", re.IGNORECASE) is not None


PROFILE_REDMI_BUDS_6_PLAY = DeviceProfile(
    key="redmi_buds_6_play",
    display_name="Redmi Buds 6 Play",
    name_pattern=r"\bredmi\s*buds\s*6\s*play\b",
    verified=True,
)

# Verified on a real unit: authentication and battery (left, right, case). Its low latency
# command is unknown, so it is not offered.
PROFILE_REDMI_BUDS_5_PRO = DeviceProfile(
    key="redmi_buds_5_pro",
    display_name="Redmi Buds 5 Pro",
    name_pattern=r"\bredmi\s*buds\s*5\s*pro\b",
    verified=True,
    transport="spp_auth",
    service_uuid="0000fd2d-0000-1000-8000-00805f9b34fb",
    fallback_ports=(24,),
    supports_low_latency=False,
    supports_anc=True,
)

PROFILE_XIAOMI_FAMILY = DeviceProfile(
    key="xiaomi_buds_family",
    display_name="Xiaomi/Redmi Buds",
    name_pattern=r"\b(?:redmi|xiaomi|mi)\s*buds\b",
    verified=False,
)

# Specific models first: the first profile that matches a name wins.
PROFILES: tuple[DeviceProfile, ...] = (
    PROFILE_REDMI_BUDS_6_PLAY,
    PROFILE_REDMI_BUDS_5_PRO,
    PROFILE_XIAOMI_FAMILY,
)

DEFAULT_PROFILE = PROFILE_XIAOMI_FAMILY


def match_profile(device_name: str) -> Optional[DeviceProfile]:
    """Return the profile for a Bluetooth device name, or None if it is not a Buds."""
    for profile in PROFILES:
        if profile.matches(device_name):
            return profile
    return None
