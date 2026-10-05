import pytest

from bluetooth import controller as controller_module
from bluetooth.controller import BTController
from bluetooth.discovery import BluetoothDevice, BluetoothDiscovery
from bluetooth.profiles import PROFILE_REDMI_BUDS_5_PRO, PROFILE_REDMI_BUDS_6_PLAY, PROFILE_XIAOMI_FAMILY
from bluetooth.spp_frame import OP_AUTH_CHALLENGE, OP_GET_DEVICE_INFO, TYPE_PHONE_REQUEST, parse_stream

BATTERY_PACKET = b"\xfe\xdc\xba\xc4" + bytes.fromhex("02020407") + bytes([80, 90, 100]) + b"\xef"


class FakeConnection:
    def __init__(self, to_receive=(), fail_connect=False, fail_ports=()):
        self.connected = False
        self.to_receive = list(to_receive)
        self.fail_connect = fail_connect
        self.fail_ports = set(fail_ports)
        self.attempted_ports: list[int] = []
        self.sent: list[bytes] = []
        self.connected_to = None

    def connect(self, address, port):
        self.attempted_ports.append(port)
        if self.fail_connect or port in self.fail_ports:
            raise OSError("host is down")
        self.connected_to = (address, port)
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send(self, data):
        if not self.connected:
            raise ConnectionError("not connected")
        self.sent.append(data)

    def receive(self):
        return self.to_receive.pop(0) if self.to_receive else b""


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(controller_module.time, "sleep", lambda _s: None)


def make(connection, **kwargs):
    controller = BTController(**kwargs)
    controller._connection = connection
    return controller


def test_battery_packet_notifies_the_callback():
    seen = []
    controller = make(FakeConnection([BATTERY_PACKET]), battery_callback=lambda *a: seen.append(a))
    controller._process_data(0)
    assert seen == [(80, 90, 100)]


def test_mode_ack_asks_for_battery_only_when_the_packet_size_changes():
    checks = []
    controller = make(FakeConnection([b"\x00" * 14, b"\x00" * 14]), check_battery_callback=lambda: checks.append(1))
    size = controller._process_data(0)
    assert size == 14 and len(checks) == 1
    controller._process_data(size)
    assert len(checks) == 1


def test_zero_bytes_means_the_socket_closed():
    controller = make(FakeConnection([b""]))
    with pytest.raises(ConnectionError):
        controller._process_data(0)


def test_connect_with_a_known_address_uses_the_profile_port_and_sends_setup(monkeypatch):
    connection = FakeConnection()
    events = []
    controller = make(connection, bd_addr="AA:BB:CC:DD:EE:FF", connection_event_callback=events.append)
    assert controller.connect() is True
    assert connection.connected_to == ("AA:BB:CC:DD:EE:FF", PROFILE_XIAOMI_FAMILY.rfcomm_port)
    assert events == ["connected"]
    assert bytes.fromhex("fedcba04510003000301ef") in connection.sent
    assert bytes.fromhex("fedcbac40200050bffffffffef4f") in connection.sent


def test_connect_discovers_the_device_and_reports_its_profile(monkeypatch):
    device = BluetoothDevice("Redmi Buds 6 Play", "11:22:33:44:55:66")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_REDMI_BUDS_6_PLAY))
    )
    found = []
    connection = FakeConnection()
    controller = make(connection, device_callback=lambda d, p: found.append((d.name, p.key)))
    assert controller.connect() is True
    assert found == [("Redmi Buds 6 Play", "redmi_buds_6_play")]
    assert connection.connected_to == ("11:22:33:44:55:66", 6)


def test_connect_without_a_buds_device_reports_it_and_fails(monkeypatch):
    monkeypatch.setattr(BluetoothDiscovery, "find_buds", classmethod(lambda cls: None))
    statuses = []
    controller = make(FakeConnection(), status_callback=lambda t, c: statuses.append((t, c)))
    assert controller.connect() is False
    assert statuses and statuses[-1][1] == "red"


def test_failed_connection_reports_the_error():
    statuses = []
    controller = make(
        FakeConnection(fail_connect=True),
        bd_addr="AA:BB:CC:DD:EE:FF",
        status_callback=lambda t, c: statuses.append((t, c)),
    )
    assert controller.connect() is False
    assert "host is down" in statuses[-1][0]


def test_send_command_failure_marks_the_connection_as_lost():
    connection = FakeConnection()
    controller = make(connection, bd_addr="AA:BB:CC:DD:EE:FF")
    controller.connect()
    connection.connected = True
    connection.send = lambda data: (_ for _ in ()).throw(OSError("broken pipe"))
    ok, message = controller.send_command("low")
    assert ok is False and "broken pipe" in message
    assert connection.connected is False


