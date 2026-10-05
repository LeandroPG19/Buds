import pytest

from bluetooth.spp_frame import (
    OP_ANC,
    OP_AUTH_CHALLENGE,
    OP_AUTH_CONFIRM,
    OP_GET_DEVICE_INFO,
    OP_GET_DEVICE_RUN_INFO,
    OP_NOTIFY_CONFIG,
    OP_REPORT_STATUS,
    TYPE_EARBUDS_NOTIFY,
    TYPE_EARBUDS_REQUEST,
    TYPE_PHONE_REQUEST,
    TYPE_RESPONSE,
    Message,
    parse_stream,
)
from bluetooth.spp_session import SppSession

FIXED_CHALLENGE = bytes(range(16))

# Frames captured from a real Redmi Buds 5 Pro (2026-10-05).
BUDS_CHALLENGE_REQUEST = bytes.fromhex("fedcbac0500012000160c881a805416aeeaa3a1e079d879568ef")
BUDS_CONFIRM_OK = bytes.fromhex("fedcbac0510003010100ef")
BUDS_CONFIRM_REJECTED = bytes.fromhex("fedcbac0510003010101ef")
DEVICE_INFO_RESPONSE = bytes.fromhex(
    "fedcba04020038000211005265646d69204275647320352050726f05014391439102025505032717506d02040102"
    "0500030643910208010407553cff020d02ef"
)
NOTIFY_CONFIG = bytes.fromhex("fedcbac7f400050203000c00ef")


def make_session():
    return SppSession(challenge_factory=lambda: FIXED_CHALLENGE)


def frames(raw_list):
    return [m for raw in raw_list for m in parse_stream(raw)]


def test_start_sends_the_challenge_with_sequence_zero():
    first = frames(make_session().start())
    assert first == [Message(TYPE_PHONE_REQUEST, OP_AUTH_CHALLENGE, 0, b"\x01" + FIXED_CHALLENGE)]


def test_the_earbuds_answer_to_our_challenge_is_confirmed_with_sequence_one():
    session = make_session()
    session.start()
    reply = session.handle(Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, 0, b"\x01" + bytes(16)).encode())
    assert frames(reply.frames) == [Message(TYPE_PHONE_REQUEST, OP_AUTH_CONFIRM, 1, b"\x01\x00")]


def test_their_challenge_is_answered_with_the_cipher_and_their_sequence():
    session = make_session()
    reply = session.handle(BUDS_CHALLENGE_REQUEST)
    expected = bytes.fromhex("787748b987ecf34ab33464eaa78f44ba")  # accepted by the real earbuds
    assert frames(reply.frames) == [Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, 0, b"\x01" + expected)]


def test_accepted_authentication_acks_and_asks_for_device_info():
    session = make_session()
    session.start()
    session.handle(Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, 0, b"\x01" + bytes(16)).encode())
    reply = session.handle(BUDS_CONFIRM_OK)

    assert session.authenticated
    assert reply.authenticated_now and not reply.auth_failed
    assert frames(reply.frames) == [
        Message(TYPE_RESPONSE, OP_AUTH_CONFIRM, 1, b"\x01"),
        Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_INFO, 2, b"\xff\xff\xff\xff"),
        Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_RUN_INFO, 3, b"\xff\xff\xff\xff"),
    ]


def test_rejected_authentication_is_reported_and_nothing_is_requested():
    session = make_session()
    reply = session.handle(BUDS_CONFIRM_REJECTED)
    assert reply.auth_failed
    assert not session.authenticated
    assert not any(m.opcode == OP_GET_DEVICE_INFO for m in frames(reply.frames))


def test_device_info_gives_the_name_and_the_three_battery_levels():
    session = make_session()
    update = session.handle(DEVICE_INFO_RESPONSE)
    assert update.device_name == "Redmi Buds 5 Pro"
    assert update.battery == (0x55, 0x3C, 0xFF)  # left 85 %, right 60 %, case unknown


