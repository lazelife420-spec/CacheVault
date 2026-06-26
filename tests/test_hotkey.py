import time

import pytest

from cache_vault.core import hotkey


def test_parse_basic_combo():
    mods, vk = hotkey.parse_hotkey("ctrl+shift+v")
    assert mods == (0x0002 | 0x0004)   # CONTROL | SHIFT
    assert vk == ord("V")


def test_parse_alt_win_and_named_key():
    mods, vk = hotkey.parse_hotkey("alt+win+space")
    assert mods == (0x0001 | 0x0008)   # ALT | WIN
    assert vk == 0x20                  # VK_SPACE


def test_parse_function_key():
    _mods, vk = hotkey.parse_hotkey("ctrl+f9")
    assert vk == 0x70 + 8              # F9


def test_parse_aliases():
    m1, _ = hotkey.parse_hotkey("control+v")
    m2, _ = hotkey.parse_hotkey("ctrl+v")
    assert m1 == m2
    m3, _ = hotkey.parse_hotkey("super+v")
    assert m3 == 0x0008               # WIN


def test_parse_no_main_key():
    _mods, vk = hotkey.parse_hotkey("ctrl+shift")
    assert vk is None


def test_normalize_orders_modifiers():
    assert hotkey.normalize_hotkey("v+shift+ctrl") == "Ctrl+Shift+V"
    assert hotkey.normalize_hotkey("WIN+ALT+space") == "Alt+Win+Space"


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.skipif(not hotkey._HAS_WIN32, reason="requires pywin32 / Windows desktop")
class TestHotkeyListenerRestart:
    """Regression: stop() must leave the listener restartable.

    start() previously no-op'd forever once ``_thread`` was set, because
    stop() asked the message-loop thread to exit but never cleared
    ``_thread``/``_hwnd`` and returned before the thread actually finished.
    """

    def test_single_listener_restarts_after_stop(self):
        listener = hotkey.HotkeyListener("ctrl+alt+shift+f9", lambda: None)
        listener.start()
        assert _wait_for(lambda: listener._hwnd is not None)

        listener.stop()
        assert _wait_for(lambda: listener._thread is None)

        listener.start()
        assert _wait_for(lambda: listener._hwnd is not None)
        listener.stop()
        assert _wait_for(lambda: listener._thread is None)

    def test_multi_listener_restarts_after_stop_with_new_bindings(self):
        listener = hotkey.MultiHotkeyListener()
        listener.set_binding(1, "ctrl+alt+shift+f10", lambda: None)
        listener.start()
        assert _wait_for(lambda: listener._hwnd is not None)
        assert _wait_for(lambda: 1 in listener.registered_ids())

        listener.stop()
        assert _wait_for(lambda: listener._thread is None)

        # Rebind to a different hotkey id, as the shell does on edit/save.
        listener.clear_bindings()
        listener.set_binding(2, "ctrl+alt+shift+f11", lambda: None)
        listener.start()
        assert _wait_for(lambda: listener._hwnd is not None)
        assert _wait_for(lambda: 2 in listener.registered_ids())

        listener.stop()
        assert _wait_for(lambda: listener._thread is None)
