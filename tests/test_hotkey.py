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
