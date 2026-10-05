"""Battery level reported by the OS for any Bluetooth earbuds (HFP battery indicator).

Used for models whose own protocol is not verified: it needs no model-specific bytes,
but it is one combined percentage, not left/right/case.
"""

import re
import subprocess
import sys
from typing import Optional

QUERY_TIMEOUT = 15

# DEVPKEY_Bluetooth_Battery, published on the Hands-Free node of the device.
_WINDOWS_SCRIPT = r"""
$mac = '__MAC__'
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*$mac*" } | ForEach-Object {
    (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' -ErrorAction SilentlyContinue).Data
} | Where-Object { $_ -ne $null } | Select-Object -First 1
"""

_MAC_HEX = re.compile(r"^[0-9A-F]{12}$")
_BLUETOOTHCTL_BATTERY = re.compile(r"Battery Percentage:\s*0x[0-9a-fA-F]+\s*\((\d+)\)")


def _percentage(value: str) -> Optional[int]:
    if not re.fullmatch(r"\d{1,3}", value):
        return None
    level = int(value)
    return level if level <= 100 else None


def parse_windows_output(output: str) -> Optional[int]:
    return _percentage((output or "").strip())


def parse_bluetoothctl_output(output: str) -> Optional[int]:
    match = _BLUETOOTHCTL_BATTERY.search(output or "")
    return _percentage(match.group(1)) if match else None


def read_battery(address: str) -> Optional[int]:
    """Return the OS-reported battery percentage for a device MAC, or None."""
    mac = re.sub(r"[:\-\s]", "", address or "").upper()
    if not _MAC_HEX.match(mac):
        return None

    try:
        if sys.platform == "win32":
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", _WINDOWS_SCRIPT.replace("__MAC__", mac)],
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=QUERY_TIMEOUT,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            return parse_windows_output(output)

        if sys.platform.startswith("linux"):
            output = subprocess.check_output(
                ["bluetoothctl", "info", ":".join(mac[i:i + 2] for i in range(0, 12, 2))],
                text=True,
                timeout=QUERY_TIMEOUT,
            )
            return parse_bluetoothctl_output(output)
    except (subprocess.SubprocessError, OSError):
        return None

    return None
