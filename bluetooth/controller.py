"""Main Bluetooth Controller for Mi Buds."""

import socket
import threading
import time
from typing import Callable, Optional

from . import os_battery, sdp
from .connection import BluetoothConnection
from .discovery import BluetoothDevice, BluetoothDiscovery
from .profiles import DEFAULT_PROFILE, DeviceProfile
from .protocol import BudsProtocol
from .spp_session import SppSession
from .constants import RECONNECT_DELAY


# ─────────────────────────────────────────────────────────────────────────────
# Type Aliases
# ─────────────────────────────────────────────────────────────────────────────
StatusCallback = Callable[[str, str], None]
BatteryCallback = Callable[[int, int, int], None]
CheckBatteryCallback = Callable[[], None]
ConnectionEventCallback = Callable[[str], None]
DeviceCallback = Callable[[BluetoothDevice, DeviceProfile], None]
PacketLogCallback = Callable[[str, bytes], None]
AncCallback = Callable[[int], None]


# ─────────────────────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────────────────────
class BTController:
    """High-level controller for Mi Buds communication."""

    _STALE_CONNECTION_TIMEOUT = 12
    _OS_BATTERY_INTERVAL = 30
    _WATCH_INTERVAL = 15
    _BATTERY_UNKNOWN = 0xFF

    def __init__(
        self,
        status_callback: Optional[StatusCallback] = None,
        battery_callback: Optional[BatteryCallback] = None,
        check_battery_callback: Optional[CheckBatteryCallback] = None,
        connection_event_callback: Optional[ConnectionEventCallback] = None,
        device_callback: Optional[DeviceCallback] = None,
        packet_log_callback: Optional[PacketLogCallback] = None,
        anc_callback: Optional[AncCallback] = None,
        bd_addr: Optional[str] = None
    ):
        self._connection = BluetoothConnection()
        self._profile = DEFAULT_PROFILE
        self._protocol = BudsProtocol(self._profile)
        self._session: Optional[SppSession] = None
        self._bd_addr = bd_addr
        self._running = True
        self._connect_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._max_reconnect_attempts = 5
        self._reconnect_attempts = 0
        self._reconnect_paused = False
        self._last_failure = ""
        self._buds_present: Optional[bool] = None
        self._last_watch_at: Optional[float] = None
        self._last_os_battery_at: Optional[float] = None
        self._last_connection_event: Optional[str] = None
        
        # Callbacks
        self._status_callback = status_callback
        self._battery_callback = battery_callback
        self._check_battery_callback = check_battery_callback
        self._connection_event_callback = connection_event_callback
        self._device_callback = device_callback
        self._packet_log_callback = packet_log_callback
        self._anc_callback = anc_callback

    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        """Check if connected to device."""
        return self._connection.connected

    @property
    def profile(self) -> DeviceProfile:
        """Profile of the model this controller is talking to."""
        return self._profile
    
    # ─────────────────────────────────────────────────────────────────────────
    # Status Updates
    # ─────────────────────────────────────────────────────────────────────────
    def _update_status(self, text: str, color: str = "black") -> None:
        """Send status update to UI."""
        if self._status_callback:
            self._status_callback(text, color)
    
    def _trigger_battery_check(self) -> None:
        """Trigger battery check callback."""
        if self._check_battery_callback:
            self._check_battery_callback()
    
    def _notify_battery(self, left: int, right: int, case: int) -> None:
        """Notify UI of battery status."""
        if self._battery_callback:
            self._battery_callback(left, right, case)

    def _notify_connection_event(self, event: str) -> None:
        """Notify UI about connection event transitions."""
        if event == self._last_connection_event:
            return

        self._last_connection_event = event
        if self._connection_event_callback:
            self._connection_event_callback(event)

    def _reset_reconnect_state(self) -> None:
        with self._state_lock:
            self._reconnect_attempts = 0
            self._reconnect_paused = False

    def _record_reconnect_failure(self) -> tuple[int, bool]:
        with self._state_lock:
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                self._reconnect_paused = True
            return self._reconnect_attempts, self._reconnect_paused

    def _reconnect_failure_message(self, attempts: int) -> str:
        """Retry status that keeps the reason of the last failure."""
        reason = self._last_failure or "Reconnect failed"
        return f"{reason} ({attempts}/{self._max_reconnect_attempts}). Retrying in {RECONNECT_DELAY}s..."

    @property
    def _uses_spp(self) -> bool:
        return self._profile.transport == "spp_auth"

    def _needs_os_battery(self) -> bool:
        """The OS level stands in until the model's own protocol delivers the real one."""
        if not self._profile.verified:
            return True
        return self._uses_spp and not (self._session and self._session.authenticated)

    def _publish_os_battery(self) -> None:
        """Show the combined battery the OS reports while the model's protocol is unavailable.

        Every earbud reports a level through the standard HFP indicator. It is shown on
        both earbuds, case unknown.
        """
        if not self._needs_os_battery() or not self._bd_addr:
            return

        now = time.monotonic()
        if self._last_os_battery_at is not None and now - self._last_os_battery_at < self._OS_BATTERY_INTERVAL:
            return
        self._last_os_battery_at = now

        level = os_battery.read_battery(self._bd_addr)
        # The query takes seconds; the model's own protocol may have answered meanwhile.
        if level is not None and self._needs_os_battery():
            self._notify_battery(level, level, self._BATTERY_UNKNOWN)

    def _watch_for_buds(self) -> None:
        """While reconnecting is paused, resume it when Buds newly show up as connected."""
        now = time.monotonic()
        if self._last_watch_at is not None and now - self._last_watch_at < self._WATCH_INTERVAL:
            return
        self._last_watch_at = now

        present = BluetoothDiscovery.find_buds() is not None
        if present and self._buds_present is False:
            self._reset_reconnect_state()
        self._buds_present = present

    def resume_reconnect_attempts(self) -> None:
        """Allow reconnect attempts again after user interaction."""
        self._reset_reconnect_state()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        """Connect to the Mi Buds device."""
        with self._connect_lock:
            if self._connection.connected:
                return True

            # Discover device if address not set
            if not self._bd_addr:
                found = BluetoothDiscovery.find_buds()
                self._buds_present = bool(found)
                if not found:
                    self._last_failure = "No connected Redmi/Xiaomi Buds found"
                    self._update_status(
                        f"{self._last_failure}. Retrying in {RECONNECT_DELAY}s...",
                        "red"
                    )
                    return False
                device, self._profile = found
                self._protocol = BudsProtocol(self._profile)
                self._bd_addr = device.address
                self._update_status(f"{device.name} found: {self._bd_addr}", "blue")
                if self._device_callback:
                    self._device_callback(device, self._profile)

            # Establish connection
            try:
                self._connect_on_any_channel()
                self._last_failure = ""
                self._update_status("Connected", "blue")
                self._reset_reconnect_state()
                self._notify_connection_event("connected")
                self.on_connect_setup()
                return True
            except Exception as e:
                self._connection.connected = False
                self._last_failure = f"Connection failed: {e}"
                self._update_status(self._last_failure, "red")
                return False
    
    def _candidate_channels(self) -> list[int]:
        """Channels to try: the one the OS cached for the control service, then the profile's."""
        channels: list[int] = []
        if self._profile.service_uuid:
            channels += sdp.find_rfcomm_channels(self._bd_addr, self._profile.service_uuid)
        fallback = self._profile.fallback_ports or (self._profile.rfcomm_port,)
        channels += [port for port in fallback if port not in channels]
        return channels

    def _connect_on_any_channel(self) -> None:
        last_error: Optional[Exception] = None
        for channel in self._candidate_channels():
            try:
                self._connection.connect(self._bd_addr, channel)
                return
            except Exception as e:
                last_error = e
        raise last_error

    # ─────────────────────────────────────────────────────────────────────────
    # Commands
    # ─────────────────────────────────────────────────────────────────────────
    def send_command(self, mode: str = "low") -> tuple[bool, str]:
        """Send latency mode command.
        
        Args:
            mode: "low" for low latency, "std" for standard
            
        Returns:
            (success, message) tuple
        """
        if not self._profile.supports_low_latency:
            return False, "Low latency mode is not available for this model yet."

        if not self._ensure_connected():
            return False, "Could not connect to device."

        try:
            payload = self._protocol.build_mode_command(mode)
            self._send(payload)
            mode_name = self._protocol.get_mode_name(mode)
            return True, f"{mode_name} mode sent."
        except Exception as e:
            self._connection.connected = False
            return False, f"Send error: {e}"
    
    def set_anc_mode(self, mode: int) -> tuple[bool, str]:
        """Switch noise control: 0 off, 1 noise cancelling, 2 transparency."""
        if not self._profile.supports_anc:
            return False, "Noise control is not available for this model."

        if not self._ensure_connected():
            return False, "Could not connect to device."

        if not (self._session and self._session.authenticated):
            return False, "Waiting for the earbuds to authenticate."

        try:
            for frame in self._session.set_anc(mode):
                self._send(frame)
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            self._connection.connected = False
            return False, f"Send error: {e}"
        return True, "Noise control command sent."

    def request_battery(self, user_initiated: bool = True) -> tuple[bool, str]:
        """Request battery status from device."""
        # User-invoked battery refresh should reopen reconnect attempts.
        if user_initiated:
            self.resume_reconnect_attempts()

        if not self._ensure_connected():
            return False, "Could not connect to device."

        if self._uses_spp and not (self._session and self._session.authenticated):
            return False, "Waiting for the earbuds to authenticate."

        try:
            if self._uses_spp:
                for frame in self._session.request_info():
                    self._send(frame)
            else:
                self._send(self._protocol.build_battery_request())
            return True, "Battery request sent."
        except Exception as e:
            self._connection.connected = False
            return False, f"Request error: {e}"
    
    def send_raw(self, data: bytes) -> tuple[bool, str]:
        """Send raw bytes to device.
        
        Args:
            data: Raw bytes to send
            
        Returns:
            (success, message) tuple
        """
        if not self._ensure_connected():
            return False, "Could not connect to device."
        
        try:
            self._send(data)
            return True, f"Raw data sent: {data.hex()}"
        except Exception as e:
            self._connection.connected = False
            return False, f"Send error: {e}"

    def _send(self, data: bytes) -> None:
        """Send bytes and mirror them to the packet log."""
        self._connection.send(data)
        self._log_packet("tx", data)

    def _log_packet(self, direction: str, data: bytes) -> None:
        if self._packet_log_callback:
            self._packet_log_callback(direction, data)

    def _ensure_connected(self) -> bool:
        """Ensure connected, attempting to connect if not."""
        return self._connection.connected or self.connect()

    def reconnect(self, force_rediscovery: bool = False) -> bool:
        """Reconnect to the device, optionally forcing MAC rediscovery."""
        self._connection.disconnect()
        if force_rediscovery:
            self._bd_addr = None
        self._notify_connection_event("reconnecting")
        return self.connect()
    
    def on_connect_setup(self):
        """Start the model's session on connection: authenticate, or send setup packets."""
        if self._uses_spp:
            self._session = SppSession()
            for frame in self._session.start():
                self.send_raw(frame)
            return

        for packet_hex in self._profile.setup_packets:
            self.send_raw(bytes.fromhex(packet_hex))
            time.sleep(0.1)
        time.sleep(1)
        self.request_battery(user_initiated=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Listener
    # ─────────────────────────────────────────────────────────────────────────
    def listen(self) -> None:
        """Main listener loop for incoming data."""
        last_packet_size = 0
        last_data_received_at = time.monotonic()
        disconnected_since: Optional[float] = None
        
        while self._running:
            if not self._connection.connected:
                with self._state_lock:
                    reconnect_paused = self._reconnect_paused

                if reconnect_paused:
                    self._publish_os_battery()
                    self._watch_for_buds()
                    time.sleep(RECONNECT_DELAY)
                    continue

                if disconnected_since is None:
                    disconnected_since = time.monotonic()

                force_rediscovery = (
                    time.monotonic() - disconnected_since >= self._STALE_CONNECTION_TIMEOUT
                )
                if force_rediscovery:
                    self._update_status("Connection stale. Full reconnect...", "orange")

                if not self.reconnect(force_rediscovery=force_rediscovery):
                    attempts, reached_limit = self._record_reconnect_failure()
                    if reached_limit:
                        self._update_status("Could not connect. Press Refresh Battery.", "red")
                        self._notify_connection_event("reconnect_failed_limit")
                    else:
                        self._update_status(self._reconnect_failure_message(attempts), "orange")
                    self._publish_os_battery()
                    time.sleep(RECONNECT_DELAY)
                else:
                    disconnected_since = None
                    last_data_received_at = time.monotonic()
                continue
            
            try:
                last_packet_size = self._process_data(last_packet_size)
                last_data_received_at = time.monotonic()
                disconnected_since = None
            except socket.timeout:
                # Keep idle connections without forcing periodic battery probes.
                # Reconnect is handled only on explicit send/receive failures.
                self._publish_os_battery()
                continue
            except Exception:
                self._handle_disconnect()
    
    def _process_data(self, last_packet_size: int) -> int:
        """Process incoming data packet."""
        data = self._connection.receive()
        if not data:
            raise ConnectionError("Received zero bytes from RFCOMM socket")

        packet_size = len(data)
        self._log_packet("rx", data)
        print(f"Received data size: {packet_size}")

        if self._uses_spp:
            self._handle_spp(data)
            return packet_size

        # Check for battery data
        if self._protocol.is_battery_packet(data):
            status = self._protocol.parse_battery(data)
            if status:
                self._notify_battery(status.left, status.right, status.case)
        
        # Check for mode acknowledgment
        elif self._protocol.is_mode_ack_packet(packet_size):
            if last_packet_size != packet_size:
                self._trigger_battery_check()
        
        return packet_size
    
    def _handle_spp(self, data: bytes) -> None:
        """Feed received bytes to the authenticated session and act on what it learned."""
        if not self._session:
            return

        update = self._session.handle(data)
        for frame in update.frames:
            self._send(frame)
        if update.auth_failed:
            self._update_status("Could not authenticate with the earbuds.", "red")
        if update.battery:
            self._notify_battery(*update.battery)
        if update.anc_mode is not None and self._anc_callback:
            self._anc_callback(update.anc_mode)

    def _handle_disconnect(self) -> None:
        """Handle connection loss."""
        self._connection.connected = False
        self._update_status("Connection lost", "red")
        self._notify_connection_event("disconnected")
        time.sleep(2)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    def stop(self) -> None:
        """Stop the controller."""
        self._running = False
        self._connection.disconnect()
