"""Capture rules, Safes, hotkey paths, receipts, and manifest metadata."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cache_vault.core import models, sensitive
from cache_vault.core.capture_receipts import record_armed_receipt
from cache_vault.core.capture_rules import CaptureController
from cache_vault.core.editable_copies import receipts_dir
from cache_vault.core.exports import create_proof_zip
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    storage = VaultStorage(":memory:")
    vault = Vault(storage=storage, settings=Settings())
    return vault, tmp_path


def test_auto_capture_on_saves(vault_env):
    vault, _ = vault_env
    vault.settings.auto_capture_enabled = True
    clip = vault.capture("auto on clip", source_app="test.exe")
    assert clip is not None
    events = vault.events.recent(5)
    assert any(e["event_type"] == models.EVENT_CLIPBOARD_AUTO_SAVED for e in events)


def test_auto_capture_off_does_not_save(vault_env):
    vault, _ = vault_env
    vault.settings.auto_capture_enabled = False
    clip = vault.capture("should not save", source_app="test.exe")
    assert clip is None
    assert vault.storage.counts()["all"] == 0


def test_manual_save_to_default_safe(vault_env):
    vault, _ = vault_env
    vault.settings.auto_capture_enabled = False
    clip = vault.capture_manual("manual save", source_app="test.exe")
    assert clip is not None
    assert clip.safe_id == vault.settings.default_safe_id
    assert clip.capture_mode == models.CAPTURE_MANUAL_SAVE_HOTKEY
    events = vault.events.recent(5)
    assert any(e["event_type"] == models.EVENT_CLIPBOARD_MANUAL_SAVED for e in events)


def test_armed_next_copy_saves_once(vault_env):
    vault, _ = vault_env
    ctrl = CaptureController(lambda: vault.settings)
    vault.settings.auto_capture_enabled = False
    ctrl.arm_next_copy("temporary", "Temporary Safe")
    sid, _ = ctrl.consume_armed()
    assert sid == "temporary"
    clip = vault.capture(
        "armed once",
        capture_mode=models.CAPTURE_ARMED_NEXT_COPY,
        safe_id=sid,
        force=True,
    )
    assert clip is not None
    assert clip.safe_id == "temporary"
    assert clip.capture_mode == models.CAPTURE_ARMED_NEXT_COPY
    assert ctrl.consume_armed() is None
    second = vault.capture(
        "armed twice",
        capture_mode=models.CAPTURE_ARMED_NEXT_COPY,
        safe_id="temporary",
        force=True,
    )
    assert second is not None
    assert vault.storage.counts()["all"] == 2


def test_ignore_next_copy(vault_env):
    vault, _ = vault_env
    ctrl = CaptureController(lambda: vault.settings)
    ctrl.arm_ignore_next()
    assert ctrl.consume_ignore() is True
    assert ctrl.consume_ignore() is False
    vault.settings.auto_capture_enabled = True
    ctrl2 = CaptureController(lambda: vault.settings)
    assert not ctrl2.consume_ignore()
    clip = vault.capture("normal after ignore consumed")
    assert clip is not None


def test_safe_metadata_on_item(vault_env):
    vault, _ = vault_env
    work = vault.create_safe("Work Safe")
    clip = vault.capture_manual("work item", safe_id=work.id)
    assert clip.safe_id == work.id
    assert clip.safe_name == "Work Safe"
    stored = vault.storage.get_clip(clip.id)
    assert stored.safe_name == "Work Safe"


def test_receipt_created_for_save_and_ignore(vault_env, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    vault, _ = vault_env
    vault.capture("receipt test", source_app="app")
    files = list(receipts_dir().glob("clipboard_auto_saved-*.json"))
    assert files
    body = json.loads(files[0].read_text(encoding="utf-8"))
    assert body["action"] == "clipboard_auto_saved"
    assert "content" not in body

    record_armed_receipt(vault.events, safe_id="default", safe_name="Default Safe")
    armed_files = list(receipts_dir().glob("clipboard_next_copy_armed-*.json"))
    assert armed_files


def test_manifest_includes_safe_metadata(vault_env, tmp_path):
    vault, root = vault_env
    clip = vault.capture_manual("manifest safe", safe_id="default")
    dest = root / "proof.zip"
    result = vault.export_proof_zip([clip.id], str(dest))
    assert result.success
    manifest = json.loads(zipfile.ZipFile(dest).read("manifest.json"))
    item = manifest["items"][0]
    assert item["safe_id"] == "default"
    assert item["capture_mode"] == models.CAPTURE_MANUAL_SAVE_HOTKEY
    assert item["auto_saved"] is False


def test_move_to_safe_receipt(vault_env):
    vault, _ = vault_env
    clip = vault.capture("move me")
    work = vault.create_safe("Receipts Safe")
    updated = vault.move_to_safe(clip.id, work.id)
    assert updated.capture_mode == models.CAPTURE_MOVED_TO_SAFE
    events = vault.events.recent(10)
    assert any(e["event_type"] == models.EVENT_ITEM_MOVED_TO_SAFE for e in events)


def test_sensitive_auto_blocked(vault_env):
    vault, _ = vault_env
    vault.settings.block_sensitive_auto_capture = True
    secret = "sk-" + "a" * 32
    assert sensitive.detect(secret).is_sensitive
    clip = vault.capture(secret, source_app="test")
    assert clip is None
    events = vault.events.recent(5)
    assert any(
        e["event_type"] == models.EVENT_CLIPBOARD_SENSITIVE_BLOCKED for e in events
    )


def test_manual_save_sensitive_allowed(vault_env):
    vault, _ = vault_env
    vault.settings.block_sensitive_auto_capture = True
    secret = "sk-" + "b" * 32
    clip = vault.capture_manual(secret, safe_id="default")
    assert clip is not None


def test_max_auto_capture_bytes(vault_env):
    vault, _ = vault_env
    vault.settings.max_auto_capture_bytes = 5
    assert vault.capture("tiny") is not None
    assert vault.capture("this string is too long for auto") is None


def test_editable_copy_still_works(vault_env, tmp_path):
    vault, root = vault_env
    original = root / "note.txt"
    original.write_text("original", encoding="utf-8")
    clip = vault.capture(str(original))
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None


def test_html_bundle_export_still_works(vault_env, tmp_path):
    vault, root = vault_env
    html = root / "page.html"
    html.write_text("<html><body>hi</body></html>", encoding="utf-8")
    clip = vault.capture(str(html))
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    dest = root / "bundle.zip"
    result = vault.export_proof_zip([clip.id], str(dest), mode="html_bundle")
    assert result.success
