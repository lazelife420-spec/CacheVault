"""HTML bundle editable copies — originals and assets stay immutable."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cache_vault.core import models
from cache_vault.core.editable_copies import (
    KIND_HTML_BUNDLE,
    build_html_bundle,
    export_html_bundle_zip,
    file_sha256,
    is_html_path,
    receipts_dir,
    scan_html_assets,
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


def _write_site(root: Path) -> Path:
    (root / "css").mkdir()
    (root / "img").mkdir()
    (root / "css" / "site.css").write_text(
        "body { background: url('../img/bg.png'); }", encoding="utf-8",
    )
    (root / "img" / "bg.png").write_bytes(b"\x89PNG")
    html = root / "page.html"
    html.write_text(
        """<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="css/site.css">
</head><body>
<img src="img/bg.png">
<img src="img/missing.png">
<script src="https://cdn.example.com/lib.js"></script>
</body></html>""",
        encoding="utf-8",
    )
    return html


def test_is_html_path():
    assert is_html_path("C:\\site\\index.html")
    assert is_html_path("/tmp/x.htm")
    assert not is_html_path("C:\\site\\page.txt")


def test_scan_html_assets(tmp_path):
    html = _write_site(tmp_path)
    scan = scan_html_assets(html)
    assert "css/site.css" in scan.copied_assets
    assert "img/bg.png" in scan.copied_assets
    assert "img/missing.png" in scan.missing_assets
    assert any("cdn.example.com" in u for u in scan.remote_assets)


def test_build_html_bundle_copies_assets(tmp_path):
    html = _write_site(tmp_path)
    bundle_dir = tmp_path / "bundle"
    meta = build_html_bundle(html, bundle_dir)
    assert (bundle_dir / "page.html").is_file()
    assert (bundle_dir / "css" / "site.css").is_file()
    assert (bundle_dir / "img" / "bg.png").is_file()
    assert meta.missing_assets == ["img/missing.png"]
    assert len(meta.remote_assets) == 1


def test_html_copy_preserves_original_hashes(vault_env):
    vault, tmp_path = vault_env
    html = _write_site(tmp_path)
    css = tmp_path / "css" / "site.css"
    img = tmp_path / "img" / "bg.png"
    before = {
        "html": file_sha256(html),
        "css": file_sha256(css),
        "img": file_sha256(img),
    }
    clip = vault.capture(str(html), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    assert rec.kind == KIND_HTML_BUNDLE
    assert file_sha256(html) == before["html"]
    assert file_sha256(css) == before["css"]
    assert file_sha256(img) == before["img"]


def test_html_revision_changes_copy_hash_only(vault_env):
    vault, tmp_path = vault_env
    html = _write_site(tmp_path)
    before_html = file_sha256(html)
    clip = vault.capture(str(html), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    Path(rec.copy_path).write_text("<html><body>edited</body></html>", encoding="utf-8")
    saved = vault.save_editable_revision(clip.id)
    assert saved is not None
    assert saved.revision == 2
    assert file_sha256(html) == before_html
    assert saved.copy_hash != rec.copy_hash


def test_html_receipt_on_create(vault_env):
    vault, tmp_path = vault_env
    html = _write_site(tmp_path)
    clip = vault.capture(str(html), source_app="test")
    vault.create_editable_copy(clip.id)
    events = vault.events.recent(10)
    assert any(e["event_type"] == models.EVENT_EDITABLE_HTML_COPY_CREATED for e in events)
    files = list(receipts_dir().glob("editable_html_copy_created-*.json"))
    assert files
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["copied_asset_count"] >= 2
    assert payload["missing_asset_count"] >= 1
    assert payload["skipped_remote_asset_count"] >= 1


def test_delete_html_bundle_leaves_originals(vault_env):
    vault, tmp_path = vault_env
    html = _write_site(tmp_path)
    css = tmp_path / "css" / "site.css"
    before_css = file_sha256(css)
    clip = vault.capture(str(html), source_app="test")
    vault.create_editable_copy(clip.id)
    assert vault.delete_editable_copy(clip.id) is True
    assert html.is_file()
    assert file_sha256(css) == before_css


def test_export_html_bundle_zip(vault_env, tmp_path):
    vault, root = vault_env
    html = _write_site(root)
    clip = vault.capture(str(html), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    dest = tmp_path / "out.zip"
    export_html_bundle_zip(Path(rec.bundle_dir), dest)
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert "page.html" in names
        assert "css/site.css" in names


def test_normal_file_copy_still_works(vault_env):
    vault, tmp_path = vault_env
    f = tmp_path / "plain.txt"
    f.write_text("plain", encoding="utf-8")
    clip = vault.capture(str(f), source_app="test")
    rec = vault.create_editable_copy(clip.id)
    assert rec is not None
    assert rec.kind != KIND_HTML_BUNDLE
    events = vault.events.recent(5)
    assert any(e["event_type"] == models.EVENT_EDITABLE_COPY_CREATED for e in events)
