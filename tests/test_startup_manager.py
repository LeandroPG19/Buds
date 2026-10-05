import importlib
import platform

import pytest

from utils import startup_manager


@pytest.fixture
def fresh_module(monkeypatch):
    def boom():
        raise AssertionError("platform.system() can take ~80 s on PCs with a slow WMI; use sys.platform")

    monkeypatch.setattr(platform, "system", boom)
    yield importlib.reload(startup_manager)
    monkeypatch.undo()
    importlib.reload(startup_manager)


def test_module_never_calls_platform_system(fresh_module):
    monkey = fresh_module
    assert monkey.is_startup_enabled() in (True, False)


def test_set_startup_dispatches_by_sys_platform(fresh_module, monkeypatch):
    calls = []
    monkeypatch.setattr(fresh_module, "_set_startup_windows", lambda enabled: calls.append(("win", enabled)) or True)
    monkeypatch.setattr(fresh_module, "_set_startup_linux", lambda enabled: calls.append(("linux", enabled)) or True)

    monkeypatch.setattr(fresh_module.sys, "platform", "win32")
    assert fresh_module.set_startup(True) is True
    monkeypatch.setattr(fresh_module.sys, "platform", "linux")
    assert fresh_module.set_startup(False) is True
    monkeypatch.setattr(fresh_module.sys, "platform", "darwin")
    assert fresh_module.set_startup(True) is False

    assert calls == [("win", True), ("linux", False)]
