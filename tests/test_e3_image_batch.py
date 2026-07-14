"""Unit tests for Screenshot/Image Batch Actions (Chunk E3)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
import pytest

from cache_vault.core import models
from cache_vault.ui.shell import CacheVaultApp


class FakeVault:
    def __init__(self):
        self.storage = FakeStorage()
        self.events = FakeEvents()
        self._exported_zip = None

    def copied_again_image(self, clip_id: str) -> bytes | None:
        return b"fake-png-bytes" if clip_id in self.storage.clips else None

    def export_proof_zip(self, ids: list[str], dest_zip: str):
        self._exported_zip = (ids, dest_zip)
        return SimpleNamespace(success=True)


class FakeStorage:
    def __init__(self):
        self.clips = {}
        self.records = {}
        self.asset_bytes = {}

    def get_clip(self, clip_id: str):
        return self.clips.get(clip_id)

    def load_clip_asset_bytes(self, clip_id: str):
        return self.asset_bytes.get(clip_id)

    def get_asset_record(self, clip_id: str):
        return self.records.get(clip_id)


class FakeEvents:
    def __init__(self):
        self.records = []

    def record(self, event_type: str, clip_id: str | None, payload: dict) -> None:
        self.records.append((event_type, clip_id, payload))


def _app_stub(vault):
    app = object.__new__(CacheVaultApp)
    app.vault = vault
    app._selected_clip_ids = []
    app._clipboard = []
    app._toasts = []
    app._copied_content = []
    app._copied_images = []

    app._guard_unlocked = lambda: True
    app.clipboard_clear = lambda: app._clipboard.clear()
    app.clipboard_append = lambda s: app._clipboard.append(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._monitor = SimpleNamespace(
        note_local_copy=lambda s: app._copied_content.append(s),
        note_local_copy_image=lambda img: app._copied_images.append(img),
    )
    return app


def _clip(clip_id: str, classification: str, content_type: str, title: str | None = None):
    return SimpleNamespace(
        id=clip_id,
        classification=classification,
        content_type=content_type,
        title=title,
    )


def test_bulk_save_images(monkeypatch, tmp_path):
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot A")
    c2 = _clip("c2", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot B")
    vault.storage.clips = {"c1": c1, "c2": c2}
    vault.storage.asset_bytes = {"c1": (b"png-bytes-1", "image/png"), "c2": (b"png-bytes-2", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    # Mock tkinter filedialog to return a temporary directory path
    dest_dir = tmp_path / "saved_images"
    dest_dir.mkdir()
    
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(dest_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    app._bulk_save_images()

    # Check files are written on disk
    files = list(dest_dir.glob("*.png"))
    assert len(files) == 2
    filenames = {f.name for f in files}
    assert any("c1" in name for name in filenames)
    assert any("c2" in name for name in filenames)

    # Check toast and event log
    assert len(app._toasts) == 1
    assert "Saved 2 screenshots" in app._toasts[0]
    assert len(vault.events.records) == 1
    assert vault.events.records[0][0] == models.EVENT_COPIED_AGAIN


def test_bulk_export_zip(monkeypatch, tmp_path):
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot A")
    vault.storage.clips = {"c1": c1}
    vault.storage.asset_bytes = {"c1": (b"png-bytes-1", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_zip = tmp_path / "export.zip"
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    app._bulk_export_zip()

    # Verify zip was created
    assert dest_zip.exists()
    with zipfile.ZipFile(dest_zip, "r") as zf:
        names = zf.namelist()
        assert len(names) == 1
        assert names[0].endswith(".png")
        assert zf.read(names[0]) == b"png-bytes-1"


def test_bulk_copy_paths(monkeypatch, tmp_path):
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    vault.storage.clips = {"c1": c1}
    vault.storage.records = {"c1": SimpleNamespace(storage_name="asset1.png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    from cache_vault.core import image_assets
    monkeypatch.setattr(image_assets, "assets_dir", lambda: tmp_path / "assets")

    app._bulk_copy_paths()

    expected_path = str(tmp_path / "assets" / "asset1.png")
    assert len(app._clipboard) == 1
    assert app._clipboard[0] == expected_path
    assert app._toasts[0] == "Copied 1 file paths to clipboard."


def test_bulk_copy_images_primary_only(monkeypatch):
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    c2 = _clip("c2", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    from cache_vault.core import image_assets
    monkeypatch.setattr(image_assets, "write_clipboard_png", lambda b: True)

    app._bulk_copy_images()

    assert len(app._copied_images) == 1
    assert app._copied_images[0] == b"fake-png-bytes"
    # Toast warns about the skipped count
    assert "use Save PNGs or Export ZIP for the remaining 1 images" in app._toasts[0]


def test_bulk_export_bundle(monkeypatch, tmp_path):
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("c2", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    dest_zip = tmp_path / "bundle.zip"
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    app._bulk_export_bundle()

    assert vault._exported_zip == (["c1", "c2"], str(dest_zip))
    assert app._toasts[0] == f"Exported mixed bundle to {dest_zip}"
