# AGENTS.md

## Must-follow constraints

- **Windows and Linux support.** Bluetooth discovery can use platform-specific implementations (Windows: PowerShell via `subprocess` + `Get-PnpDevice`, Linux: native Linux-compatible discovery). Keep behavior consistent across supported platforms.
- **One app for the whole Xiaomi/Redmi Buds family.** The owner has several models and wants a single client (decided 2026-10-05; this replaces the old "6 Play only" rule). Everything that can differ per model lives in a `DeviceProfile` in `bluetooth/profiles.py`: name pattern, RFCOMM port, battery pattern and request, mode command, setup packets. Add a model by adding a profile there, never by branching in the controller or UI.
- **`verified` means tested on hardware.** Redmi Buds 6 Play (legacy transport: commands are sent straight away) and Redmi Buds 5 Pro (`spp_auth` transport: SAFER+ challenge/response first; battery of left, right and case and noise control off/noise cancelling/transparency verified on a real unit on 2026-10-05; no low latency command known, so `supports_low_latency=False` and the UI hides that card; `supports_anc=True` shows the Noise Control card) are `verified=True`. Any other model uses the family profile with `verified=False`: the app shows a notice, records its packets to `%APPDATA%\MiBudsClient\packets-<model>.log` and shows the combined battery Windows reports. Do not flip `verified` or invent per-model bytes without a capture from that hardware.
- **Authenticated models.** `bluetooth/spp_frame.py` (framing), `bluetooth/safer_plus.py` (cipher) and `bluetooth/spp_session.py` (handshake state machine) implement the protocol documented by Gadgetbridge (AGPL-3.0) and XiaomayEarbudsWin (MIT); credit them if code is derived. `tests/test_safer_plus.py` holds challenge/answer pairs captured from real earbuds: if they fail, the cipher is wrong. The RFCOMM channel comes from the OS SDP cache (`bluetooth/sdp.py`), never hard-coded alone: it differs per model (6 Play: 6, 5 Pro: 24).
- **Device matching is by name.** `BluetoothDiscovery.select_device` picks a connected device whose name matches a profile (specific profiles before the family one). Do not fall back to an arbitrary connected device.
- **RFCOMM port lives in the profile.** Default is 6 (`bluetooth/constants.py`); a model that needs another channel gets its own profile value.
- **Assets directory bundling.** Build uses `datas=[('assets', 'assets')]` in PyInstaller spec. All UI assets (icon.ico, images) must stay in `assets/` folder.
- **Single instance enforcement.** Application forbids multiple running instances via port 65432. Do not remove or change `check_for_existing_instance()` at app startup.
- **Flet-only UI.** The entire UI layer (including system tray via pystray) depends on Flet. Do not introduce other UI frameworks.

## Validation before finishing

- **Unit tests pass.** `pip install -r requirements-dev.txt`, then `python -m pytest`. New behavior gets a test seen failing first.
- **Test with actual device.** Any change to the bytes of a profile in `bluetooth/profiles.py` or to `bluetooth/constants.py` must be tested against that model's hardware; unit tests alone are insufficient. `tests/test_protocol.py` pins the verified 6 Play bytes.
- **Build succeeds.** Run `flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"` and verify executable runs.
- **Single instance works.** Launch executable twice; second instance should exit silently and focus existing window.

## Repo-specific conventions

- **Protocol payloads are hex strings.** All Bluetooth command/response data in `bluetooth/constants.py` and `protocol.py` use `.fromhex()` conversion. Maintain consistency.
- **Battery encoding.** Raw byte values >= 128 indicate charging (subtract 128 for actual %). See `BatteryIndicator._format_battery()` in `ui/components.py`.
- **Callbacks over events.** BT controller uses callback functions (`status_callback`, `battery_callback`) instead of events. Maintain this pattern.
- **Resource paths via `get_resource_path()`** in `utils/resource_manager.py`. Use this for assets in UI code.
- **Version string format.** Semantic versioning with optional pre-release tags: `v1.2.3`, `v1.2.3-alpha.1`, `v1.2.3-beta.2`, `v1.2.3-rc1`. Parser in `utils/updater.py` supports these formats.

## Important locations

- **Per-model protocol:** `bluetooth/profiles.py` (profiles, `match_profile`); defaults in `bluetooth/constants.py` (BATTERY_PATTERN, MODE_COMMAND_TEMPLATE, timeouts)
- **Packet capture for unverified models:** `utils/diagnostics.py`
- **Protocol documentation:** `docs/PROTOCOL.md` (framing, handshake, cipher, battery, noise control). Keep it in step with `bluetooth/spp_*.py` and the profiles.
- **Adding a model from a capture:** the "Add my model" issue form (`.github/ISSUE_TEMPLATE/add-my-model.yml`) collects the packet log. Read the RFCOMM channel from the SDP records (`bluetooth/sdp.py` explains how), try the handshake of `docs/PROTOCOL.md`, then add a `DeviceProfile` with `verified=True` only after the model's own hardware confirmed it.
- **Build config:** `MiBudsClient.spec` (assets bundling, icon path)
- **UI constants (colors, sizes):** `ui/constants.py`

## Change safety rules

- **Preserve backward compatibility.** Do not change protocol packets or device matching logic without testing on hardware.
- **Do not add external Bluetooth libraries.** Current implementation uses Python's `socket` module directly for RFCOMM. Keep it minimal.
- **Flet is pinned to 1.0.x.** Use the 1.0 API (`ft.run`, `ft.Padding.*`, `ft.Border.*`, `ft.Alignment.*`, `ft.Button`); the lowercase 0.x helpers and `ft.app` no longer exist.
- **Do not call `platform.system()`.** On some PCs it takes ~80 s (Python queries WMI). Use `sys.platform`.
- **GitHub URL is contractual.** Hardcoded in UI constants and used by updater. Changes break update checking and links.
