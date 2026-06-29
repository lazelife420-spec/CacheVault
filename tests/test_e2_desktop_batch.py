"""Unit tests for Desktop Batch Copy Wiring (Chunk E2)."""

from __future__ import annotations

from types import SimpleNamespace
from cache_vault.core import models
from cache_vault.ui.shell import CacheVaultApp


class FakeVault:
    def __init__(self):
        self.storage = FakeStorage()
        self.events = FakeEvents()

    def copied_again(self, clip_id: str) -> str | None:
        clip = self.storage.get_clip(clip_id)
        return clip.content if clip else None


class FakeStorage:
    def __init__(self):
        self.clips = {}

    def get_clip(self, clip_id: str):
        return self.clips.get(clip_id)


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

    app._guard_unlocked = lambda: True
    app.clipboard_clear = lambda: app._clipboard.clear()
    app.clipboard_append = lambda s: app._clipboard.append(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._monitor = SimpleNamespace(note_local_copy=lambda s: app._copied_content.append(s))
    return app


def _clip(clip_id: str, content: str, classification: str, content_type: str, title: str | None = None):
    return SimpleNamespace(
        id=clip_id,
        content=content,
        classification=classification,
        content_type=content_type,
        title=title,
    )


def test_desktop_multi_link_copy_plain():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT, "Example Domain")
    c2 = _clip("c2", "https://google.com", models.CLASS_LINK, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("plain")

    assert len(app._clipboard) == 1
    assert app._clipboard[0] == "Example Domain - https://example.com\nhttps://google.com"
    assert len(app._toasts) == 1
    assert app._toasts[0] == "Copied 2 links"

    # Event recorded
    assert len(vault.events.records) == 1
    event_type, _, payload = vault.events.records[0]
    assert event_type == models.EVENT_COPIED_AGAIN
    assert payload["count"] == 2
    assert payload["format"] == "plain"
    assert payload["success"] is True
    assert payload["breakdown"] == "2 links · 0 screenshots · 0 text clips"


def test_desktop_multi_link_copy_markdown():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT, "Example Domain")
    c2 = _clip("c2", "https://google.com", models.CLASS_LINK, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("markdown")

    assert app._clipboard[0] == "- [Example Domain](https://example.com)\n- [https://google.com](https://google.com)"
    assert app._toasts[0] == "Copied 2 links as Markdown"


def test_desktop_multi_link_copy_numbered():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT, "Example Domain")
    c2 = _clip("c2", "https://google.com", models.CLASS_LINK, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("numbered")

    assert app._clipboard[0] == "1. [Example Domain](https://example.com)\n2. [https://google.com](https://google.com)"
    assert app._toasts[0] == "Copied 2 links as Numbered"


def test_desktop_preserves_selection_order():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("c2", "https://google.com", models.CLASS_LINK, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c2", "c1"]  # reversed selection

    app._bulk_copy_format("plain")
    assert app._clipboard[0] == "https://google.com\nhttps://example.com"


def test_desktop_text_only_batch_copy():
    vault = FakeVault()
    c1 = _clip("c1", "Hello text 1", models.CLASS_PLAIN, models.CONTENT_TEXT)
    c2 = _clip("c2", "Hello text 2", models.CLASS_PLAIN, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("plain")
    assert app._clipboard[0] == "Hello text 1\n\nHello text 2"
    assert app._toasts[0] == "Copied 2 text clips"


def test_desktop_mixed_text_link_copy():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("c2", "Some text block", models.CLASS_PLAIN, models.CONTENT_TEXT)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("plain")
    assert app._clipboard[0] == "https://example.com\n\nSome text block"
    assert app._toasts[0] == "Copied 2 text/link clips"


def test_desktop_mixed_selection_with_screenshots_skips_honest():
    vault = FakeVault()
    c1 = _clip("c1", "https://example.com", models.CLASS_LINK, models.CONTENT_TEXT)
    c2 = _clip("c2", "img-bytes", models.CLASS_IMAGE, models.CONTENT_IMAGE)
    vault.storage.clips = {"c1": c1, "c2": c2}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("plain")
    # Only link is copied, image is skipped
    assert app._clipboard[0] == "https://example.com"
    # Toast indicates skipped screenshot
    assert app._toasts[0] == "Copied 1 text/link clips (1 image skipped)"

    # Events shows breakdown
    event = vault.events.records[0][2]
    assert event["breakdown"] == "1 links · 1 screenshots · 0 text clips"
