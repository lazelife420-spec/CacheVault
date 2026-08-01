"""Vault Macro live execution — core engine, variables, receipts, toggles."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import receipts_dir
from cache_vault.core.macro_execute import (
    MacroExecutor,
    find_macros_for_hotkey,
    match_shortcut_suffix,
    system_reserved_hotkeys,
)
from cache_vault.core.macro_variables import MacroVariableContext, expand_macro_variables
from cache_vault.core.paste_delivery import PasteResult
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.core.vault_macros import (
    Macro,
    MacroSafeRegistry,
    MacroStore,
    OUTPUT_CLIPBOARD_PASTE,
    OUTPUT_KEYSTROKE,
    TRIGGER_HOTKEY,
    TRIGGER_MENU_ONLY,
    TRIGGER_TEXT_SHORTCUT,
)


@pytest.fixture
def exec_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings = Settings()
    settings.vault_macros_enabled = True
    settings.vault_macros_setup_completed = True
    settings.macro_text_shortcuts_enabled = True
    settings.macro_hotkeys_enabled = True
    settings.macro_sensitive_confirmation = True
    store = MacroStore(tmp_path / "CacheVault" / "macros.json")
    registry = MacroSafeRegistry(settings)
    # Keep `vault` referenced for the fixture's full lifetime: Vault.__del__
    # closes its storage connection, and prior to this fix nothing kept the
    # Vault itself alive once this function returned (only `events`, which
    # holds a reference to `vault.storage` but not to `vault`) -- CPython's
    # refcounting GC collected `vault` immediately, closing the in-memory
    # connection `events` still depended on for the rest of the test.
    vault = Vault(storage=VaultStorage(":memory:"), settings=settings)
    events = vault.events
    notices: list[str] = []
    executor = MacroExecutor(
        settings,
        store,
        registry,
        events,
        on_notice=notices.append,
        confirm_sensitive=lambda _label: True,
    )
    try:
        yield settings, store, registry, events, executor, notices
    finally:
        vault.close()


def test_exec_env_events_survive_fixture_setup(exec_env):
    """Regression for the fixture-lifetime defect: before this fix, nothing
    kept `vault` referenced past exec_env's setup returning, so CPython's
    refcounting GC collected it immediately, Vault.__del__ closed the
    in-memory connection `events` still depended on, and any write here
    raised sqlite3.ProgrammingError: Cannot operate on a closed database."""
    _settings, _store, _registry, events, _executor, _notices = exec_env
    event_id = events.record("regression_probe", details={"probe": True})
    recent = events.recent(limit=10)
    assert any(row["id"] == event_id for row in recent)


def test_exec_env_never_touches_real_profile(exec_env):
    from cache_vault.core.storage import default_db_path

    _settings, _store, _registry, events, _executor, _notices = exec_env
    assert str(events._storage.db_path) == ":memory:"
    assert events._storage.db_path != default_db_path()


def test_vault_close_and_del_are_idempotent():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    storage = vault.storage

    vault.close()
    vault.close()
    vault.__del__()

    with pytest.raises(sqlite3.ProgrammingError):
        storage.conn.execute("SELECT 1")


def _macro(**kwargs) -> Macro:
    defaults = dict(
        id="m1",
        name="Test Macro",
        body="Hello {date}",
        enabled=True,
        trigger_type=TRIGGER_MENU_ONLY,
        output_mode=OUTPUT_CLIPBOARD_PASTE,
    )
    defaults.update(kwargs)
    return Macro(**defaults)


def test_core_macro_execute_imports_without_ui():
    import ast

    src = Path(__file__).resolve().parents[1] / "cache_vault" / "core" / "macro_execute.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "customtkinter" not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert "customtkinter" not in node.module


def test_variable_expansion_live_path():
    ctx = MacroVariableContext(safe_name="Email Safe", item_id="abc")
    expanded, missing = expand_macro_variables(
        "On {date} at {time} — {safe_name} / {item_id}{newline}Tab:{tab}",
        ctx,
    )
    assert not missing
    assert "Email Safe" in expanded
    assert "abc" in expanded
    assert "\n" in expanded
    assert "\t" in expanded


def test_clipboard_paste_mode_prepares_output(exec_env, monkeypatch):
    settings, store, _registry, events, executor, _notices = exec_env
    macro = _macro(body="Paste me")
    store.upsert(macro)
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.set_clipboard_text", lambda t: t == "Paste me",
    )
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.deliver_ctrl_v",
        lambda _hwnd: PasteResult(True, "ok", "Notepad"),
    )
    monkeypatch.setattr("cache_vault.core.macro_execute.send_backspaces", lambda *a, **k: True)
    result = executor.execute(
        macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=12345,
    )
    assert result.ok
    assert result.output_mode == OUTPUT_CLIPBOARD_PASTE
    assert result.target_title == "Notepad"


def test_execution_success_and_failure_receipts(exec_env, monkeypatch, tmp_path):
    settings, store, _registry, events, executor, _notices = exec_env
    macro = _macro(body="Hi")
    store.upsert(macro)
    monkeypatch.setattr("cache_vault.core.macro_execute.set_clipboard_text", lambda _t: True)
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.deliver_ctrl_v",
        lambda _hwnd: PasteResult(False, "focus_restore_failed", "App"),
    )
    result = executor.execute(macro, trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+alt+1", target_hwnd=1)
    assert not result.ok
    files = list(receipts_dir().glob("macro_failed-*.json"))
    assert files
    body = json.loads(files[0].read_text(encoding="utf-8"))
    assert "Hi" not in json.dumps(body)
    assert "body" not in body
    assert body.get("macro_id") == "m1"


def test_receipt_on_success(exec_env, monkeypatch):
    settings, store, _registry, events, executor, _notices = exec_env
    macro = _macro(body="OK", trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";sig")
    store.upsert(macro)
    monkeypatch.setattr("cache_vault.core.macro_execute.set_clipboard_text", lambda _t: True)
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.deliver_ctrl_v",
        lambda _hwnd: PasteResult(True, "ok", "Notepad"),
    )
    result = executor.execute(
        macro,
        trigger_type=TRIGGER_TEXT_SHORTCUT,
        trigger_value=";sig",
        target_hwnd=99,
        shortcut_backspaces=4,
    )
    assert result.ok
    assert result.action == "text_shortcut_expanded"
    files = list(receipts_dir().glob("text_shortcut_expanded-*.json"))
    assert files


def test_disabled_macro_does_not_execute(exec_env):
    _settings, store, _registry, _events, executor, _notices = exec_env
    macro = _macro(enabled=False)
    store.upsert(macro)
    result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    assert not result.ok
    assert result.skipped_disabled


def test_global_macro_disabled_blocks_execution(exec_env):
    settings, store, _registry, _events, executor, _notices = exec_env
    settings.vault_macros_enabled = False
    macro = _macro()
    store.upsert(macro)
    ok, reason = executor.execution_allowed()
    assert not ok
    result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    assert not result.ok
    assert reason == "vault_macros_disabled"


def test_macro_hotkeys_disabled_via_resolve(exec_env):
    settings, store, _registry, _events, executor, _notices = exec_env
    settings.macro_hotkeys_enabled = False
    macro = _macro(trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+alt+9")
    store.upsert(macro)
    macros, picker = executor.resolve_hotkey("ctrl+alt+9")
    assert macros == []
    assert not picker


def test_duplicate_hotkey_returns_picker_needed(exec_env):
    settings, store, _registry, _events, executor, _notices = exec_env
    store.save_all([
        _macro(id="a", trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+alt+9"),
        _macro(id="b", name="B", trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+alt+9"),
    ])
    macros, picker = executor.resolve_hotkey("ctrl+alt+9")
    assert len(macros) == 2
    assert picker is True


def test_sensitive_macro_blocked_when_not_confirmed(exec_env, monkeypatch):
    settings, store, _registry, _events, executor, notices = exec_env
    executor.confirm_sensitive = lambda _label: False
    macro = _macro(body="password: hunter2", sensitive_confirm=True)
    store.upsert(macro)
    result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    assert not result.ok
    assert result.blocked_sensitive
    files = list(receipts_dir().glob("macro_blocked_sensitive-*.json"))
    assert files


def test_text_shortcut_suffix_match():
    macros = [
        _macro(id="1", trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";sig"),
        _macro(id="2", trigger_type=TRIGGER_TEXT_SHORTCUT, trigger_value=";signature"),
    ]
    hit = match_shortcut_suffix("hello;sig", macros)
    assert hit and hit[0] == ";sig"
    hit2 = match_shortcut_suffix("x;signature", macros)
    assert hit2 and hit2[0] == ";signature"


def test_system_reserved_hotkeys_includes_capture_and_paste(exec_env):
    settings, *_ = exec_env
    reserved = system_reserved_hotkeys(settings)
    assert "Ctrl+Shift+V" in reserved or "ctrl+shift+v" in {h.lower() for h in reserved}


def test_keystroke_mode_blocked_when_disabled(exec_env, monkeypatch):
    settings, store, _registry, _events, executor, _notices = exec_env
    settings.macro_keystroke_enabled = False
    macro = _macro(body="type me", output_mode=OUTPUT_KEYSTROKE)
    store.upsert(macro)
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.deliver_text_keystrokes",
        lambda *a, **k: PasteResult(True, "ok"),
    )
    result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    assert not result.ok
    assert result.reason == "keystroke_mode_disabled"


def test_blocked_or_cancel_path_does_not_mutate_clipboard(exec_env, monkeypatch):
    """Failed prepare (missing vars) must not touch clipboard."""
    _settings, store, _registry, _events, executor, _notices = exec_env
    macro = _macro(body="Hello {selected_text}")
    store.upsert(macro)
    calls: list[str] = []
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.set_clipboard_text",
        lambda t: calls.append(t) or True,
    )
    result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    assert not result.ok
    assert calls == []


def test_text_shortcuts_listener_disabled_when_setting_off(exec_env):
    from cache_vault.core.macro_shortcut_listener import TextShortcutListener

    settings, store, *_ = exec_env
    settings.macro_text_shortcuts_enabled = False
    listener = TextShortcutListener(on_match=lambda *a: None)
    listener.update(store.load_all(), enabled=False)
    assert not listener.active


def test_run_count_updates_after_execution(exec_env, monkeypatch):
    settings, store, _registry, _events, executor, _notices = exec_env
    macro = _macro(body="count")
    store.upsert(macro)
    monkeypatch.setattr("cache_vault.core.macro_execute.set_clipboard_text", lambda _t: True)
    monkeypatch.setattr(
        "cache_vault.core.macro_execute.deliver_ctrl_v",
        lambda _hwnd: PasteResult(True, "ok"),
    )
    executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=1)
    updated = store.get("m1")
    assert updated.run_count == 1
    assert updated.last_used_at


def test_find_macros_for_hotkey_respects_enabled():
    macros = [
        _macro(id="on", trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+shift+9"),
        _macro(id="off", enabled=False, trigger_type=TRIGGER_HOTKEY, trigger_value="ctrl+shift+9"),
    ]
    hits = find_macros_for_hotkey(macros, "ctrl+shift+9")
    assert len(hits) == 1
    assert hits[0].id == "on"
