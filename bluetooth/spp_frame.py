"""Wire framing of the Xiaomi/Redmi Buds control protocol.

Frame: FE DC BA | type | opcode | length (u16 BE) | [00 if response] | seq | payload | EF
The length counts the payload plus the sequence byte (plus the 00 pad in responses).
"""

from dataclasses import dataclass

HEADER = bytes([0xFE, 0xDC, 0xBA])
TRAILER = 0xEF

TYPE_PHONE_REQUEST = 0xC4
TYPE_RESPONSE = 0x04
TYPE_EARBUDS_REQUEST = 0xC0
TYPE_EARBUDS_NOTIFY = 0xC7

OP_GET_DEVICE_INFO = 0x02
OP_ANC = 0x08
OP_GET_DEVICE_RUN_INFO = 0x09
OP_REPORT_STATUS = 0x0E
OP_AUTH_CHALLENGE = 0x50
OP_AUTH_CONFIRM = 0x51
OP_SET_CONFIG = 0xF2
OP_GET_CONFIG = 0xF3
OP_NOTIFY_CONFIG = 0xF4


def is_request_type(msg_type: int) -> bool:
    """Request types carry the 0x40 bit and have no 00 pad in the header."""
    return bool(msg_type & 0x40)


@dataclass(frozen=True)
class Message:
    msg_type: int
    opcode: int
    seq: int
    payload: bytes = b""

    @property
    def is_response(self) -> bool:
        return not is_request_type(self.msg_type)

    def encode(self) -> bytes:
        length = len(self.payload) + (1 if is_request_type(self.msg_type) else 2)
        frame = bytearray(HEADER)
        frame += bytes([self.msg_type, self.opcode, length >> 8, length & 0xFF])
        if not is_request_type(self.msg_type):
            frame.append(0x00)
        frame.append(self.seq)
        frame += self.payload
        frame.append(TRAILER)
        return bytes(frame)


def parse_stream(data: bytes) -> list[Message]:
    """Split a received chunk into frames; it may carry several or ignore trailing garbage."""
    messages: list[Message] = []
    pos = data.find(HEADER)
    while pos != -1 and pos + 7 <= len(data):
        msg_type, opcode = data[pos + 3], data[pos + 4]
        length = (data[pos + 5] << 8) | data[pos + 6]
        pad = 0 if is_request_type(msg_type) else 1
        seq_at = pos + 7 + pad
        end = pos + 7 + length

        if length < 1 + pad or end >= len(data) or data[end] != TRAILER:
            pos = data.find(HEADER, pos + 1)
            continue

        messages.append(Message(msg_type, opcode, data[seq_at], bytes(data[seq_at + 1:end])))
        pos = data.find(HEADER, end + 1)
    return messages
