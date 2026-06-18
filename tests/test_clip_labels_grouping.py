from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace

from cache_vault.core import clip_accents, clip_metadata, grouping, models
from cache_vault.ui.clip_list import ClipList


def _clip(**kwargs):
    data = {
        "content_type": "image/png",
        "classification": "screenshot",
        "content": "https://example.com/private",
        "preview": "https://example.com/private",
        "source_app": "Chrome.exe",
        "capture_mode": "snipping_tool",
        "created_at": "2026-06-18T09:48:12",
        "updated_at": "2026-06-18T09:48:12",
        "date_used": "2026-06-18T09:48:12",
        "id": "a1b2c3d4e5",
        "is_pinned": False,
        "duplicate_of": None,
        "is_sensitive": False,
        "content_hash": "abc123",
        "collection": None,
        "title": "Private screenshot",
        "source_url": None,
        "safe_id": "default",
        "safe_name": "Default Safe",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_labels_for_clip_basic():
    clip = _clip()
    labels = clip_metadata.labels_for_clip(clip)
    assert 'Screenshot' in labels
    assert 'Chrome' in labels or 'Browser' in labels


def test_time_buckets():
    c1 = _clip(created_at='2026-06-18T09:48:12')
    assert clip_metadata._time_bucket(c1.created_at) in ('Today','Yesterday','This Week','Older')


def test_group_by_date_and_source():
    c1 = _clip(created_at='2026-06-18T09:48:12', source_app='Chrome.exe', id='a')
    c2 = _clip(created_at='2026-06-17T08:00:00', source_app='SnippingTool.exe', id='b')
    groups = grouping.group_clips([c1,c2], 'date')
    assert any(k in ('Today','Yesterday','This Week','Older') for k in groups.keys())
    groups2 = grouping.group_clips([c1,c2], 'source')
    assert 'Chrome.exe' in groups2 or 'SnippingTool.exe' in groups2


def test_label_accent_mapping_is_deterministic_and_subtle():
    assert clip_accents.label_accent("Screenshot").key == clip_accents.label_accent("Image").key
    assert clip_accents.label_accent("Screenshot").key == "image"
    assert clip_accents.label_accent("Link").key == "link"
    assert clip_accents.label_accent("Domain").key == "link"
    assert clip_accents.label_accent("Sensitive").key == "warning"
    assert clip_accents.label_accent("Favorite").key == "favorite"
    assert clip_accents.label_accent("Has Receipt").key == "receipt"
    assert clip_accents.label_accent("Something New").key == "neutral"
    assert asdict(clip_accents.label_accent("Chrome")) == asdict(clip_accents.label_accent("Chrome"))


def test_type_accent_mapping_by_clip_type():
    assert clip_accents.type_accent(models.CLASS_IMAGE, models.CONTENT_IMAGE).key == "image"
    assert clip_accents.type_accent("screenshot", "image/png").key == "image"
    assert clip_accents.type_accent(models.CLASS_LINK, models.CONTENT_TEXT).key == "link"
    assert clip_accents.type_accent(models.CLASS_CODE, models.CONTENT_TEXT).key == "code"
    assert clip_accents.type_accent(models.CLASS_PATH, models.CONTENT_TEXT).key == "file"


def test_group_header_accent_is_deterministic_by_group_type():
    assert clip_accents.group_header_accent("date", "Today").key == "neutral"
    assert clip_accents.group_header_accent("source", "Cursor.exe").key == "source"
    assert clip_accents.group_header_accent("source", "Chrome.exe").key == "browser"
    assert clip_accents.group_header_accent("type", "Screenshot").key == "image"
    assert clip_accents.group_header_accent("domain", "example.com").key == "link"
    assert clip_accents.group_header_accent("safe", "Work Safe").key == "neutral"
    assert asdict(clip_accents.group_header_accent("type", "Link")) == asdict(
        clip_accents.group_header_accent("type", "Link")
    )


def test_group_by_domain_and_safe():
    clip = _clip(
        classification=models.CLASS_LINK,
        content_type=models.CONTENT_TEXT,
        content="https://Example.com/account",
        preview="https://Example.com/account",
        safe_name="Work Safe",
    )
    assert "example.com" in grouping.group_clips([clip], "domain")
    assert "Work Safe" in grouping.group_clips([clip], "safe")


def test_locked_message_hides_private_metadata_and_claims():
    msg = clip_accents.LOCKED_ITEMS_MESSAGE
    assert msg == "Vault locked — unlock to view items"
    assert clip_accents.no_forbidden_accent_claims(msg)
    for private_term in ("Chrome", "example.com", "Screenshot", "image", "source", "domain"):
        assert private_term.lower() not in msg.lower()


def test_locked_list_render_hides_labels_and_group_headers(tk_root):
    clip = _clip(title="Private screenshot", source_app="Chrome.exe")
    view = ClipList(tk_root, on_select=lambda _clip: None)
    view.render([clip], group_by="type")
    assert "Screenshot" in _widget_text(view)
    assert "Chrome" in _widget_text(view)

    view.render([], empty_message=clip_accents.LOCKED_ITEMS_MESSAGE)
    text = _widget_text(view)
    assert clip_accents.LOCKED_ITEMS_MESSAGE in text
    for private_term in ("Private screenshot", "Chrome", "Screenshot", "example.com", "(1)"):
        assert private_term not in text
    view.destroy()


def _widget_text(widget) -> str:
    parts: list[str] = []
    try:
        value = widget.cget("text")
    except Exception:  # noqa: BLE001
        value = ""
    if value:
        parts.append(str(value))
    for child in widget.winfo_children():
        parts.append(_widget_text(child))
    return "\n".join(parts)
