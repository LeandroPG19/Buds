"""Protocol handling for Mi Buds communication."""

from dataclasses import dataclass
from typing import Optional

from .profiles import DEFAULT_PROFILE, DeviceProfile


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BatteryStatus:
    """Battery levels for all components."""
    left: int
    right: int
    case: int


# ─────────────────────────────────────────────────────────────────────────────
# Protocol Handler
# ─────────────────────────────────────────────────────────────────────────────
class BudsProtocol:
    """Handles protocol encoding/decoding for one Buds model."""

    def __init__(self, profile: DeviceProfile = DEFAULT_PROFILE):
        self.profile = profile

    def build_mode_command(self, mode: str) -> bytes:
        """Build latency mode command payload.

        Args:
            mode: "low" for low latency, anything else for standard

        Returns:
            Bytes payload to send
        """
        param = "01" if mode == "low" else "00"
        counter = hex(self.profile.counter)[2:].zfill(2)
        return bytes.fromhex(self.profile.mode_template.format(counter=counter, param=param))

    def build_battery_request(self) -> bytes:
        """Build battery status request payload."""
        return bytes.fromhex(self.profile.battery_request)

    def parse_battery(self, data: bytes) -> Optional[BatteryStatus]:
        """Parse battery information from data packet.

        Args:
            data: Raw data received from device

        Returns:
            BatteryStatus if found, None otherwise
        """
        idx = data.find(self.profile.battery_pattern)
        if idx == -1:
            return None

        start = idx + len(self.profile.battery_pattern)
        if len(data) < start + 3:
            return None

        return BatteryStatus(left=data[start], right=data[start + 1], case=data[start + 2])

    def is_battery_packet(self, data: bytes) -> bool:
        """Check if packet contains battery status pattern."""
        return self.profile.battery_pattern in data

    def is_mode_ack_packet(self, packet_size: int) -> bool:
        """Check if packet size indicates a mode acknowledgment packet."""
        return packet_size == self.profile.mode_ack_size

    @staticmethod
    def get_mode_name(mode: str) -> str:
        """Get human-readable mode name."""
        return "Low latency" if mode == "low" else "Standard"
