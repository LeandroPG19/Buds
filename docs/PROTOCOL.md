# Xiaomi / Redmi Buds control protocol

How MiBudsClient talks to the earbuds, as implemented in `bluetooth/` and checked against real hardware. It is an unofficial description written from the open-source work listed in [Credits](#credits) and from captures of real earbuds; it can be incomplete or wrong for models that have not been tested.

| Model | Transport | What is verified |
|-------|-----------|------------------|
| Redmi Buds 6 Play | direct commands, no authentication | battery, low-latency mode |
| Redmi Buds 5 Pro | authenticated session (`spp_auth`) | authentication, battery, noise control |

All multi-byte numbers are big-endian. Every example below is hex.

## Transport

Bluetooth Classic **RFCOMM**, opened with a plain socket. The control service has the UUID `0000fd2d-0000-1000-8000-00805f9b34fb` (service name `xiaoai` on the 5 Pro). Its **channel number differs per model** (6 Play: 6, 5 Pro: 24), so do not hard-code it.

The channel is in the SDP records the OS stored at pairing time. On Windows they are in the registry, readable without administrator rights:

```
HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\<mac>\CachedServices
```

Each value is an SDP record. Find the one that contains the service UUID (`1C` + the 16 UUID bytes) and read the RFCOMM channel from its protocol descriptor: `19 00 03 08 <channel>`. See `bluetooth/sdp.py`.

## Frame

```
FE DC BA | type | opcode | length (2) | [00] | seq | payload | EF
```

- `length` counts `seq` and the payload, plus the `00` pad in responses.
- The `00` pad exists only in responses (types without the `0x40` bit).
- `seq` is a counter kept by whoever sends a request; a response repeats the `seq` of the request it answers.

| Type | Meaning |
|------|---------|
| `C4` | request from the phone/PC |
| `04` | response |
| `C0` | request from the earbuds |
| `C7` | notification from the earbuds (must be acknowledged) |

| Opcode | Name |
|--------|------|
| `02` | GET_DEVICE_INFO |
| `08` | ANC (noise control) |
| `09` | GET_DEVICE_RUN_INFO |
| `0E` | REPORT_STATUS |
| `50` / `51` | AUTH_CHALLENGE / AUTH_CONFIRM |
| `F2` / `F3` / `F4` | SET_CONFIG / GET_CONFIG / NOTIFY_CONFIG |

A single read can contain several frames; split on `FE DC BA` and check the length and the trailing `EF`. See `bluetooth/spp_frame.py`.

## Redmi Buds 6 Play: direct commands

No handshake. The two commands the app sends are ordinary frames:

| Command | Bytes |
|---------|-------|
| Setup packet after connecting (an `AUTH_CONFIRM` response) | `fedcba04510003000301ef` |
| Ask for device info (carries the battery); a `GET_DEVICE_INFO` frame followed by a `4f` byte that the original app has always sent | `fedcbac40200050bffffffffef4f` |
| Low-latency on | `fedcbac4f200059003002f01ef` |
| Low-latency off | `fedcbac4f200059003002f00ef` |

The battery is found in the answer by the marker `02 02 04 07`; the three bytes after it are left, right and case.

## Redmi Buds 5 Pro: authenticated session

The earbuds **ignore every request until the app authenticates**; they do not answer or disconnect, so a silent channel usually means "not authenticated".

### Handshake

| # | Direction | Frame |
|---|-----------|-------|
| 1 | app → earbuds | `C4` / `50`, seq 0, payload `01` + 16 random bytes |
| 2 | earbuds → app | `04` / `50`, payload `01` + their answer to your challenge |
| 3 | app → earbuds | `C4` / `51`, payload `01 00` |
| 4 | earbuds → app | `04` / `51`, payload `01` |
| 5 | earbuds → app | `C0` / `50`, payload `01` + **their** 16-byte challenge |
| 6 | app → earbuds | `04` / `50` with the same `seq`, payload `01` + `SAFER+(challenge)` |
| 7 | earbuds → app | `C0` / `51`, payload **`01 00` = authenticated**, `01 01` = rejected |
| 8 | app → earbuds | `04` / `51` with the same `seq`, payload `01`, then `GET_DEVICE_INFO` and `GET_DEVICE_RUN_INFO` |

Both requests carry the payload `ff ff ff ff`. See `bluetooth/spp_session.py`.

### The cipher

The answer to a challenge is a Bluetooth-style **SAFER+** encryption of a fixed block, using the challenge as the key:

```
answer = encrypt(plaintext = 11 22 33 33 22 11 11 22 33 33 22 11 11 22 33 33, key = challenge)
```

Parameters, from the Gadgetbridge implementation (`bluetooth/safer_plus.py`):

- 128-bit key, 8 rounds. A byte position `i` uses **XOR and the exponent table** when bit `i` of `0x9999` is set, and **addition modulo 256 and the logarithm table** when it is clear.
- Tables: `exp(x) = 45^x mod 257` (with `exp(128) = 0`), `log` is its inverse with `log(0) = 128` and **`log(1) = 0`**.
- Key schedule: `key[15] ^= 6`; a 17-byte register is the key plus the XOR of all its bytes; before each subkey **every register byte is rotated left by 3 bits**; subkey `i`, byte `j` is `register[(i + j) mod 17] + bias[i-1][j]`, with `bias[i][j] = 45^(45^(17(i+2)+j+1) mod 257) mod 257`.
- Each round: combine with an even subkey, exp/log layer, combine with an odd subkey, then multiply by the 16×16 SAFER+ linear matrix (four PHT layers with the Armenian shuffle). Before the third round (index 2) the plaintext is combined in again. A final subkey closes the block.

Two mistakes that make the handshake fail **silently** and that exist in at least one public port: rotating the register left by 5 instead of 3, and leaving `log(1)` at 128 instead of 0. The earbuds are a free test oracle: the answer they send in step 2 is `encrypt(SEQ, your challenge)`, so you can validate an implementation without guessing. A pair captured from a real unit:

```
challenge  9762e8a1836d32cc4b7b8605c553545f
answer     f7fe2d0211bab715efe4c33ac740574d
```

### After authenticating

Every frame below is a TLV stream: `[length][id][value…]`, where `length` counts the id and the value.

**Battery** is `[left][right][case]`, one byte each. Bit 7 means charging, the low 7 bits are the percentage and `FF` means unknown (the case reports `FF` when the earbuds are out of it). It comes in the `GET_DEVICE_INFO` response (id `07`, seen on a real 5 Pro) and in `REPORT_STATUS` (id `00`, as documented by the reference projects; the app handles it but it has not been observed on the test unit yet).

**Device name** is id `00` of the `GET_DEVICE_INFO` response, as text.

**Noise control** (Redmi Buds 5 Pro):

| Mode | Value |
|------|-------|
| off | `00` |
| noise cancelling | `01` |
| transparency | `02` |

To change it, send `C4` / `08` with payload `02 04 <mode>`; the earbuds answer with an empty `04` / `08`. The current mode is in id `09` of the `GET_DEVICE_RUN_INFO` response, and every change is announced by a `NOTIFY_CONFIG` entry `[04][00][0b][mode][strength]`. The `REPORT_STATUS` entry with id `04` stays `00` whatever the mode, so it is **not** the noise mode.

**Acknowledgements.** `REPORT_STATUS` (`0E`) and `NOTIFY_CONFIG` (`F4`) must be answered with an empty `04` frame carrying the same `seq`. The earbuds repeated an unanswered `AUTH_CONFIRM` request until it was answered, so unanswered requests should be expected to be resent.

## What is not implemented

Noise-control strength, adaptive noise cancelling, the equalizer, touch gestures, ear detection and firmware information exist in the protocol and are not used by the app yet. The low-latency command of the 5 Pro is unknown.

## Credits

- [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) (AGPL-3.0), Redmi Buds support by Jonathan Gobbo: the reference for framing, the handshake and the cipher.
- [XiaomayEarbudsWin](https://github.com/Apechi/XiaomayEarbudsWin) (MIT): a Windows client that documents the same protocol.
- The implementation in this repository is independent, written in Python and checked against a real Redmi Buds 5 Pro.
