"""Proof-backed export zip — manifest, SHA256SUMS, receipts."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import file_sha256, receipts_dir
from cache_vault.core.exports import create_proof_zip, verify_zip_hashes
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
    assert any(n.startswith("items/") for n in names)


def test_manifest_and_sums_validate(vault_env, tmp_path):
    vault, _ = vault_env
    clip = vault.capture("validate me", source_app="test")
    dest = tmp_path / "proof.zip"
    vault.export_proof_zip([clip.id], str(dest))
    ok, errors = verify_zip_hashes(dest)
    assert ok, errors
    manifest = json.loads(zipfile.ZipFile(dest).read("manifest.json"))
    assert manifest["sha256sums_included"] is True
    assert manifest["manifest_included"] is True
    assert manifest["export_id"]


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