def test_packet_log_sees_what_goes_out_and_what_comes_in():
    log = []
    connection = FakeConnection([BATTERY_PACKET])
    controller = make(connection, bd_addr="AA:BB:CC:DD:EE:FF", packet_log_callback=lambda d, b: log.append((d, b)))
    controller.connect()
    controller._process_data(0)
    assert ("tx", bytes.fromhex("fedcbac40200050bffffffffef4f")) in log
    assert ("rx", BATTERY_PACKET) in log


def test_retry_message_keeps_the_reason_when_no_buds_are_connected(monkeypatch):
    monkeypatch.setattr(BluetoothDiscovery, "find_buds", classmethod(lambda cls: None))
    controller = make(FakeConnection())
    controller.connect()
    message = controller._reconnect_failure_message(2)
    assert "No connected Redmi/Xiaomi Buds found" in message
    assert "(2/5)" in message


def test_retry_message_keeps_the_connection_error():
    controller = make(FakeConnection(fail_connect=True), bd_addr="AA:BB:CC:DD:EE:FF")
    controller.connect()
    assert "host is down" in controller._reconnect_failure_message(1)


def test_retry_message_without_a_known_reason_is_generic():
    controller = make(FakeConnection())
    assert controller._reconnect_failure_message(3).startswith("Reconnect failed (3/5)")


def test_a_successful_connection_clears_the_failure_reason():
    connection = FakeConnection(fail_connect=True)
    controller = make(connection, bd_addr="AA:BB:CC:DD:EE:FF")
    controller.connect()
    connection.fail_connect = False
    controller.connect()
    assert controller._reconnect_failure_message(1).startswith("Reconnect failed (1/5)")


def unverified_controller(monkeypatch, level=60, **kwargs):
    device = BluetoothDevice("Redmi Buds 5 Pro", "AA:BB:CC:DD:EE:01")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_XIAOMI_FAMILY))
    )
    monkeypatch.setattr(controller_module.os_battery, "read_battery", lambda address: level)
    return make(FakeConnection(fail_connect=True), **kwargs)


def test_unverified_model_publishes_the_combined_os_battery(monkeypatch):
    seen = []
    controller = unverified_controller(monkeypatch, battery_callback=lambda *a: seen.append(a))
    controller.connect()
    controller._publish_os_battery()
    assert seen == [(60, 60, 0xFF)]


def test_os_battery_is_not_asked_more_often_than_the_interval(monkeypatch):
    seen = []
    controller = unverified_controller(monkeypatch, battery_callback=lambda *a: seen.append(a))
    controller.connect()
    controller._publish_os_battery()
    controller._publish_os_battery()
    assert len(seen) == 1


def test_verified_model_never_uses_the_os_battery(monkeypatch):
    device = BluetoothDevice("Redmi Buds 6 Play", "11:22:33:44:55:66")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_REDMI_BUDS_6_PLAY))
    )
    monkeypatch.setattr(
        controller_module.os_battery, "read_battery", lambda address: pytest.fail("must not be called")
    )
    seen = []
    controller = make(FakeConnection(), battery_callback=lambda *a: seen.append(a))
    controller.connect()
    controller._publish_os_battery()
    assert seen == []


def test_os_battery_without_a_value_publishes_nothing(monkeypatch):
    seen = []
    controller = unverified_controller(monkeypatch, level=None, battery_callback=lambda *a: seen.append(a))
    controller.connect()
    controller._publish_os_battery()
    assert seen == []


def test_paused_controller_resumes_when_the_buds_show_up_again(monkeypatch):
    controller = make(FakeConnection())
    for _ in range(5):
        controller._record_reconnect_failure()
    assert controller._reconnect_paused

    monkeypatch.setattr(BluetoothDiscovery, "find_buds", classmethod(lambda cls: None))
    controller._watch_for_buds()
    assert controller._reconnect_paused

    device = BluetoothDevice("Redmi Buds 5 Pro", "AA:BB:CC:DD:EE:01")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_XIAOMI_FAMILY))
    )
    controller._last_watch_at = None
    controller._watch_for_buds()
    assert not controller._reconnect_paused


def test_paused_controller_does_not_keep_resuming_while_the_buds_stay_connected(monkeypatch):
    device = BluetoothDevice("Redmi Buds 5 Pro", "AA:BB:CC:DD:EE:01")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_XIAOMI_FAMILY))
    )
    controller = make(FakeConnection())
    controller._buds_present = True
    for _ in range(5):
        controller._record_reconnect_failure()
    controller._watch_for_buds()
    assert controller._reconnect_paused