def test_config_notifications_are_acknowledged_with_their_sequence():
    reply = make_session().handle(NOTIFY_CONFIG)
    assert reply.frames == [bytes.fromhex("fedcba04f400020002ef")]


def test_status_report_updates_the_battery_and_is_acknowledged():
    status = Message(TYPE_EARBUDS_NOTIFY, OP_REPORT_STATUS, 5, bytes([0x04, 0x00, 0x50, 0xD0, 0xFF])).encode()
    update = make_session().handle(status)
    assert update.battery == (0x50, 0xD0, 0xFF)  # right earbud is charging (bit 7)
    assert frames(update.frames) == [Message(TYPE_RESPONSE, OP_REPORT_STATUS, 5, b"")]


def test_status_without_battery_does_not_report_one():
    status = Message(TYPE_EARBUDS_NOTIFY, OP_REPORT_STATUS, 6, bytes([0x02, 0x04, 0x01])).encode()
    assert make_session().handle(status).battery is None


def test_battery_request_needs_authentication_and_uses_a_fresh_sequence():
    session = make_session()
    assert session.request_info() == []

    session.start()
    session.handle(BUDS_CONFIRM_OK)
    first = frames(session.request_info())
    second = frames(session.request_info())
    assert [m.opcode for m in first] == [OP_GET_DEVICE_INFO]
    assert second[0].seq == first[0].seq + 1


RUN_INFO_RESPONSE = bytes.fromhex(
    "fedcba0409002800030700aabbccddee010701aabbccddee0103020400020301020400020600020902020a00020b00ef"
)


def test_run_info_gives_the_current_noise_mode():
    # The 5 Pro was in transparency (2) when this was captured.
    assert make_session().handle(RUN_INFO_RESPONSE).anc_mode == 2


def notify(seq, payload_hex):
    return Message(TYPE_EARBUDS_NOTIFY, OP_NOTIFY_CONFIG, seq, bytes.fromhex(payload_hex)).encode()


def test_noise_mode_changes_arrive_as_a_sound_control_notification_and_are_acked():
    session = make_session()
    # Captured after sending modes 1, 0 and 2: the config id is 0x0b, then mode and strength.
    for payload, expected in (("04000b0100", 1), ("04000b0000", 0), ("04000b0201", 2)):
        update = session.handle(notify(4, payload))
        assert update.anc_mode == expected
        assert frames(update.frames) == [Message(TYPE_RESPONSE, OP_NOTIFY_CONFIG, 4, b"")]


def test_other_config_notifications_do_not_change_the_noise_mode():
    update = make_session().handle(NOTIFY_CONFIG)  # wear detection, config 0x0c
    assert update.anc_mode is None


def test_status_report_flag_is_not_the_noise_mode():
    # REPORT_STATUS carries a constant 0 at id 4 whatever the mode is; it must not be read as one.
    status = Message(TYPE_EARBUDS_NOTIFY, OP_REPORT_STATUS, 3, bytes([0x02, 0x04, 0x00])).encode()
    assert make_session().handle(status).anc_mode is None


def test_set_noise_mode_builds_the_command_the_earbuds_acknowledged():
    session = make_session()
    assert session.set_anc(1) == []  # not authenticated yet

    session.handle(BUDS_CONFIRM_OK)
    sent = frames(session.set_anc(1))
    assert [(m.msg_type, m.opcode, m.payload) for m in sent] == [(TYPE_PHONE_REQUEST, OP_ANC, b"\x02\x04\x01")]


def test_set_noise_mode_uses_a_fresh_sequence_each_time():
    session = make_session()
    session.handle(BUDS_CONFIRM_OK)
    first = frames(session.set_anc(0))[0].seq
    second = frames(session.set_anc(2))[0].seq
    assert second == first + 1


def test_unknown_noise_mode_is_rejected():
    session = make_session()
    session.handle(BUDS_CONFIRM_OK)
    with pytest.raises(ValueError):
        session.set_anc(3)


def test_garbage_is_ignored():
    update = make_session().handle(b"\x00\x01\x02")
    assert update.frames == [] and update.battery is None and not update.auth_failed

