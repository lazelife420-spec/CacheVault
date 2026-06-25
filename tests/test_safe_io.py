from __future__ import annotations

import json

import pytest

from cache_vault.core import safe_io


def _list_tmp(d):
    return [p.name for p in d.iterdir() if p.suffix == ".tmp" or ".tmp" in p.name]


def test_atomic_write_creates_file_no_temp_left(tmp_path):
    target = tmp_path / "sub" / "data.json"
    safe_io.atomic_write_text(target, '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert _list_tmp(target.parent) == []  # no leftover temp files


def test_keep_backup_preserves_last_known_good(tmp_path):
    target = tmp_path / "settings.json"
    safe_io.atomic_write_text(target, "v1", keep_backup=True)  # no prior file -> no bak
    assert not safe_io.backup_path(target).exists()
    safe_io.atomic_write_text(target, "v2", keep_backup=True)  # backs up v1
    assert target.read_text(encoding="utf-8") == "v2"
    assert safe_io.backup_path(target).read_text(encoding="utf-8") == "v1"


def test_failed_replace_leaves_original_intact(tmp_path, monkeypatch):
    target = tmp_path / "data.json"
    target.write_text("ORIGINAL", encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("simulated crash during replace")

    monkeypatch.setattr(safe_io.os, "replace", boom)
    with pytest.raises(OSError):
        safe_io.atomic_write_text(target, "NEW")

    assert target.read_text(encoding="utf-8") == "ORIGINAL"  # never half-written
    assert _list_tmp(tmp_path) == []  # temp cleaned up even on failure


def test_quarantine_corrupt_moves_and_preserves(tmp_path):
    target = tmp_path / "command_center.json"
    target.write_text("{ broken json", encoding="utf-8")
    moved = safe_io.quarantine_corrupt(target)
    assert moved is not None and moved.exists()
    assert moved.name.startswith("command_center.json.corrupt-")
    assert moved.read_text(encoding="utf-8") == "{ broken json"  # preserved
    assert not target.exists()  # original moved aside, not deleted in place


def test_quarantine_missing_file_returns_none(tmp_path):
    assert safe_io.quarantine_corrupt(tmp_path / "nope.json") is None


# --- store-level recovery ----------------------------------------------------
def test_command_center_store_quarantines_corrupt(tmp_path):
    from cache_vault.core.command_center import HotkeyActionStore

    path = tmp_path / "command_center.json"
    path.write_text("}{ not json", encoding="utf-8")
    store = HotkeyActionStore(path)

    assert store.load_all() == []  # recovers to empty, no crash
    quarantined = list(tmp_path.glob("command_center.json.corrupt-*"))
    assert len(quarantined) == 1  # broken file preserved
    assert not path.exists()


def test_command_center_save_is_atomic_with_backup(tmp_path):
    from cache_vault.core.command_center import HotkeyAction, HotkeyActionStore

    path = tmp_path / "command_center.json"
    store = HotkeyActionStore(path)
    store.upsert(HotkeyAction(name="A", hotkey="ctrl+alt+a"))
    store.upsert(HotkeyAction(name="B", hotkey="ctrl+alt+b"))  # second save -> .bak

    assert path.is_file()
    assert safe_io.backup_path(path).is_file()
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


def test_settings_recovers_and_quarantines_corrupt(tmp_path):
    from cache_vault.core.settings import Settings

    path = tmp_path / "settings.json"
    path.write_text("totally not json", encoding="utf-8")
    s = Settings.load(path)

    assert isinstance(s, Settings)
    assert s.auto_capture_enabled is True  # safe defaults
    assert getattr(s, "_persist_path", None) == path
    assert len(list(tmp_path.glob("settings.json.corrupt-*"))) == 1


def test_macro_store_quarantines_corrupt(tmp_path):
    from cache_vault.core.vault_macros import MacroStore

    path = tmp_path / "macros.json"
    path.write_text("<broken>", encoding="utf-8")
    store = MacroStore(path)

    assert store.load_all() == []
    assert len(list(tmp_path.glob("macros.json.corrupt-*"))) == 1
