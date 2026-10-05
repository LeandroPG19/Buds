One desktop app for **Xiaomi / Redmi Buds**: battery of each earbud and the case, noise control and low-latency mode, on Windows and Linux. No phone, account or cloud.

## Download

| System | File |
|--------|------|
| Windows 10 / 11 (64-bit) | `MiBudsClient-<version>-windows-x64.zip` |
| Linux (64-bit) | `MiBudsClient-<version>-linux-x64.zip` |

macOS is not supported: Python has no Bluetooth RFCOMM socket there, so the app could not talk to the earbuds.

## Supported earbuds

| Model | Battery | Noise control | Low-latency |
|-------|:-------:|:-------------:|:-----------:|
| Redmi Buds 5 Pro | left / right / case | yes | not yet |
| Redmi Buds 6 Play | left / right / case | n/a | yes |
| Other Redmi / Xiaomi Buds | combined level | not yet | not yet |

Models that are not verified yet still work for the battery and record what they exchange, so they can get a proper profile: see **Help us support your model** in the README.

## How to use it

1. Pair your earbuds in the Bluetooth settings of your system and **connect** them (out of the case).
2. Unzip and run `MiBudsClient`.

**Windows:** the file is not code-signed, so SmartScreen may say "Windows protected your PC". Choose *More info* then *Run anyway*. The source is public, and you can build the same file yourself (README).

**Linux:** make it executable (`chmod +x MiBudsClient`). It needs BlueZ (the usual Bluetooth stack). The tray icon needs GTK 3 (`python3-gi` and `gir1.2-gtk-3.0` on Debian/Ubuntu); without them the app still works, just without the tray icon. This build has had little testing on Linux; please report problems.

Licensed under the GNU GPLv3; the source is at https://github.com/LeandroPG19/Buds.
