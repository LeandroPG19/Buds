from bluetooth import sdp

XIAOMI_UUID = "0000fd2d-0000-1000-8000-00805f9b34fb"
FASTPAIR_UUID = "df21fe2c-2515-4fdb-8886-f12c4d67927c"

# SDP records as cached by Windows for a real Redmi Buds 5 Pro. XIAOAI_RECORD is byte-exact;
# the other two keep the real header and RFCOMM channel but have a simplified tail.
XIAOAI_RECORD = bytes.fromhex(
    "353a0900000a2000000509000135111c0000fd2d00001000800000805f9b34fb090004350c3503190100350519"
    "000308180901002506786961 6f6169".replace(" ", "")
)
FASTPAIR_RECORD = bytes.fromhex(
    "35540900000a2000000409000135111cdf21fe2c25154fdb8886f12c4d67927c090004350c3503190100350519"
    "0003081709000935083506190ee0090102090100250a42544641535450414952"
)
HANDSFREE_RECORD = bytes.fromhex(
    "35620900000a00010000090001350619111e191203090004350c3503190100350519000308010900053503191002"
)


def test_channel_of_the_service_with_the_requested_uuid():
    records = [HANDSFREE_RECORD, FASTPAIR_RECORD, XIAOAI_RECORD]
    assert sdp.channels_for_uuid(records, XIAOMI_UUID) == [24]
    assert sdp.channels_for_uuid(records, FASTPAIR_UUID) == [23]


def test_unknown_uuid_gives_no_channel():
    assert sdp.channels_for_uuid([XIAOAI_RECORD], "12345678-0000-1000-8000-00805f9b34fb") == []


def test_record_without_an_rfcomm_channel_gives_nothing():
    no_channel = bytes.fromhex("353a0900000a2000000509000135111c0000fd2d00001000800000805f9b34fb")
    assert sdp.channels_for_uuid([no_channel], XIAOMI_UUID) == []


def test_malformed_uuid_is_rejected():
    assert sdp.channels_for_uuid([XIAOAI_RECORD], "not-a-uuid") == []


def test_duplicate_records_do_not_repeat_the_channel():
    assert sdp.channels_for_uuid([XIAOAI_RECORD, XIAOAI_RECORD], XIAOMI_UUID) == [24]


def test_lookup_is_empty_off_windows_or_for_a_bad_address(monkeypatch):
    monkeypatch.setattr(sdp.sys, "platform", "linux")
    assert sdp.find_rfcomm_channels("AA:BB:CC:DD:EE:01", XIAOMI_UUID) == []
    monkeypatch.setattr(sdp.sys, "platform", "win32")
    assert sdp.find_rfcomm_channels("not a mac", XIAOMI_UUID) == []


def test_windows_lookup_reads_the_cached_records(monkeypatch):
    monkeypatch.setattr(sdp.sys, "platform", "win32")
    seen = {}

    def fake_read(mac_hex):
        seen["mac"] = mac_hex
        return [XIAOAI_RECORD]

    monkeypatch.setattr(sdp, "_read_cached_records_windows", fake_read)
    assert sdp.find_rfcomm_channels("AA:BB:CC:DD:EE:01", XIAOMI_UUID) == [24]
    assert seen["mac"] == "aabbccddee01"
