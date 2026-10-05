"""Find the RFCOMM channel of a service from the SDP records the OS cached for a paired device.

Python's socket module cannot run an SDP query, and the channel of the control service differs
per model (Redmi Buds 6 Play: 6, Redmi Buds 5 Pro: 24). Windows keeps the records of every paired
device in the registry, so they can be read without extra libraries or admin rights.
"""

import re
import sys
import uuid
from typing import Optional

# SDP data elements: UUID128 is 0x1C + 16 bytes; ProtocolDescriptor RFCOMM is UUID16 0x0003
# followed by a uint8 (0x08) channel.
_UUID128_TAG = b"\x1c"
_RFCOMM_CHANNEL = re.compile(rb"\x19\x00\x03\x08(.)", re.DOTALL)

_DEVICES_KEY = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
_RECORD_FOLDERS = ("CachedServices", "DynamicCachedServices")


def _uuid_bytes(service_uuid: str) -> Optional[bytes]:
    try:
        return uuid.UUID(service_uuid).bytes
    except ValueError:
        return None


def channels_for_uuid(records: list[bytes], service_uuid: str) -> list[int]:
    """RFCOMM channels of the records whose service class is `service_uuid`, without duplicates."""
    wanted = _uuid_bytes(service_uuid)
    if wanted is None:
        return []

    channels: list[int] = []
    for record in records:
        if _UUID128_TAG + wanted not in record:
            continue
        match = _RFCOMM_CHANNEL.search(record)
        if match and match.group(1)[0] not in channels:
            channels.append(match.group(1)[0])
    return channels


def _read_cached_records_windows(mac_hex: str) -> list[bytes]:
    import winreg

    records: list[bytes] = []
    for folder in _RECORD_FOLDERS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{_DEVICES_KEY}\\{mac_hex}\\{folder}") as key:
                index = 0
                while True:
                    _, value, _ = winreg.EnumValue(key, index)
                    index += 1
                    if isinstance(value, bytes):
                        records.append(value)
        except OSError:
            continue
    return records


def find_rfcomm_channels(address: str, service_uuid: str) -> list[int]:
    """Channels for a service of a paired device; empty when unknown (other OS, not paired)."""
    mac_hex = re.sub(r"[:\-\s]", "", address or "").lower()
    if sys.platform != "win32" or not re.fullmatch(r"[0-9a-f]{12}", mac_hex):
        return []
    try:
        return channels_for_uuid(_read_cached_records_windows(mac_hex), service_uuid)
    except OSError:
        return []
