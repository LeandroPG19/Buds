"""Bluetooth device discovery (Windows and Linux)."""

import subprocess
import json
import sys
from dataclasses import dataclass
from typing import Optional

from .profiles import PROFILES, DeviceProfile

# The PowerShell script took 4.5 s on a healthy PC (it queries WMI per device).
DISCOVERY_TIMEOUT = 15


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BluetoothDevice:
    """Represents a connected Bluetooth device."""
    name: str
    address: str


# ─────────────────────────────────────────────────────────────────────────────
# Discovery Script
# ─────────────────────────────────────────────────────────────────────────────
POWERSHELL_DISCOVERY_SCRIPT = r"""
$bt = Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' }
$results = foreach ($d in $bt) {
    $isConn = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_IsConnected' -ErrorAction SilentlyContinue).Data
    if ($isConn -eq $true) {
        $addr = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Bluetooth_DeviceAddress' -ErrorAction SilentlyContinue).Data
        if ($addr -is [byte[]]) {
            $addrStr = ($addr | ForEach-Object { $_.ToString('X2') }) -join ':'
        } else {
            $addrStr = [string]$addr
        }
        [pscustomobject]@{ Name=$d.FriendlyName; Address=$addrStr }
    }
}
if ($results) { $results | ConvertTo-Json -Compress }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Discovery Class
# ─────────────────────────────────────────────────────────────────────────────
class BluetoothDiscovery:
    """Handles Bluetooth device discovery."""
    
    @staticmethod
    def is_supported() -> bool:
        """Check if discovery is supported on current platform."""
        return sys.platform in ["win32", "linux"]
    
    @classmethod
    def list_connected_devices(cls) -> list[BluetoothDevice]:
        """Return every connected Bluetooth device the OS reports."""
        if not cls.is_supported():
            return []

        try:
            if sys.platform == "win32":
                return cls._parse_devices_win(cls._run_discovery_script_win())
            return cls._list_connected_devices_linux()
        except Exception:
            return []

    @staticmethod
    def select_device(
        devices: list[BluetoothDevice],
    ) -> Optional[tuple[BluetoothDevice, DeviceProfile]]:
        """Pick the connected device that matches a Buds profile.

        Specific profiles win over the family one, so a verified model is chosen
        before an unverified one when several earbuds are connected.
        """
        for profile in PROFILES:
            for device in devices:
                if profile.matches(device.name):
                    return device, profile
        return None

    @classmethod
    def find_buds(cls) -> Optional[tuple[BluetoothDevice, DeviceProfile]]:
        """Return the connected Buds and its profile, or None."""
        return cls.select_device(cls.list_connected_devices())
    
    @staticmethod
    def _run_discovery_script_win() -> str:
        """Execute PowerShell discovery script."""
        # This flag prevents a console window from appearing on Windows.
        creation_flags = 0x08000000  # subprocess.CREATE_NO_WINDOW
        
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", POWERSHELL_DISCOVERY_SCRIPT],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=DISCOVERY_TIMEOUT,
            creationflags=creation_flags
        ).strip()
    
    @classmethod
    def _parse_devices_win(cls, output: str) -> list[BluetoothDevice]:
        """Parse PowerShell JSON output; entries without an address are skipped."""
        if not output:
            return []

        try:
            data = json.loads(output)
        except ValueError:
            return []

        items = data if isinstance(data, list) else [data]
        return [
            BluetoothDevice(name=item.get("Name", ""), address=cls._format_mac(item["Address"]))
            for item in items
            if isinstance(item, dict) and item.get("Address")
        ]

    @classmethod
    def _list_connected_devices_linux(cls) -> list[BluetoothDevice]:
        """List connected Bluetooth devices using bluetoothctl on Linux."""
        connected: list[BluetoothDevice] = []
        try:
            devices_output = subprocess.check_output(["bluetoothctl", "devices"], text=True)
            for line in devices_output.splitlines():
                # Format: Device XX:XX:XX:XX:XX:XX Name
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    continue

                mac, name = parts[1], parts[2]
                info_output = subprocess.check_output(["bluetoothctl", "info", mac], text=True)
                if "Connected: yes" in info_output:
                    connected.append(BluetoothDevice(name=name, address=cls._format_mac(mac)))
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return connected
    
    @staticmethod
    def _format_mac(addr: str) -> str:
        """Format MAC address to standard format (XX:XX:XX:XX:XX:XX)."""
        if not addr:
            return addr
        cleaned = addr.replace(":", "").replace("-", "").replace(" ", "").upper()
        if len(cleaned) == 12:
            return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
        return addr
