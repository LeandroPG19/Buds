from bluetooth.spp_frame import (
    OP_AUTH_CHALLENGE,
    OP_GET_DEVICE_INFO,
    OP_SET_CONFIG,
    TYPE_EARBUDS_NOTIFY,
    TYPE_EARBUDS_REQUEST,
    TYPE_PHONE_REQUEST,
    TYPE_RESPONSE,
    Message,
    parse_stream,
)


def test_encoder_reproduces_the_bytes_hardware_tested_on_the_6_play():
    # Low latency command and battery request of bluetooth/constants.py, as frames.
    assert Message(TYPE_PHONE_REQUEST, OP_SET_CONFIG, 0x90, bytes.fromhex("03002f01")).encode() == bytes.fromhex(
        "fedcbac4f200059003002f01ef"
    )
    assert Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_INFO, 0x0B, b"\xff\xff\xff\xff").encode() == bytes.fromhex(
        "fedcbac40200050bffffffffef"
    )


def test_request_roundtrip():
    original = Message(TYPE_PHONE_REQUEST, 0x08, 7, b"\x02\x04\x01")
    assert parse_stream(original.encode()) == [original]


def test_response_header_has_a_zero_pad_and_counts_it_in_the_length():
    frame = Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, 3, b"\x01").encode()
    assert frame == bytes.fromhex("fedcba0450" + "0003" + "00" + "03" + "01" + "ef")
    assert parse_stream(frame) == [Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, 3, b"\x01")]


def test_empty_payload_response_is_an_ack():
    ack = Message(TYPE_RESPONSE, 0x0E, 9)
    assert parse_stream(ack.encode()) == [ack]


def test_several_frames_in_one_chunk_are_all_returned():
    a = Message(TYPE_EARBUDS_NOTIFY, 0x0E, 1, b"\x05\x00\x50\x50\x50")
    b = Message(TYPE_EARBUDS_REQUEST, OP_AUTH_CHALLENGE, 2, b"\x01" + bytes(16))
    assert parse_stream(a.encode() + b.encode()) == [a, b]


def test_garbage_before_and_after_is_ignored():
    frame = Message(TYPE_PHONE_REQUEST, 0x02, 1, b"\xff").encode()
    assert parse_stream(b"\x00\x01" + frame + b"\x99") == [Message(TYPE_PHONE_REQUEST, 0x02, 1, b"\xff")]


def test_truncated_or_corrupt_frames_give_nothing():
    frame = Message(TYPE_PHONE_REQUEST, 0x02, 1, b"\xff\xff").encode()
    assert parse_stream(frame[:-1]) == []
    assert parse_stream(frame[:-1] + b"\x00") == []
    assert parse_stream(b"") == []
    assert parse_stream(b"\xfe\xdc") == []


def test_a_bad_length_does_not_hide_the_next_good_frame():
    good = Message(TYPE_PHONE_REQUEST, 0x02, 1, b"\xff")
    bad = bytearray(Message(TYPE_PHONE_REQUEST, 0x02, 1, b"\xff\xff").encode())
    bad[6] = 0x7F
    assert parse_stream(bytes(bad) + good.encode()) == [good]
