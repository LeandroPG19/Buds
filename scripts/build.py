"""Build the standalone app for this operating system and zip it.

The same script runs on a developer PC and in the release workflow:

    python scripts/build.py              # tests, then build and zip
    python scripts/build.py --skip-tests

macOS is not supported: Python has no Bluetooth RFCOMM socket there, so the app could start
but never talk to the earbuds.
"""

import argparse
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_NAME = "MiBudsClient"


def read_version() -> str:
    source = (ROOT / "ui" / "constants.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"(v[^"]+)"', source, re.MULTILINE)
    if not match:
        raise SystemExit("APP_VERSION not found in ui/constants.py")
    return match.group(1)


def os_label() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise SystemExit(
        f"Unsupported platform {sys.platform!r}: the app needs a Bluetooth RFCOMM socket "
        "(Windows or Linux only)."
    )


def arch_label() -> str:
    machine = os.environ.get("PROCESSOR_ARCHITECTURE") if sys.platform == "win32" else os.uname().machine
    return {"AMD64": "x64", "x86_64": "x64", "ARM64": "arm64", "aarch64": "arm64"}.get(machine or "", machine or "unknown")


def artifact_name(version: str, label: str, arch: str) -> str:
    return f"{APP_NAME}-{version}-{label}-{arch}.zip"


def pack_command(label: str) -> list[str]:
    command = [
        sys.executable, "-m", "flet.cli", "pack", "main.py",
        "--name", APP_NAME,
        "--distpath", str(DIST),
        "--add-data", "assets:assets",
        "-y",
    ]
    if label == "windows":
        command += ["--icon", str(ROOT / "assets" / "icon.ico")]
    else:
        command += ["--icon", str(ROOT / "assets" / "icon.png"), "--hidden-import", "optparse"]
    return command


def built_file(label: str) -> Path:
    return DIST / (f"{APP_NAME}.exe" if label == "windows" else APP_NAME)


def make_zip(executable: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(executable, executable.name)
        archive.write(ROOT / "LICENSE", "LICENSE")
        archive.write(ROOT / "README.md", "README.md")


def check_bluetooth_socket() -> None:
    import socket

    if not hasattr(socket, "AF_BLUETOOTH"):
        raise SystemExit(
            "This Python has no Bluetooth socket support (socket.AF_BLUETOOTH is missing); "
            "a build made with it could never reach the earbuds."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-tests", action="store_true", help="do not run pytest first")
    args = parser.parse_args()

    label = os_label()
    check_bluetooth_socket()

    if not args.skip_tests:
        subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)

    subprocess.run(pack_command(label), cwd=ROOT, check=True)

    executable = built_file(label)
    if not executable.exists():
        raise SystemExit(f"flet pack finished but {executable} does not exist")

    target = DIST / artifact_name(read_version(), label, arch_label())
    make_zip(executable, target)
    print(f"Built {target} ({target.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
