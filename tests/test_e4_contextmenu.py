"""Unit tests for Styled Smart Selection Action Menu (Chunk E4)."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from cache_vault.core import models
from cache_vault.core.contextmenu import clip_menu_items, MenuItem


from cache_vault.core.models import Clip

def _clip(content: str, classification: str, content_type: str, title: str | None = None) -> Clip:
    return Clip(
        id=f"clip_{content[:3]}",
        content=content,
        preview=content,
        classification=classification,
        content_type=content_type,
        title=title,
        is_pinned=False,
        deleted_at=None,
        capture_mode=models.CAPTURE_AUTO,
    )


def test_single_clip_nested_backward_compatibility():
    """Verify that a single clip still returns the legacy nested menu structure."""
    c = _clip("https://example.com", models.CLASS_LINK, models.CONTENT_TEXT, "Example")
    items = clip_menu_items(c)

    keys = [item.key for item in items]
    assert "primary" in keys
    assert "copy_clean" in keys
    assert "organize" in keys

    # Verify children exist in single-item path
    primary_sec = next(i for i in items if i.key == "primary")
    assert len(primary_sec.children) > 0


def test_multiple_links_flat_menu():
    """Verify multiple selected links returns flat list of link actions."""
    c1 = _clip("https://example.com/1", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("https://example.com/2", models.CLASS_LINK, models.CONTENT_TEXT)
    items = clip_menu_items([c1, c2])

    keys = [item.key for item in items]
    assert "copy_plain" in keys
    assert "copy_markdown" in keys
    assert "copy_numbered" in keys
    assert "move_safe" in keys
    assert "receipt" in keys
    assert "export" in keys
    assert "remove" in keys

    # Verify flat list, no children cascades
    for item in items:
        assert len(item.children) == 0


def test_multiple_images_flat_menu():
    """Verify multiple selected images/screenshots returns flat list of image actions."""
    c1 = _clip("asset1.png", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    c2 = _clip("asset2.png", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    items = clip_menu_items([c1, c2])

    keys = [item.key for item in items]
    assert "copy_pngs" not in keys
    assert "save_pngs" in keys
    assert "export_zip" in keys
    assert "copy_paths" in keys
    assert "view_proof" in keys
    assert "remove" in keys

    for item in items:
        assert len(item.children) == 0


def test_mixed_selection_flat_menu():
    """Verify mixed selection returns flat list of bundle/mixed actions."""
    c1 = _clip("https://example.com", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("asset1.png", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    items = clip_menu_items([c1, c2])

    keys = [item.key for item in items]
    assert "export_bundle" in keys
    assert "copy_text_links" in keys
    assert "save_screenshots" in keys
    assert "receipt" in keys
    assert "remove" in keys

    for item in items:
        assert len(item.children) == 0