BUDS_CONFIRM_OK = bytes.fromhex("fedcbac0510003010100ef")
BUDS_CONFIRM_REJECTED = bytes.fromhex("fedcbac0510003010101ef")
DEVICE_INFO_RESPONSE = bytes.fromhex(
    "fedcba04020038000211005265646d69204275647320352050726f05014391439102025505032717506d02040102"
    "0500030643910208010407553cff020d02ef"
)


def buds_5_pro_controller(monkeypatch, connection=None, channels=(24,), **kwargs):
    device = BluetoothDevice("Redmi Buds 5 Pro", "AA:BB:CC:DD:EE:01")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_REDMI_BUDS_5_PRO))
    )
    monkeypatch.setattr(controller_module.sdp, "find_rfcomm_channels", lambda address, uuid: list(channels))
    connection = connection or FakeConnection()
    return make(connection, **kwargs), connection


def sent_messages(connection):
    return [m for raw in connection.sent for m in parse_stream(raw)]


def test_buds_5_pro_connects_on_the_channel_found_in_the_sdp_records(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch, channels=(24,))
    assert controller.connect() is True
    assert connection.connected_to == ("AA:BB:CC:DD:EE:01", 24)


def test_buds_5_pro_starts_authentication_instead_of_sending_legacy_packets(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch)
    controller.connect()
    messages = sent_messages(connection)
    assert [(m.msg_type, m.opcode) for m in messages] == [(TYPE_PHONE_REQUEST, OP_AUTH_CHALLENGE)]
    assert bytes.fromhex("fedcba04510003000301ef") not in connection.sent


def test_falls_back_to_the_profile_channels_when_the_os_has_no_records(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch, channels=())
    controller.connect()
    assert connection.connected_to[1] == 24


def test_tries_the_next_channel_when_the_first_one_fails(monkeypatch):
    connection = FakeConnection(fail_ports={30})
    controller, connection = buds_5_pro_controller(monkeypatch, connection, channels=(30, 24))
    assert controller.connect() is True
    assert connection.attempted_ports == [30, 24]
    assert connection.connected_to[1] == 24


def test_reports_the_error_when_no_channel_connects(monkeypatch):
    statuses = []
    controller, _ = buds_5_pro_controller(
        monkeypatch, FakeConnection(fail_connect=True), status_callback=lambda t, c: statuses.append(t)
    )
    assert controller.connect() is False
    assert "host is down" in statuses[-1]


def test_battery_from_the_device_info_reaches_the_ui_with_each_earbud_apart(monkeypatch):
    seen = []
    controller, connection = buds_5_pro_controller(monkeypatch, battery_callback=lambda *a: seen.append(a))
    controller.connect()
    connection.to_receive = [BUDS_CONFIRM_OK, DEVICE_INFO_RESPONSE]
    controller._process_data(0)
    controller._process_data(0)

    assert seen == [(0x55, 0x3C, 0xFF)]
    assert any(m.opcode == OP_GET_DEVICE_INFO for m in sent_messages(connection))


def test_rejected_authentication_is_shown_and_no_battery_is_requested(monkeypatch):
    statuses = []
    controller, connection = buds_5_pro_controller(monkeypatch, status_callback=lambda t, c: statuses.append((t, c)))
    controller.connect()
    connection.to_receive = [BUDS_CONFIRM_REJECTED]
    controller._process_data(0)
    assert statuses[-1][1] == "red" and "authenticate" in statuses[-1][0].lower()


def test_battery_request_waits_for_authentication(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch)
    controller.connect()
    before = len(connection.sent)
    ok, message = controller.request_battery()
    assert ok is False and "authenticat" in message.lower()
    assert len(connection.sent) == before

    connection.to_receive = [BUDS_CONFIRM_OK]
    controller._process_data(0)
    before = len(connection.sent)
    assert controller.request_battery()[0] is True
    assert len(connection.sent) == before + 1


def test_low_latency_is_refused_on_a_model_without_it(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch)
    controller.connect()
    sent = len(connection.sent)
    ok, message = controller.send_command("low")
    assert ok is False and "not available" in message
    assert len(connection.sent) == sent


def test_os_battery_is_used_only_until_the_5_pro_authenticates(monkeypatch):
    seen = []
    monkeypatch.setattr(controller_module.os_battery, "read_battery", lambda address: 42)
    controller, connection = buds_5_pro_controller(monkeypatch, battery_callback=lambda *a: seen.append(a))
    controller.connect()
    controller._publish_os_battery()
    assert seen == [(42, 42, 0xFF)]

    connection.to_receive = [BUDS_CONFIRM_OK]
    controller._process_data(0)
    controller._last_os_battery_at = None
    controller._publish_os_battery()
    assert seen == [(42, 42, 0xFF)]


