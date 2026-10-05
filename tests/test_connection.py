import pytest

from bluetooth import connection as connection_module
from bluetooth.connection import BluetoothConnection


class FakeSocket:
    instances: list["FakeSocket"] = []
    fail_connect = False

    def __init__(self, *args):
        self.closed = False
        self.sent: list[bytes] = []
        self.connected_to = None
        FakeSocket.instances.append(self)

    def settimeout(self, value):
        self.timeout = value

    def connect(self, target):
        if FakeSocket.fail_connect:
            raise OSError("host is down")
        self.connected_to = target

    def send(self, data):
        self.sent.append(data)

    def recv(self, size):
        return b"\x01"

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_socket(monkeypatch):
    FakeSocket.instances = []
    FakeSocket.fail_connect = False
    monkeypatch.setattr(connection_module.socket, "socket", FakeSocket)
    monkeypatch.setattr(connection_module.socket, "AF_BLUETOOTH", 32, raising=False)
    monkeypatch.setattr(connection_module.socket, "BTPROTO_RFCOMM", 3, raising=False)


def test_connect_uses_the_given_port():
    conn = BluetoothConnection()
    conn.connect("AA:BB:CC:DD:EE:FF", 6)
    assert conn.connected
    assert FakeSocket.instances[0].connected_to == ("AA:BB:CC:DD:EE:FF", 6)


def test_failed_connect_closes_the_socket_and_stays_disconnected():
    FakeSocket.fail_connect = True
    conn = BluetoothConnection()
    with pytest.raises(OSError):
        conn.connect("AA:BB:CC:DD:EE:FF", 6)
    assert not conn.connected
    assert FakeSocket.instances[0].closed


def test_send_without_a_socket_raises_instead_of_pretending_it_was_sent():
    conn = BluetoothConnection()
    with pytest.raises(ConnectionError):
        conn.send(b"\x01")


def test_send_after_disconnect_raises():
    conn = BluetoothConnection()
    conn.connect("AA:BB:CC:DD:EE:FF", 6)
    conn.disconnect()
    with pytest.raises(ConnectionError):
        conn.send(b"\x01")


def test_receive_without_a_socket_returns_empty():
    assert BluetoothConnection().receive() == b""
