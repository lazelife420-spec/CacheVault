import pytest
import os
import zipfile
from unittest.mock import MagicMock
from cache_vault.core import models, selection, contextmenu, display_metadata
from cache_vault.core.models import Clip
from cache_vault.ui import batch_actions

def test_mixed_selection_type_breakdown():
    c1 = Clip(id="c1", content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE)
    c2 = Clip(id="c2", content_type=models.CONTENT_TEXT, classification=models.CLASS_PLAIN, content="Hello")
    c3 = Clip(id="c3", content_type=models.CONTENT_TEXT, classification=models.CLASS_LINK, content="https://google.com")

    summary = selection.analyze_selection([c1, c2, c3])
    assert summary.selected_count == 3
    assert summary.image_count == 1
    assert summary.text_count == 1
    assert summary.link_count == 1
    assert summary.selection_class == "mixed"
    assert "3 selected" in summary.summary_label
    assert "1 screenshot" in summary.summary_label
    assert "1 text clip" in summary.summary_label
    assert "1 link" in summary.summary_label


def test_local_timezone_conversion():
    # Test converting UTC string
    utc_str = "2026-07-01T18:00:00Z"
    local_dt = display_metadata.to_local_time(utc_str)
    # The timezone of the resulting datetime should be local
    formatted = display_metadata.format_display_time(utc_str)
    assert len(formatted) > 0
    clip = Clip(created_at=utc_str, content_type=models.CONTENT_IMAGE, source_app="Chrome.exe")
    meta = display_metadata.format_full_metadata(clip)
    assert "Chrome.exe" in meta


def test_dynamic_menu_labels():
    c1 = Clip(id="c1", content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE)
    c2 = Clip(id="c2", content_type=models.CONTENT_TEXT, classification=models.CLASS_PLAIN, content="Text")

    items = contextmenu.clip_menu_items([c1, c2])
    labels = [item.label for item in items]
    assert any("Export 1 Screenshot to Folder" in l for l in labels)
    assert any("Export 1 Screenshot as ZIP" in l for l in labels)
    assert any("Copy 1 Text/Link Clip" in l for l in labels)


def test_mixed_zip_export(monkeypatch, tmp_path):
    class FakeStorage:
        def __init__(self):
            self.clips = {}
            self.asset_bytes = {}
        def get_clip(self, cid):
            return self.clips.get(cid)
        def load_clip_asset_bytes(self, cid):
            return self.asset_bytes.get(cid)

    class FakeVault:
        def __init__(self):
            self.storage = FakeStorage()
            self.events = MagicMock()

    class AppStub:
        def __init__(self, vault):
            self.vault = vault
            self._selected_clip_ids = []
            self._toasts = []
        def _guard_unlocked(self):
            return True
        def _show_toast(self, msg):
            self._toasts.append(msg)

    vault = FakeVault()
    c1 = Clip(id="c1", created_at="2026-07-01T12:00:00Z", content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE, title="Screen")
    c2 = Clip(id="c2", created_at="2026-07-01T12:00:00Z", content_type=models.CONTENT_TEXT, classification=models.CLASS_PLAIN, content="Hello World", title="MyText")

    vault.storage.clips = {"c1": c1, "c2": c2}
    vault.storage.asset_bytes = {"c1": (b"image-bytes", "image/png")}

    app = AppStub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    dest_zip = tmp_path / "mixed_export.zip"
    monkeypatch.setattr(batch_actions.filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    batch_actions.bulk_export_zip(app)

    assert dest_zip.exists()
    with zipfile.ZipFile(dest_zip, "r") as zf:
        names = zf.namelist()
        assert len(names) == 2
        img_name = [n for n in names if n.endswith(".png")][0]
        txt_name = [n for n in names if n.endswith(".txt")][0]
        assert zf.read(img_name) == b"image-bytes"
        assert zf.read(txt_name) == b"Hello World"
    assert "Exported 2 items to ZIP" in app._toasts[0]