RUN_INFO_RESPONSE = bytes.fromhex(
    "fedcba0409002800030700aabbccddee010701aabbccddee0103020400020301020400020600020902020a00020b00ef"
)
NOISE_NOTIFICATION = bytes.fromhex("fedcbac7f400060704000b0201ef")  # config 0x0b: transparency, strength 1


def authenticated_5_pro(monkeypatch, **kwargs):
    controller, connection = buds_5_pro_controller(monkeypatch, **kwargs)
    controller.connect()
    connection.to_receive = [BUDS_CONFIRM_OK]
    controller._process_data(0)
    connection.sent.clear()
    return controller, connection


def test_current_noise_mode_reaches_the_ui_from_the_run_info(monkeypatch):
    seen = []
    controller, connection = authenticated_5_pro(monkeypatch, anc_callback=seen.append)
    connection.to_receive = [RUN_INFO_RESPONSE]
    controller._process_data(0)
    assert seen == [2]


def test_noise_mode_changed_from_the_earbuds_reaches_the_ui(monkeypatch):
    seen = []
    controller, connection = authenticated_5_pro(monkeypatch, anc_callback=seen.append)
    connection.to_receive = [NOISE_NOTIFICATION]
    controller._process_data(0)
    assert seen == [2]


def test_setting_the_noise_mode_sends_the_command(monkeypatch):
    controller, connection = authenticated_5_pro(monkeypatch)
    ok, _ = controller.set_anc_mode(1)
    assert ok is True
    sent = sent_messages(connection)
    assert [(m.opcode, m.payload) for m in sent] == [(0x08, b"\x02\x04\x01")]


def test_noise_mode_waits_for_authentication(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch)
    controller.connect()
    connection.sent.clear()
    ok, message = controller.set_anc_mode(1)
    assert ok is False and "authenticate" in message
    assert connection.sent == []


def test_models_without_noise_control_refuse_it(monkeypatch):
    device = BluetoothDevice("Redmi Buds 6 Play", "11:22:33:44:55:66")
    monkeypatch.setattr(
        BluetoothDiscovery, "find_buds", classmethod(lambda cls: (device, PROFILE_REDMI_BUDS_6_PLAY))
    )
    connection = FakeConnection()
    controller = make(connection)
    controller.connect()
    connection.sent.clear()
    ok, message = controller.set_anc_mode(1)
    assert ok is False and "not available" in message
    assert connection.sent == []


def test_unknown_noise_mode_is_refused_without_sending(monkeypatch):
    controller, connection = authenticated_5_pro(monkeypatch)
    ok, message = controller.set_anc_mode(7)
    assert ok is False and "Unknown" in message
    assert connection.sent == []


def test_a_failed_send_marks_the_connection_as_lost(monkeypatch):
    controller, connection = authenticated_5_pro(monkeypatch)
    connection.send = lambda data: (_ for _ in ()).throw(OSError("broken pipe"))
    ok, message = controller.set_anc_mode(0)
    assert ok is False and "broken pipe" in message
    assert connection.connected is False


def test_a_slow_os_query_does_not_overwrite_the_real_battery(monkeypatch):
    seen = []
    controller, connection = buds_5_pro_controller(monkeypatch, battery_callback=lambda *a: seen.append(a))
    controller.connect()

    def slow_read(address):
        # While Windows answers (about 2 s), the earbuds authenticate and report their real levels.
        connection.to_receive = [BUDS_CONFIRM_OK, DEVICE_INFO_RESPONSE]
        controller._process_data(0)
        controller._process_data(0)
        return 60

    monkeypatch.setattr(controller_module.os_battery, "read_battery", slow_read)
    controller._publish_os_battery()
    assert seen == [(0x55, 0x3C, 0xFF)]


def test_a_new_connection_starts_a_fresh_session(monkeypatch):
    controller, connection = buds_5_pro_controller(monkeypatch)
    controller.connect()
    connection.to_receive = [BUDS_CONFIRM_OK]
    controller._process_data(0)
    assert controller._session.authenticated

    connection.connected = False
    controller.connect()
    assert not controller._session.authenticated


def test_reconnect_gives_up_after_the_attempt_limit():
    controller = make(FakeConnection())
    for _ in range(4):
        _, paused = controller._record_reconnect_failure()
        assert paused is False
    _, paused = controller._record_reconnect_failure()
    assert paused is True
    controller.resume_reconnect_attempts()
    assert controller._reconnect_paused is False
