"""Control session with Xiaomi/Redmi Buds that authenticate the app (Redmi Buds 5 Pro and similar).

Pure state machine: it takes received bytes and returns the frames to send plus what was learned,
so the socket handling stays in the controller. Handshake validated on real Redmi Buds 5 Pro
hardware; the message flow follows Gadgetbridge's Redmi Buds support (AGPL-3.0).
"""

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import safer_plus
from .spp_frame import (
    OP_ANC,
    OP_AUTH_CHALLENGE,
    OP_AUTH_CONFIRM,
    OP_GET_DEVICE_INFO,
    OP_GET_DEVICE_RUN_INFO,
    OP_NOTIFY_CONFIG,
    OP_REPORT_STATUS,
    TYPE_PHONE_REQUEST,
    TYPE_RESPONSE,
    Message,
    parse_stream,
)

_QUERY_ALL = b"\xff\xff\xff\xff"
_AUTH_OK = b"\x01\x00"
_BATTERY_UNKNOWN = 0xFF

# TLV ids: GET_DEVICE_INFO carries the battery at 0x07, REPORT_STATUS at 0x00.
_TLV_NAME = 0x00
_TLV_INFO_BATTERY = 0x07
_TLV_STATUS_BATTERY = 0x00

# Noise control: GET_DEVICE_RUN_INFO has the current mode at id 0x09; changes are announced
# by NOTIFY_CONFIG entries [00][0x0b][mode][strength]. (REPORT_STATUS id 0x04 stays 0 whatever
# the mode, so it is not used.)
_TLV_RUN_INFO_ANC = 0x09
_CONFIG_SOUND_CONTROL = 0x0B

ANC_OFF = 0
ANC_NOISE_CANCELLING = 1
ANC_TRANSPARENCY = 2
ANC_MODES = (ANC_OFF, ANC_NOISE_CANCELLING, ANC_TRANSPARENCY)


@dataclass
class SppUpdate:
    frames: list[bytes] = field(default_factory=list)
    battery: Optional[tuple[int, int, int]] = None
    anc_mode: Optional[int] = None
    device_name: Optional[str] = None
    authenticated_now: bool = False
    auth_failed: bool = False


def _tlvs(payload: bytes) -> list[tuple[int, bytes]]:
    """Split [len][id][value...] entries; len counts the id byte and the value."""
    entries = []
    i = 0
    while i + 1 < len(payload):
        length = payload[i]
        if length == 0:
            break
        entries.append((payload[i + 1], payload[i + 2:i + 1 + length]))
        i += length + 1
    return entries


def _battery(value: bytes) -> Optional[tuple[int, int, int]]:
    """[left, right, case]; bit 7 means charging and 0xFF means unknown."""
    if len(value) < 3:
        return None
    left, right, case = value[0], value[1], value[2]
    if left == right == case == _BATTERY_UNKNOWN:
        return None
    return left, right, case


class SppSession:
    def __init__(self, challenge_factory: Callable[[], bytes] = lambda: os.urandom(16)):
        self._challenge_factory = challenge_factory
        self._seq = 0
        self.authenticated = False

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    def start(self) -> list[bytes]:
        challenge = self._challenge_factory()
        return [Message(TYPE_PHONE_REQUEST, OP_AUTH_CHALLENGE, self._next_seq(), b"\x01" + challenge).encode()]

    def request_info(self) -> list[bytes]:
        """Ask for device info (name and battery). Only meaningful once authenticated."""
        if not self.authenticated:
            return []
        return [Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_INFO, self._next_seq(), _QUERY_ALL).encode()]

    def set_anc(self, mode: int) -> list[bytes]:
        """Switch noise control (off, noise cancelling, transparency). Needs authentication."""
        if mode not in ANC_MODES:
            raise ValueError(f"Unknown noise control mode: {mode}")
        if not self.authenticated:
            return []
        return [Message(TYPE_PHONE_REQUEST, OP_ANC, self._next_seq(), bytes([0x02, 0x04, mode])).encode()]

    def handle(self, data: bytes) -> SppUpdate:
        update = SppUpdate()
        for message in parse_stream(data):
            self._handle_message(message, update)
        return update

    def _handle_message(self, m: Message, update: SppUpdate) -> None:
        if m.opcode == OP_AUTH_CHALLENGE:
            self._handle_challenge(m, update)
        elif m.opcode == OP_AUTH_CONFIRM and not m.is_response:
            self._handle_confirm(m, update)
        elif m.opcode in (OP_REPORT_STATUS, OP_NOTIFY_CONFIG) and not m.is_response:
            update.frames.append(Message(TYPE_RESPONSE, m.opcode, m.seq, b"").encode())
            if m.opcode == OP_REPORT_STATUS:
                for tlv_id, value in _tlvs(m.payload):
                    if tlv_id == _TLV_STATUS_BATTERY and (battery := _battery(value)):
                        update.battery = battery
            else:
                for tlv_id, value in _tlvs(m.payload):
                    if tlv_id == 0x00 and len(value) >= 2 and value[0] == _CONFIG_SOUND_CONTROL:
                        update.anc_mode = value[1]
        elif m.opcode == OP_GET_DEVICE_RUN_INFO and m.is_response:
            for tlv_id, value in _tlvs(m.payload):
                if tlv_id == _TLV_RUN_INFO_ANC and value:
                    update.anc_mode = value[0]
        elif m.opcode == OP_GET_DEVICE_INFO and m.is_response:
            for tlv_id, value in _tlvs(m.payload):
                if tlv_id == _TLV_NAME:
                    update.device_name = value.decode("utf-8", errors="replace").strip("\x00 ")
                elif tlv_id == _TLV_INFO_BATTERY and (battery := _battery(value)):
                    update.battery = battery

    def _handle_challenge(self, m: Message, update: SppUpdate) -> None:
        if m.is_response:
            update.frames.append(
                Message(TYPE_PHONE_REQUEST, OP_AUTH_CONFIRM, self._next_seq(), _AUTH_OK).encode()
            )
        elif len(m.payload) >= 17:
            answer = safer_plus.challenge_response(m.payload[1:17])
            update.frames.append(Message(TYPE_RESPONSE, OP_AUTH_CHALLENGE, m.seq, b"\x01" + answer).encode())

    def _handle_confirm(self, m: Message, update: SppUpdate) -> None:
        if m.payload != _AUTH_OK:
            update.auth_failed = True
            return

        self.authenticated = True
        update.authenticated_now = True
        update.frames.append(Message(TYPE_RESPONSE, OP_AUTH_CONFIRM, m.seq, b"\x01").encode())
        update.frames.append(Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_INFO, self._next_seq(), _QUERY_ALL).encode())
        update.frames.append(
            Message(TYPE_PHONE_REQUEST, OP_GET_DEVICE_RUN_INFO, self._next_seq(), _QUERY_ALL).encode()
        )
