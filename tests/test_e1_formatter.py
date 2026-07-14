"""Unit tests for Shared Batch Link Formatter Foundation (Chunk E1)."""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from cache_vault.core import models
from cache_vault.core.formatter import format_batch_links, make_batch_link_receipt


def _clip(content: str, title: str | None = None, source_url: str | None = None):
    return SimpleNamespace(
        classification=models.CLASS_LINK,
        content_type=models.CONTENT_TEXT,
        content=content,
        title=title,
        source_url=source_url,
    )


def test_format_multiple_links_as_plain_list():
    clips = [
        _clip("https://example.com", "Example Domain"),
        _clip("https://google.com"),
    ]
    out = format_batch_links(clips, "plain")
    expected = "Example Domain - https://example.com\nhttps://google.com"
    assert out == expected


def test_format_multiple_links_as_markdown_list():
    clips = [
        _clip("https://example.com", "Example Domain"),
        _clip("https://google.com"),
    ]
    out = format_batch_links(clips, "markdown")
    expected = "- [Example Domain](https://example.com)\n- [https://google.com](https://google.com)"
    assert out == expected


def test_format_multiple_links_as_numbered_list():
    clips = [
        _clip("https://example.com", "Example Domain"),
        _clip("https://google.com"),
    ]
    out = format_batch_links(clips, "numbered")
    expected = "1. [Example Domain](https://example.com)\n2. [https://google.com](https://google.com)"
    assert out == expected


def test_format_preserves_selection_order():
    clips = [
        _clip("https://google.com", "Google"),
        _clip("https://example.com", "Example"),
    ]
    out = format_batch_links(clips, "plain")
    assert out == "Google - https://google.com\nExample - https://example.com"


def test_markdown_title_escaping():
    # Title has brackets [ and ]
    clips = [
        _clip("https://example.com/a(b)", "Example [Site]"),
    ]
    out = format_batch_links(clips, "markdown")
    # Brackets escaped to \[ and \]
    # URL parenthesis escaped to %29
    assert out == "- [Example \\[Site\\]](https://example.com/a(b%29)"


def test_duplicates_preserved_by_default():
    clips = [
        _clip("https://example.com", "Example"),
        _clip("https://example.com", "Example"),
    ]
    out = format_batch_links(clips, "plain")
    assert out == "Example - https://example.com\nExample - https://example.com"


def test_dedupe_removes_duplicates_when_requested():
    clips = [
        _clip("https://example.com", "Example First"),
        _clip("https://google.com", "Google"),
        _clip("https://example.com", "Example Second"),
    ]
    out = format_batch_links(clips, "plain", dedupe=True)
    # Only first occurrence of https://example.com is kept
    assert out == "Example First - https://example.com\nGoogle - https://google.com"


def test_empty_selection_raises_error():
    with pytest.raises(ValueError, match="No clips selected to format."):
        format_batch_links([], "plain")


def test_make_batch_link_receipt():
    meta = make_batch_link_receipt(
        action="extension_batch_link_copy",
        source="browser_extension",
        count=5,
        format_type="markdown",
        capture_mode="browser_extension",
        source_page="https://example.com/page",
        browser="Chrome",
        transfer_status="completed",
    )

    assert meta["action"] == "extension_batch_link_copy"
    assert meta["source"] == "browser_extension"
    assert meta["count"] == 5
    assert meta["format"] == "markdown"
    assert meta["capture_mode"] == "browser_extension"
    assert meta["source_page"] == "https://example.com/page"
    assert meta["browser"] == "Chrome"
    assert meta["transfer_status"] == "completed"
    assert "error" not in meta
