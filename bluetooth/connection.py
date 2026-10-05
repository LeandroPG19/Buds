"""Bluetooth socket connection handler."""

import socket
import threading
from typing import Optional

from .constants import SOCKET_TIMEOUT, RECV_BUFFER_SIZE


class BluetoothConnection:
    """Manages Bluetooth socket connection."""
    
    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
    
    @property
    def connected(self) -> bool:
        """Check if currently connected."""
        return self._connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection status."""
        self._connected = value
    
    def connect(self, address: str, port: int) -> None:
        """Establish connection to device.

        Args:
            address: Bluetooth MAC address
            port: RFCOMM channel of the device profile

        Raises:
            Exception: If connection fails; the socket is closed first
        """
        sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )
        try:
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((address, port))
        except Exception:
            sock.close()
            raise
        self._sock = sock
        self._connected = True
    
    def disconnect(self) -> None:
        """Close the connection."""
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
    
    def send(self, data: bytes) -> None:
        """Send data to device.
        
        Args:
            data: Bytes to send
            
        Raises:
            ConnectionError: If there is no open socket
            Exception: If send fails
        """
        with self._lock:
            if not self._sock:
                raise ConnectionError("Not connected")
            self._sock.send(data)
    
    def receive(self) -> bytes:
        """Receive data from device.
        
        Returns:
            Received bytes
            
        Raises:
            socket.timeout: If no data available
            Exception: If receive fails
        """
        if self._sock:
            return self._sock.recv(RECV_BUFFER_SIZE)
        return b""
