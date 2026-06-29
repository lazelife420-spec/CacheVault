"""Unit tests for Desktop Batch Receipt Polish (Chunk E5)."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from cache_vault.core import models
from cache_vault.ui.shell import CacheVaultApp


class FakeVault:
    def __init__(self):
        self.storage = FakeStorage()
        self.events = FakeEvents()

    def copied_again(self, clip_id: str) -> str | None:
        c = self.storage.get_clip(clip_id)
        return c.content if c else None

    def copied_again_image(self, clip_id: str) -> bytes | None:
        return b"fake-png"

    def export_proof_zip(self, ids: list[str], dest_zip: str):
        return SimpleNamespace(success=True)


class FakeStorage:
    def __init__(self):
        self.clips = {}
        self.asset_bytes = {}

    def get_clip(self, clip_id: str):
        return self.clips.get(clip_id)

    def load_clip_asset_bytes(self, clip_id: str):
        return self.asset_bytes.get(clip_id)

    def get_asset_record(self, clip_id: str):
        return SimpleNamespace(storage_name="test.png")


class FakeEvents:
    def __init__(self):
        self.records = []

    def record(self, event_type: str, clip_id: str | None, payload: dict) -> None:
        self.records.append((event_type, clip_id, payload))


def _clip(clip_id: str, classification: str, content_type: str, content: str = ""):
    return SimpleNamespace(
        id=clip_id,
        classification=classification,
        content_type=content_type,
        content=content,
        title=None,
    )


def _app_stub(vault):
    app = object.__new__(CacheVaultApp)
    app.vault = vault
    app._selected_clip_ids = []
    app._clipboard = []
    app._toasts = []
    app._copied_content = []
    app._copied_images = []
    app._receipt_logs = []

    app._guard_unlocked = lambda: True
    app.clipboard_clear = lambda: app._clipboard.clear()
    app.clipboard_append = lambda s: app._clipboard.append(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._monitor = SimpleNamespace(
        note_local_copy=lambda s: app._copied_content.append(s),
        note_local_copy_image=lambda img: app._copied_images.append(img),
    )
    return app


def test_batch_copy_selected_receipt(monkeypatch):
    """Verify clean links-only copy records batch_copy_selected as completed."""
    vault = FakeVault()
    vault.storage.clips = {
        "c1": _clip("c1", models.CLASS_LINK, models.CONTENT_TEXT, "https://example.com/1"),
        "c2": _clip("c2", models.CLASS_LINK, models.CONTENT_TEXT, "https://example.com/2"),
    }
    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    receipts = []
    from cache_vault.core import editable_copies
    monkeypatch.setattr(editable_copies, "write_file_receipt", lambda name, meta: receipts.append((name, meta)))

    app._bulk_copy_format("markdown")

    assert len(receipts) == 1
    name, meta = receipts[0]
    assert name == "batch_copy_selected"
    assert meta["action"] == "batch_copy_selected"
    assert meta["transfer_status"] == "completed"
    assert meta["item_breakdown"] == {"links": 2, "text": 0, "images": 0}


def test_batch_copy_text_parts_receipt(monkeypatch):
    """Verify mixed copy with skipped screenshots records batch_copy_text_parts as partial."""
    vault = FakeVault()
    vault.storage.clips = {
        "c1": _clip("c1", models.CLASS_LINK, models.CONTENT_TEXT, "https://example.com/1"),
        "c2": _clip("c2", models.CLASS_IMAGE, models.CONTENT_IMAGE),
    }
    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    receipts = []
    from cache_vault.core import editable_copies
    monkeypatch.setattr(editable_copies, "write_file_receipt", lambda name, meta: receipts.append((name, meta)))

    app._bulk_copy_format("plain")

    assert len(receipts) == 1
    name, meta = receipts[0]
    assert name == "batch_copy_text_parts"
    assert meta["action"] == "batch_copy_text_parts"
    assert meta["transfer_status"] == "partial"
    assert meta["copied_count"] == 1
    assert meta["skipped_count"] == 1
    assert meta["skipped_types"] == ["image"]
    assert meta["item_breakdown"] == {"links": 1, "text": 0, "images": 1}


def test_batch_export_images_png_receipt(monkeypatch, tmp_path):
    """Verify image folder saving records batch_export_images with png format."""
    vault = FakeVault()
    vault.storage.clips = {
        "c1": _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE),
    }
    vault.storage.asset_bytes = {"c1": (b"png-bytes", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_dir = tmp_path / "images"
    dest_dir.mkdir()

    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(dest_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    receipts = []
    from cache_vault.core import editable_copies
    monkeypatch.setattr(editable_copies, "write_file_receipt", lambda name, meta: receipts.append((name, meta)))

    app._bulk_save_images()

    assert len(receipts) == 1
    name, meta = receipts[0]
    assert name == "batch_export_images"
    assert meta["format"] == "png"
    assert meta["transfer_status"] == "completed"
    assert meta["item_breakdown"] == {"images": 1}


def test_batch_export_images_zip_receipt(monkeypatch, tmp_path):
    """Verify image zip export records batch_export_images with zip format."""
    vault = FakeVault()
    vault.storage.clips = {
        "c1": _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE),
    }
    vault.storage.asset_bytes = {"c1": (b"png-bytes", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_zip = tmp_path / "export.zip"

    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    receipts = []
    from cache_vault.core import editable_copies
    monkeypatch.setattr(editable_copies, "write_file_receipt", lambda name, meta: receipts.append((name, meta)))

    app._bulk_export_zip()

    assert len(receipts) == 1
    name, meta = receipts[0]
    assert name == "batch_export_images"
    assert meta["format"] == "zip"
    assert meta["transfer_status"] == "completed"
    assert meta["item_breakdown"] == {"images": 1}


def test_batch_export_bundle_receipt(monkeypatch, tmp_path):
    """Verify mixed bundle ZIP export records batch_export_bundle with zip format."""
    vault = FakeVault()
    vault.storage.clips = {
        "c1": _clip("c1", models.CLASS_LINK, models.CONTENT_TEXT, "https://example.com"),
        "c2": _clip("c2", models.CLASS_IMAGE, models.CONTENT_IMAGE),
    }

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    dest_zip = tmp_path / "bundle.zip"

    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    receipts = []
    from cache_vault.core import editable_copies
    monkeypatch.setattr(editable_copies, "write_file_receipt", lambda name, meta: receipts.append((name, meta)))

    app._bulk_export_bundle()

    assert len(receipts) == 1
    name, meta = receipts[0]
    assert name == "batch_export_bundle"
    assert meta["format"] == "zip"
    assert meta["transfer_status"] == "completed"
    assert meta["item_breakdown"] == {"links": 1, "text": 0, "images": 1}
