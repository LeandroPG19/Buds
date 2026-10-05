"""Packet capture for earbud models whose protocol has not been verified."""

import re
import threading
from datetime import datetime
from pathlib import Path

from .user_preferences import app_data_dir

DEFAULT_MAX_BYTES = 256 * 1024


def packet_log_path(device_name: str) -> Path:
    """Return the per-device capture file, e.g. packets-redmi-buds-5-pro.log."""
    slug = re.sub(r"[^a-z0-9]+", "-", device_name.lower()).strip("-") or "device"
    return Path(app_data_dir()) / f"packets-{slug}.log"


class PacketLog:
    """Append-only hex log of what is sent to and received from the earbuds.

    Rotates to `<file>.1` past `max_bytes` so it never grows unbounded.
    Logging must never break the connection, so every failure is swallowed.
    """

    def __init__(self, path: Path, max_bytes: int = DEFAULT_MAX_BYTES):
        self._path = Path(path)
        self._max_bytes = max_bytes
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def write(self, direction: str, data: bytes) -> None:
        line = f"{datetime.now().isoformat(timespec='milliseconds')} {direction} {data.hex()}\n"
        with self._lock:
            try:
                if self._path.exists() and self._path.stat().st_size >= self._max_bytes:
                    self._path.replace(self._path.with_name(self._path.name + ".1"))
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass
