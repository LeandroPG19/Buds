# MiBudsClient

A Python & Flet-based desktop client for Xiaomi/Redmi Buds. Features real-time battery tracking and low-latency mode via Bluetooth.

## Features

- **Battery Tracking:** Real-time display of battery percentages for left earbud, right earbud, and charging case.
- **Charging Status:** Indicators showing whether the earbuds or case are currently charging.
- **Low Latency Mode:** Off, Auto, and On modes for controlling Game Mode (Low Latency). Auto mode uses a single app list with Exclude/Include behavior and supports keeping low latency active until the app closes.
- **System Tray Support:** Minimize to tray and control features like Low Latency Mode directly from the tray menu.
- **Auto-Connect:** Automatically detects compatible connected Bluetooth devices.
- **Single Instance Protection:** Prevents multiple instances of the application from running simultaneously.
- **Windows Startup Support:** Option to start the application automatically when Windows boots.
- **Smart Updater:** Built-in update checker that supports semantic versioning, including pre-release tags like `alpha`, `beta`, and `rc`.
- **Modern UI:** A sleek, dark-themed interface built with the Flet framework.

## Downloads

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/3767c651-d965-4450-b191-1369292c8383" width="400"></td>
  </tr>
  <tr>
    <td><a href="https://github.com/CesurPolat/MiBudsClient/releases"><img src="https://github.com/user-attachments/assets/abf831bc-7329-435a-a398-b1f6c706ca0d" width="200"></a></td>
  </tr>
</table>

## Installation

1. Clone or download this repository:
   ```bash
   git clone https://github.com/CesurPolat/MiBudsClient.git
   cd MiBudsClient
   ```

2. Install the required dependencies (Flet 1.0.x; the first launch downloads its desktop client):
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the following command in your terminal to start the application:

```bash
python main.py
```

Upon launch, the app will automatically scan for your device and attempt to connect. Once connected, battery levels will be displayed on the screen.

## Building the Executable

To package the application into a standalone executable for Windows, run the following command:

```bash
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

```bash
flet pack main.py \
  --icon assets/icon.ico \
  --add-data "assets:assets" \
  --name "MiBudsClient" \
  --hidden-import optparse
```

## Supported Devices

The app picks whichever connected device is named like a Redmi/Xiaomi Buds and shows its name.

| Model | Status |
|-------|--------|
| Redmi Buds 6 Play | Verified on hardware: battery and low latency mode |
| Redmi Buds 5 Pro | Verified on hardware: battery of each earbud and the case, and noise control (off / noise cancelling / transparency). Low latency mode is not available yet. |
| Any other Redmi/Xiaomi Buds | Same protocol assumed, **not verified**. The window shows a notice and every packet is recorded to `%APPDATA%\MiBudsClient\packets-<model>.log` so the model can get its own verified profile (see `bluetooth/profiles.py`). |

## Credits

The authentication handshake of newer earbuds (Redmi Buds 5 Pro) follows the protocol documented by
[Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) and
[XiaomayEarbudsWin](https://github.com/Apechi/XiaomayEarbudsWin); this is an independent Python implementation validated on real hardware.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3). See the [LICENSE](LICENSE) file for details.

---
**Note:** This is not an official Xiaomi application. It is developed for personal use and the open-source community.
