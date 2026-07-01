from __future__ import annotations

import dataclasses
import pytest
import inspect
from cache_vault.core import models
from cache_vault.core.models import Clip
from cache_vault.core.contextmenu import clip_menu_items
from cache_vault.ui import clip_context

def _clip(content, **kw):
    return Clip(
        content=content,
        content_hash=models.content_hash(content),
        preview=models.make_preview(content),
        **kw,
    )

def test_vault_copy_to_safe_creates_duplicate(vault):
    # 1. Create a clip in default safe
    c = vault.capture("Original text clip", safe_id="default")
    assert c is not None
    assert c.safe_id == "default"

    # Create a destination safe
    work_safe = vault.create_safe("Work Safe")

    # 2. Copy clip to Work Safe
    copied = vault.copy_to_safe(c.id, work_safe.id)
    assert copied is not None
    assert copied.id != c.id
    assert copied.content == c.content
    assert copied.safe_id == work_safe.id
    assert copied.safe_name == "Work Safe"
    assert copied.capture_mode == models.CAPTURE_COPIED_TO_SAFE

    # 3. Verify original clip is unchanged and still in default safe
    orig = vault.storage.get_clip(c.id)
    assert orig is not None
    assert orig.safe_id == "default"

    # 4. Verify EVENT_ITEM_COPIED_TO_SAFE is recorded
    events = vault.events.recent()
    copied_event = next(e for e in events if e["event_type"] == models.EVENT_ITEM_COPIED_TO_SAFE)
    assert copied_event["details"]["clip_id"] == copied.id
    assert copied_event["details"]["safe_id"] == work_safe.id


def test_vault_copy_to_safe_duplicates_image_asset(vault):
    # Setup mock asset directory/environment
    from cache_vault.core.image_assets import ClipAssetRecord, make_storage_name
    
    c = vault.storage.add_clip(_clip("img_content", content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE))
    
    asset_rec = ClipAssetRecord(
        asset_id="asset-123",
        clip_id=c.id,
        mime_type="image/png",
        file_ext="png",
        size_bytes=100,
        sha256="fake-sha",
        created_at=models.now_iso(),
        original_name="test.png",
        storage_name=make_storage_name(c.id, "png"),
        width=10,
        height=10
    )
    
    vault.storage.save_clip_asset(asset_rec, b"fake png bytes")
    
    work_safe = vault.create_safe("Work Safe")
    
    # Copy image clip
    copied = vault.copy_to_safe(c.id, work_safe.id)
    assert copied is not None
    
    # Verify new asset record was created
    new_asset_rec = vault.storage.get_asset_record(copied.id)
    assert new_asset_rec is not None
    assert new_asset_rec.asset_id != "asset-123"
    assert new_asset_rec.clip_id == copied.id
    assert new_asset_rec.storage_name == make_storage_name(copied.id, "png")
    
    # Verify asset bytes match
    loaded = vault.storage.load_clip_asset_bytes(copied.id)
    assert loaded is not None
    assert loaded[0] == b"fake png bytes"


def test_copy_to_safe_invalid_safe_returns_none(vault):
    c = vault.capture("some text")
    res = vault.copy_to_safe(c.id, "non_existent_safe_id")
    assert res is None

    # ignore safe should also return None
    res_ignore = vault.copy_to_safe(c.id, "ignore")
    assert res_ignore is None


def test_copy_to_safe_invalid_clip_returns_none(vault):
    res = vault.copy_to_safe("non_existent_clip_id", "default")
    assert res is None


def test_context_menu_contains_copy_to_safe():
    c = _clip("some text")
    
    # 1. With last_safe_name
    items = clip_menu_items(c, last_safe_name="My Safe")
    organize_sec = next(i for i in items if i.key == "organize")
    keys = [item.key for item in organize_sec.children]
    
    assert "copy_to_last_safe" in keys
    assert "copy_to_safe" in keys
    assert "move_safe" in keys
    
    # Verify copy_to_last_safe label contains My Safe
    last_safe_item = next(i for i in organize_sec.children if i.key == "copy_to_last_safe")
    assert "My Safe" in last_safe_item.label

    # 2. Without last_safe_name
    items_no_last = clip_menu_items(c, last_safe_name=None)
    organize_no_last = next(i for i in items_no_last if i.key == "organize")
    keys_no_last = [item.key for item in organize_no_last.children]
    assert "copy_to_last_safe" not in keys_no_last
    assert "copy_to_safe" in keys_no_last


def test_clip_context_wires_copy_to_safe_dispatch():
    src = inspect.getsource(clip_context.open_clip_menu)
    assert '"copy_to_safe": lambda: window._copy_to_safe(clip.id)' in src
    assert '"copy_to_last_safe": lambda: window._copy_to_last_safe(clip.id)' in src
