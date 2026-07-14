"""Hotkey diagnosis helpers for settings UI."""

from __future__ import annotations

from cache_vault.core import hotkey


def test_diagnose_ok_default_binding():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift+v",
        "quick_paste",
        {"quick_paste": "ctrl+shift+v", "manual_save": "ctrl+shift+c"},
        win32_available=True,
    )
    assert kind == "ok"
    assert "Ready" in msg
    assert "Ctrl+Shift+V" in msg


def test_diagnose_invalid_missing_key():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift",
        "quick_paste",
        {"quick_paste": "ctrl+shift"},
        win32_available=True,
    )
    assert kind == "invalid"
    assert "Missing key" in msg


def test_diagnose_duplicate_within_app():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift+c",
        "quick_paste",
        {"quick_paste": "ctrl+shift+c", "manual_save": "ctrl+shift+c"},
        win32_available=True,
    )
    assert kind == "duplicate"
    assert "elsewhere" in msg


def test_diagnose_conflict_with_external_spec():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift+1",
        "quick_paste",
        {"quick_paste": "ctrl+shift+1"},
        win32_available=True,
        external_specs={"ctrl+shift+1": "macro “Signature”"},
    )
    assert kind == "conflict"
    assert "Signature" in msg


def test_diagnose_no_conflict_when_external_differs():
    kind, _msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift+v",
        "quick_paste",
        {"quick_paste": "ctrl+shift+v"},
        win32_available=True,
        external_specs={"ctrl+shift+1": "macro “Signature”"},
    )
    assert kind == "ok"


def test_diagnose_unavailable_without_win32():
    kind, msg = hotkey.diagnose_hotkey_spec(
        "ctrl+shift+v",
        "quick_paste",
        {"quick_paste": "ctrl+shift+v"},
        win32_available=False,
    )
    assert kind == "unavailable"


def test_default_hotkey_bindings_match_settings():
    from cache_vault.core.settings import Settings

    s = Settings()
    assert hotkey.DEFAULT_HOTKEY_BINDINGS["manual_save"] == s.manual_save_hotkey
    assert hotkey.DEFAULT_HOTKEY_BINDINGS["quick_paste"] == s.quick_paste_hotkey
