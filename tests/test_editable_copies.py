"""Editable working copies — originals stay immutable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import (
    EditableCopyStore,
    file_sha256,
    receipts_dir,
    write_file_receipt,
)
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    storage = VaultStorage(":memory:")
    vault = Vault(storage=storage, settings=Settings())
    return vault, tmp_path


def test_create_copy_preserves_original_hash(vault_env):
    vault, tmp_path = vault_env
    original = tmp_path / "note.txt"
    original.write_text("hello original", encoding="utf-8")
    before = file_sha256(original)

    clip = vault.capture(str(original), source_app="test")
    assert clip is not None

    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    assert rec.revision == 1
    assert Path(rec.copy_path).is_file()
    assert file_sha256(original) == before
    assert rec.copy_hash == file_sha256(rec.copy_path)


def test_save_revision_after_edit(vault_env):
    vault, tmp_path = vault_env
    original = tmp_path / "draft.md"
    original.write_text("v1", encoding="utf-8")
    clip = vault.capture(str(original), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None

    Path(rec.copy_path).write_text("v2 edited", encoding="utf-8")
    saved = vault.save_editable_revision(clip.id)
    assert saved is not None
    assert saved.revision == 2
    assert Path(saved.copy_path).read_text(encoding="utf-8") == "v2 edited"
    assert original.read_text(encoding="utf-8") == "v1"


def test_delete_copy_leaves_original(vault_env):
    vault, tmp_path = vault_env
    original = tmp_path / "keep.txt"
    original.write_text("untouched", encoding="utf-8")
    clip = vault.capture(str(original), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None

    assert vault.delete_editable_copy(clip.id) is True
    assert original.read_text(encoding="utf-8") == "untouched"
    assert vault.latest_editable_copy(clip.id) is None


def test_events_and_file_receipts(vault_env, monkeypatch):
    vault, tmp_path = vault_env
    original = tmp_path / "receipt.txt"
    original.write_text("data", encoding="utf-8")
    clip = vault.capture(str(original), source_app="test")
    vault.create_editable_copy(clip.id)

    events = vault.events.recent(20)
    created = [e for e in events if e["event_type"] == models.EVENT_EDITABLE_COPY_CREATED]
    assert len(created) == 1
    assert created[0]["clip_id"] == clip.id

    receipt_files = list(receipts_dir().glob("editable_copy_created-*.json"))
    assert receipt_files
    payload = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert payload["action"] == "editable_copy_created"
    assert payload["clip_id"] == clip.id


def test_save_revision_noop_when_unchanged(vault_env):
    vault, tmp_path = vault_env
    original = tmp_path / "same.txt"
    original.write_text("same", encoding="utf-8")
    clip = vault.capture(str(original), source_app="test")
    vault.create_editable_copy(clip.id)
    assert vault.save_editable_revision(clip.id) is None


def test_store_schema_on_migrate(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    db_path = tmp_path / "vault.db"
    storage = VaultStorage(str(db_path))
    rows = storage.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='editable_copies'"
    ).fetchall()
    assert rows
    store = EditableCopyStore(storage.conn)
    assert store.latest_for_clip("missing") is None


def test_write_file_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = write_file_receipt("test_action", {"clip_id": "abc123"})
    assert path.is_file()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["action"] == "test_action"
    assert body["clip_id"] == "abc123"
