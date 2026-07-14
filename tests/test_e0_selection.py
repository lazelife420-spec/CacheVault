"""Unit tests for Smart Selection UX Foundation (Chunk E0)."""

from __future__ import annotations

from types import SimpleNamespace
from cache_vault.core import models
from cache_vault.core.selection import analyze_selection


def _link():
    return SimpleNamespace(classification=models.CLASS_LINK, content_type=models.CONTENT_TEXT)


def _image():
    return SimpleNamespace(classification=models.CLASS_IMAGE, content_type=models.CONTENT_IMAGE)


def _screenshot():
    # screenshot classification is also treated as image
    return SimpleNamespace(classification="screenshot", content_type=models.CONTENT_TEXT)


def _text():
    return SimpleNamespace(classification=models.CLASS_PLAIN, content_type=models.CONTENT_TEXT)


def test_empty_selection():
    summary = analyze_selection([])
    assert summary.selected_count == 0
    assert summary.selection_class == "empty"
    assert summary.summary_label == "No items selected"
    assert summary.available_actions == []
    assert summary.get_toast_message("copy") == "No items selected."


def test_link_only_selection():
    clips = [_link() for _ in range(5)]
    summary = analyze_selection(clips)
    assert summary.selected_count == 5
    assert summary.link_count == 5
    assert summary.image_count == 0
    assert summary.text_count == 0
    assert summary.selection_class == "link_only"
    assert summary.summary_label == "5 links"
    assert "Copy as Plain List" in summary.available_actions
    assert "Copy as Markdown" in summary.available_actions
    assert "Save to Safe" in summary.available_actions
    assert summary.get_toast_message("copy", "Markdown") == "Copied 5 links as Markdown"


def test_image_only_selection():
    clips = [_screenshot() for _ in range(3)]
    summary = analyze_selection(clips)
    assert summary.selected_count == 3
    assert summary.link_count == 0
    assert summary.image_count == 3
    assert summary.text_count == 0
    assert summary.selection_class == "image_only"
    assert summary.summary_label == "3 screenshots"
    assert "Copy PNG Files" in summary.available_actions
    assert "Save All As PNG" in summary.available_actions
    assert summary.get_toast_message("save_png") == "Saved 3 screenshots as PNG"


def test_text_only_selection():
    clips = [_text() for _ in range(2)]
    summary = analyze_selection(clips)
    assert summary.selected_count == 2
    assert summary.link_count == 0
    assert summary.image_count == 0
    assert summary.text_count == 2
    assert summary.selection_class == "text_only"
    assert summary.summary_label == "2 text clips"
    assert "Copy as Plain List" in summary.available_actions
    assert summary.get_toast_message("copy") == "Copied 2 text clips"


def test_mixed_selection():
    clips = (
        [_link() for _ in range(5)]
        + [_image() for _ in range(3)]
        + [_text() for _ in range(2)]
    )
    summary = analyze_selection(clips)
    assert summary.selected_count == 10
    assert summary.link_count == 5
    assert summary.image_count == 3
    assert summary.text_count == 2
    assert summary.selection_class == "mixed"
    assert summary.summary_label == "5 links · 3 screenshots · 2 text clips"
    assert "Export Bundle" in summary.available_actions
    assert "Copy Text + Links" in summary.available_actions
    assert "Save Screenshots" in summary.available_actions
    assert summary.get_toast_message("copy") == "Copied 10 selected items\n5 links · 3 screenshots · 2 text clips"
    assert summary.get_toast_message("export") == "Exported mixed bundle\n5 links · 3 screenshots · 2 text clips"


def test_receipt_metadata():
    clips = [_link(), _image()]
    summary = analyze_selection(clips)
    meta = summary.get_receipt_metadata("batch_action")
    assert meta["action"] == "batch_action"
    assert meta["selected_count"] == 2
    assert meta["link_count"] == 1
    assert meta["image_count"] == 1
    assert meta["text_count"] == 0
    assert meta["selection_class"] == "mixed"
    assert meta["summary"] == "1 link · 1 screenshot"


def test_mixed_copy_does_not_drop_screenshots():
    # Verification that the analyze_selection detects both screenshots and text
    # so that callers implementing copy paths can handle them without dropping.
    clips = [_text(), _screenshot()]
    summary = analyze_selection(clips)
    assert summary.image_count == 1
    assert summary.text_count == 1
    assert summary.selection_class == "mixed"
