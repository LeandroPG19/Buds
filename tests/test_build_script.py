import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_script", ROOT / "scripts" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_version_is_read_from_the_app_constants():
    assert build.read_version().startswith("v")
    assert build.read_version() in (ROOT / "ui" / "constants.py").read_text(encoding="utf-8")


def test_artifact_name_says_version_os_and_architecture():
    assert build.artifact_name("v1.2.3", "windows", "x64") == "MiBudsClient-v1.2.3-windows-x64.zip"


@pytest.mark.parametrize(
    "platform, label",
    [("win32", "windows"), ("linux", "linux")],
)
def test_supported_platforms(monkeypatch, platform, label):
    monkeypatch.setattr(build.sys, "platform", platform)
    assert build.os_label() == label


def test_macos_is_refused_because_python_has_no_bluetooth_socket_there(monkeypatch):
    monkeypatch.setattr(build.sys, "platform", "darwin")
    with pytest.raises(SystemExit) as error:
        build.os_label()
    assert "RFCOMM" in str(error.value)


@pytest.mark.parametrize(
    "machine, expected",
    [("AMD64", "x64"), ("x86_64", "x64"), ("ARM64", "arm64"), ("aarch64", "arm64")],
)
def test_architecture_names(monkeypatch, machine, expected):
    monkeypatch.setattr(build.sys, "platform", "win32")
    monkeypatch.setenv("PROCESSOR_ARCHITECTURE", machine)
    assert build.arch_label() == expected


def test_windows_build_uses_the_ico_icon_and_bundles_the_assets():
    command = build.pack_command("windows")
    assert command[command.index("--icon") + 1].endswith("icon.ico")
    assert "assets:assets" in command
    assert "optparse" not in command


def test_linux_build_uses_the_png_icon_and_the_hidden_import():
    command = build.pack_command("linux")
    assert command[command.index("--icon") + 1].endswith("icon.png")
    assert command[command.index("--hidden-import") + 1] == "optparse"


def test_built_file_name_depends_on_the_os():
    assert build.built_file("windows").name == "MiBudsClient.exe"
    assert build.built_file("linux").name == "MiBudsClient"


def test_the_zip_carries_the_program_and_the_license(tmp_path):
    executable = tmp_path / "MiBudsClient.exe"
    executable.write_bytes(b"binary")
    target = tmp_path / "out.zip"
    build.make_zip(executable, target)
    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == ["LICENSE", "MiBudsClient.exe", "README.md"]
