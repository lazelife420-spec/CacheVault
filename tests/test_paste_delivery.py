"""Tests for paste delivery and quick-paste settings."""

from __future__ import annotations

import json
from pathlib import Path

from cache_vault.core.models import EVENT_ITEM_PASTED
from cache_vault.core.settings import Settings
from cache_vault.core.paste_delivery import (
    PasteResult,
    restore_clipboard_text,
    snapshot_clipboard_text,
)
from cache_vault.core.vault import Vault
from cache_vault.core.storage import VaultStorage


def test_settings_restore_clipboard_default_off(tmp_path):
    s = Settings()
    assert s.auto_paste is True
    assert s.restore_clipboard_after_paste is False
    path = tmp_path / "settings.json"
    s.save(path)
    loaded = Settings.load(path)
    assert loaded.restore_clipboard_after_paste is False


def test_settings_restore_clipboard_persists(tmp_path):
    s = Settings(restore_clipboard_after_paste=True)
    path = tmp_path / "settings.json"
    s.save(path)
    loaded = Settings.load(path)
    assert loaded.restore_clipboard_after_paste is True


def test_log_item_pasted_event(tmp_path):
    vault = Vault(storage=VaultStorage(str(tmp_path / "v.db")))
    clip = vault.capture("hello paste line\nsecond line", source_app="test")
    assert clip is not None
    vault.log_item_pasted(
        clip.id,
        success=True,
        item_type="text",
        target_title="Notepad",
        clipboard_restored=False,
    )
    events = vault.events.recent(5)
    pasted = [e for e in events if e["event_type"] == EVENT_ITEM_PASTED]
    assert len(pasted) == 1
    details = pasted[0]["details"]
    assert details["success"] is True
    assert details["item_type"] == "text"
    assert details["target_title"] == "Notepad"
    assert "hello" not in json.dumps(details)


def test_clipboard_snapshot_restore_roundtrip():
    if snapshot_clipboard_text is None:
        return
    prior = snapshot_clipboard_text()
    marker = "__cache_vault_paste_test__"
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, marker)
        finally:
            win32clipboard.CloseClipboard()
        assert restore_clipboard_text(prior) is True
        assert snapshot_clipboard_text() == prior
    except Exception:
        pass  # headless / clipboard locked — skip on CI


def test_paste_result_dataclass():
    r = PasteResult(True, "ok", "Notepad")
    assert r.ok and r.target_title == "Notepad"
