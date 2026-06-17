"""Proof-backed export zip — manifest, SHA256SUMS, receipts."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import file_sha256, receipts_dir
from cache_vault.core.exports import (
    create_export_pack,
    create_proof_zip,
    validate_manifest,
    verify_export_pack,
    verify_zip_hashes,
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


def test_export_text_clip_proof_zip(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("hello proof export", source_app="test")
    dest = tmp_path / "out.zip"
    result = vault.export_proof_zip([clip.id], str(dest))
    assert result.success
    assert dest.is_file()
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "manifest.json" in names
    assert "SHA256SUMS.txt" in names
    assert "EXPORT_RECEIPT.txt" in names
    assert "README.txt" in names
    assert any(n.startswith("items/") for n in names)


def test_manifest_and_sums_validate(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("validate me", source_app="test")
    dest = tmp_path / "proof.zip"
    vault.export_proof_zip([clip.id], str(dest))
    ok, errors = verify_zip_hashes(dest)
    assert ok, errors
    ok2, errors2 = verify_export_pack(dest)
    assert ok2, errors2
    manifest = json.loads(zipfile.ZipFile(dest).read("manifest.json"))
    assert manifest["sha256sums_included"] is True
    assert manifest["manifest_included"] is True
    assert manifest["receipts_included"] is True
    assert manifest["export_id"]
    assert not validate_manifest(manifest)


def test_export_editable_copy_uses_copy_not_original(vault_env, tmp_path):
    vault, root = vault_env
    original = root / "note.txt"
    original.write_text("original text", encoding="utf-8")
    before = file_sha256(original)
    clip = vault.capture(str(original), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    Path(rec.copy_path).write_text("edited copy", encoding="utf-8")

    dest = tmp_path / "copy.zip"
    result = vault.export_proof_zip([clip.id], str(dest), mode="editable_copy")
    assert result.success
    assert file_sha256(original) == before

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert any(n.startswith("editable_copies/") for n in names)
        assert b"edited copy" in zf.read(
            next(n for n in names if n.startswith("editable_copies/") and n.endswith(".txt"))
        )
    item = result.manifest["items"][0]
    assert item["export_source"] == "editable_copy"
    assert item["editable_copy"]["original_clip_id"] == clip.id
    assert item["editable_copy"]["used_editable_copy"] is True
    assert item["safe_id"] == clip.safe_id
    assert item["capture_mode"] == clip.capture_mode


def test_export_html_bundle_uses_copied_bundle(vault_env, tmp_path):
    vault, root = vault_env
    site = root / "site"
    (site / "css").mkdir(parents=True)
    html = site / "page.html"
    css = site / "css" / "style.css"
    css.write_text("body{}", encoding="utf-8")
    html.write_text('<link href="css/style.css">', encoding="utf-8")
    html_before = file_sha256(html)
    css_before = file_sha256(css)

    clip = vault.capture(str(html), source_app="test")
    vault.create_editable_copy(clip.id)
    dest = tmp_path / "html.zip"
    result = vault.export_proof_zip([clip.id], str(dest), mode="html_bundle")
    assert result.success
    assert file_sha256(html) == html_before
    assert file_sha256(css) == css_before

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert any(n.startswith("html_bundles/") for n in names)
        assert any("css/style.css" in n for n in names)
    assert result.manifest["items"][0]["export_source"] == "html_bundle_copy"
    hb = result.manifest["items"][0]["html_bundle"]
    assert hb["original_assets_not_fetched"] is True
    assert hb["original_assets_not_mutated"] is True
    assert hb["remote_assets_skipped"] >= 0
    assert hb.get("exported_html_path")


def test_missing_original_warning(vault_env, tmp_path):
    vault, root = vault_env
    missing = root / "gone.txt"
    clip = vault.capture(str(missing), source_app="test")
    dest = tmp_path / "missing.zip"
    result = vault.export_proof_zip(
        [clip.id], str(dest), include_original_files=True,
    )
    assert result.success
    assert any("missing" in w.lower() for w in result.warnings)


def test_export_receipt_created(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("receipt test", source_app="test")
    vault.export_proof_zip([clip.id], str(tmp_path / "r.zip"))
    events = vault.events.recent(10)
    assert any(e["event_type"] == models.EVENT_EXPORT_ZIP_CREATED for e in events)
    files = list(receipts_dir().glob("export_zip_created-*.json"))
    assert files


def test_original_unchanged_after_export(vault_env, tmp_path):
    vault, root = vault_env
    f = root / "keep.txt"
    f.write_text("unchanged", encoding="utf-8")
    before = file_sha256(f)
    clip = vault.capture(str(f), source_app="test")
    vault.export_proof_zip(
        [clip.id], str(tmp_path / "k.zip"), include_original_files=True,
    )
    assert file_sha256(f) == before


def test_export_events_include_export_id(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("event id", source_app="test")
    vault.export_proof_zip([clip.id], str(tmp_path / "e.zip"))
    exports = vault.list_export_events(5)
    assert exports
    assert exports[0]["details"].get("export_id")


def test_manifest_includes_safe_and_capture_metadata(vault_env, tmp_path):
    vault, _ = vault_env
    work = vault.create_safe("Work Safe")
    clip = vault.capture_manual("safe export item", safe_id=work.id)
    dest = tmp_path / "safe.zip"
    result = vault.export_proof_zip([clip.id], str(dest))
    item = result.manifest["items"][0]
    assert item["safe_id"] == work.id
    assert item["safe_name"] == "Work Safe"
    assert item["capture_mode"] == models.CAPTURE_MANUAL_SAVE_HOTKEY
    assert item["auto_saved"] is False
    assert result.manifest["safes"]


def test_receipts_folder_in_zip(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("with receipts", source_app="test")
    dest = tmp_path / "r.zip"
    vault.export_proof_zip([clip.id], str(dest))
    with zipfile.ZipFile(dest) as zf:
        assert any(n.startswith("receipts/") for n in zf.namelist())


def test_export_file_receipt_includes_safe_fields(vault_env, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    vault, _ = vault_env
    clip = vault.capture_manual("receipt fields", safe_id="default")
    vault.export_proof_zip([clip.id], str(tmp_path / "f.zip"))
    files = list(receipts_dir().glob("export_zip_created-*.json"))
    assert files
    body = json.loads(files[-1].read_text(encoding="utf-8"))
    assert body["manifest_included"] is True
    assert body["sha256sums_included"] is True
    assert body["receipts_included"] is True
    assert body.get("safe_id") == "default"
    assert "content" not in body


def test_create_export_pack_alias(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("alias test", source_app="test")
    dest = tmp_path / "alias.zip"
    result = create_export_pack(
        [clip],
        str(dest),
        events_for_clips=lambda _ids: vault.events.recent(50),
    )
    assert result.success


def test_core_exports_has_no_ui_imports():
    source = Path("cache_vault/core/exports.py").read_text(encoding="utf-8")
    assert "customtkinter" not in source
    assert "cache_vault.ui" not in source


def test_validate_manifest_rejects_invalid():
    errors = validate_manifest({"document_type": "wrong"})
    assert errors
