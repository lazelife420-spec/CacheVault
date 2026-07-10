import pytest
import tkinter as tk
import customtkinter as ctk
from cache_vault.core import models, clip_metadata, storage as S
from cache_vault.core.models import Clip
from cache_vault.ui.clip_list import ClipList
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.preview import PreviewPanel
from cache_vault.ui.home_dashboard import HomeDashboard
from cache_vault.ui.clip_context import open_clip_menu

def _clip(content: str, **kw) -> Clip:
    defaults = {
        "id": "clip-123",
        "content": content,
        "preview": content,
        "classification": models.CLASS_PLAIN,
        "content_type": models.CONTENT_TEXT,
        "created_at": "2026-07-09T22:00:00+00:00",
        "updated_at": "2026-07-09T22:00:00+00:00",
        "content_hash": "dummy_hash",
        "safe_id": "default",
        "safe_name": "Default Safe",
    }
    defaults.update(kw)
    return Clip(**defaults)

class DummyRecord:
    width = 1920
    height = 1080

class DummyStorage:
    def asset_storage_ready(self) -> bool:
        return True
    def get_asset_record(self, clip_id: str):
        return DummyRecord()

def test_ux_metadata_formatting():
    """Verify that source_summary_line correctly formats source, captured time, age and safe."""
    clip = _clip("plain text", source_app="Chrome", is_pinned=False)
    # Mocking now for deterministic test
    formatted = clip_metadata.source_summary_line(clip, None)
    assert "Chrome" in formatted
    assert "Default Safe" in formatted

    # Test screenshot dimension resolution
    clip_img = _clip("img content", classification=models.CLASS_IMAGE, content_type=models.CONTENT_IMAGE, source_app="Brave")
    formatted_img = clip_metadata.source_summary_line(clip_img, DummyStorage())
    assert "Screenshot" in formatted_img
    assert "1920" in formatted_img
    assert "1080" in formatted_img

def test_ux_double_click_callback(tk_root):
    """Verify double-click callback is configured and fired correctly in ClipList and ClipGrid."""
    clicked_clips = []

    clist = ClipList(
        tk_root,
        on_select=lambda _c: None,
        on_double_click=lambda c: clicked_clips.append(c),
    )
    c1 = _clip("c1")
    clist.render([c1])

    # Simulate double click event
    event = tk.Event()
    clist._double_click(event, c1)
    assert len(clicked_clips) == 1
    assert clicked_clips[0].id == "clip-123"

    cgrid = ClipGrid(
        tk_root,
        on_select=lambda _c: None,
        on_double_click=lambda c: clicked_clips.append(c),
    )
    cgrid._on_double_click = lambda c: clicked_clips.append(c)
    cgrid._double_click(event, c1)
    assert len(clicked_clips) == 2

def test_ux_preview_panel_stacked_layout(tk_root):
    """Verify that the preview panel uses a stacked layout packing all sections."""
    panel = PreviewPanel(tk_root, actions={})
    c = _clip("preview text")
    panel.show(c)

    # Verify segmented button tabs are hidden (not packed)
    with pytest.raises(Exception):
        panel._tabs.pack_info()

    # Verify body (text preview) is packed
    assert "fill" in panel._body.pack_info()
    # Verify metadata, seal and history are packed/active in hierarchy
    assert "fill" in panel._meta_title.pack_info()
    assert "fill" in panel._meta.pack_info()
    assert "fill" in panel._usage_title.pack_info()
    assert "fill" in panel._usage.pack_info()

    panel.destroy()

def test_ux_dashboard_command_center(tk_root):
    """Verify redesigned Command Center titles, actions, and custom curated list rendering."""
    dashboard = HomeDashboard(
        tk_root,
        on_filter=lambda _k: None,
        on_open_receipts=lambda: None,
        on_mobile_settings=lambda: None,
        on_pair_android=lambda: None,
        on_export=lambda: None,
        on_select_clip=lambda _c: None,
        on_copy=lambda _id: None,
    )
    summary = {
        "all": 5, "favorites": 1, "screenshots": 1, "duplicates": 0,
        "recently_removed": 0, "receipts": 1, "sensitive": 1, "expired": 0,
        "capture_paused": False, "mobile_enabled": False,
    }

    recent = [_clip("recent 1", id="recent-1")]
    today = [_clip("today 1", id="today-1", created_at=models.now_iso())]
    images = [_clip("img 1", id="img-1", classification=models.CLASS_IMAGE, content_type=models.CONTENT_IMAGE)]
    links = [_clip("link 1", id="link-1", classification=models.CLASS_LINK)]
    receipts = [_clip("receipt 1", id="receipt-1", content_hash="hash1")]
    sensitive = [_clip("sensitive 1", id="sensitive-1", is_sensitive=True)]

    dashboard.render(
        summary,
        recent,
        [],
        images,
        today_clips=today,
        link_clips=links,
        receipts=receipts,
        sensitive_items=sensitive
    )

    dashboard.update_idletasks()

    # Find all titles rendered by section titles (recursively scanning the real UI structure)
    section_titles = []
    def _scan_labels(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                font = child.cget("font")
                weight = font.cget("weight") if hasattr(font, "cget") else ""
                if weight == "bold":
                    text = child.cget("text")
                    if text in ("Recent Active Clip", "Clips Captured Today", "Images & Screenshots", "Recent Links", "Stamped Proof Receipts", "Sensitive / Expiring Items"):
                        section_titles.append(text)
            _scan_labels(child)
    _scan_labels(dashboard._body)

    assert "Recent Active Clip" in section_titles
    assert "Clips Captured Today" in section_titles
    assert "Images & Screenshots" in section_titles
    assert "Recent Links" in section_titles
    assert "Stamped Proof Receipts" in section_titles
    assert "Sensitive / Expiring Items" in section_titles

    dashboard.destroy()
