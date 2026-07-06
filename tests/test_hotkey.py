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


def test_parse_numpad_digit():
    mods, vk = hotkey.parse_hotkey("ctrl+num2")
    assert mods == 0x0002
    assert vk == 0x62  # VK_NUMPAD2


def test_parse_top_row_digit_distinct_from_numpad():
    _mods, vk_top = hotkey.parse_hotkey("ctrl+2")
    _mods, vk_num = hotkey.parse_hotkey("ctrl+num2")
    assert vk_top == ord("2")
    assert vk_num == 0x62
    assert vk_top != vk_num


def test_normalize_keysym_kp_prefix():
    assert hotkey.normalize_keysym("KP_2") == "num2"


def test_normalize_keysym_digit_uses_keycode_for_numpad():
    assert hotkey.normalize_keysym("2", keycode=98) == "num2"
    assert hotkey.normalize_keysym("2", keycode=50) == "2"


def test_normalize_display_numpad():
    assert hotkey.normalize_hotkey("ctrl+num2") == "Ctrl+Num 2"


def test_canonical_spec_preserves_numpad_identity():
    assert hotkey.canonical_hotkey_spec("ctrl+Num 2") == "ctrl+num2"
    assert hotkey.canonical_hotkey_spec("ctrl+2") == "ctrl+2"
    assert hotkey.canonical_hotkey_spec("ctrl+2") != hotkey.canonical_hotkey_spec("ctrl+num2")


def test_diagnose_numpad_and_top_row_not_duplicate():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+num2",
        "quick_paste",
        {"quick_paste": "ctrl+num2", "manual_save": "ctrl+2"},
        win32_available=True,
    )
    assert kind == "ok"
    assert "Num 2" in msg


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
