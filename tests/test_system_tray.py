import importlib
import sys

import pytest

from ui import system_tray


@pytest.fixture
def tray_without_pystray(monkeypatch):
    """Reload the module as if pystray could not load (Linux without GTK, no display...)."""
    monkeypatch.setitem(sys.modules, "pystray", None)  # makes `import pystray` raise ImportError
    yield importlib.reload(system_tray)
    monkeypatch.undo()
    importlib.reload(system_tray)


def test_the_module_imports_when_pystray_cannot_load(tray_without_pystray):
    assert tray_without_pystray.pystray is None


def test_a_missing_tray_does_not_stop_the_app(tray_without_pystray):
    tray = tray_without_pystray.SystemTray(on_show=lambda: None, on_exit=lambda: None)
    tray.run()
    tray.refresh_menu()
    tray.notify("hello")
    assert tray.icon is None


def test_a_pystray_that_fails_while_loading_is_also_tolerated(monkeypatch):
    def failing_import(name, *args, **kwargs):
        if name == "pystray":
            raise ValueError("Namespace Gtk not available")
        return real_import(name, *args, **kwargs)

    real_import = __import__
    monkeypatch.setattr("builtins.__import__", failing_import)
    reloaded = importlib.reload(system_tray)
    assert reloaded.pystray is None
    monkeypatch.undo()
    importlib.reload(system_tray)
