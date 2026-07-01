from __future__ import annotations

import datetime
from cache_vault.ui.clip_list import _short_time

def test_short_time_formatting():
    # 1. Test empty/null time handles gracefully
    assert _short_time("") == "—"
    assert _short_time(None) == "—"
    
    # 2. Test valid ISO timestamp formatting for current year
    now = datetime.datetime.now()
    dt = datetime.datetime(now.year, 6, 30, 18, 24)
    iso = dt.isoformat()
    # Should format to "Jun 30, 6:24 PM" if current year
    res = _short_time(iso)
    assert "Jun 30, 6:24 PM" in res
    
    # 3. Test valid ISO timestamp formatting for previous year
    dt_prev = datetime.datetime(2023, 12, 12, 9, 5)
    iso_prev = dt_prev.isoformat()
    # Should format to "Dec 12, 2023, 9:05 AM"
    res_prev = _short_time(iso_prev)
    assert "Dec 12, 2023, 9:05 AM" in res_prev


def test_preview_panel_image_metadata_extraction(vault):
    from cache_vault.ui.preview import PreviewPanel
    from cache_vault.core import models

    # Create dummy image clip and mock actions to simulate panel
    clip_id = "test-image-clip"
    dummy_meta = {
        "sha256": "abcdef",
        "size_bytes": 10240,
        "width": 1920,
        "height": 1080,
        "original_name": "screenshot_2026.png",
    }
    
    actions = {
        "load_asset": lambda cid: (b"dummy_png_bytes", "image/png"),
        "asset_meta": lambda cid: dummy_meta,
    }

    panel = PreviewPanel(None, actions=actions)
    
    # Verify metadata-based hint formatting behaves safely
    class MockClip:
        id = clip_id
        classification = models.CLASS_IMAGE
        content_type = models.CONTENT_IMAGE
        title = "Test Screenshot"
        preview = ""
        content = ""
        is_sensitive = False

    panel._render_image_preview(MockClip())
    
    # Verify the hint label has filename, dims, and size
    hint_text = panel._image_hint.cget("text")
    assert "screenshot_2026.png" in hint_text
    assert "1920x1080" in hint_text
    assert "image/png" in hint_text
    
    # Clean up
    panel.destroy()
