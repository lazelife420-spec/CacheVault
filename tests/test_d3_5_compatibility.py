"""Chunk D3.5 Mobile Model Compatibility Gate tests.

Proves backward compatibility of clips and receipts created before mobile
fields existed, verifies badges and Mobile Inbox routing, and asserts failed
transfer receipts do not imply success.
"""

from __future__ import annotations

from cache_vault.core import clip_metadata, models
from cache_vault.core.mobile.models import (
    PairedDevice,
    is_mobile_inbox_clip,
    is_from_phone_clip,
    TRANSFER_STATUS_FAILED,
)
from cache_vault.core.mobile.inbox import record_failed_mobile_transfer
from cache_vault.ui.receipt_ledger import event_to_row, format_detail_text


def test_legacy_clip_no_is_saved_to_phone_defaults_to_false(storage):
    """Prove a legacy clip missing is_saved_to_phone defaults safely to False."""
    class FakeRow(dict):
        def keys(self):
            return list(super().keys())

    row = FakeRow({
        "id": "clip-legacy-1",
        "created_at": "2026-06-16T01:00:00+00:00",
        "updated_at": "2026-06-16T01:00:00+00:00",
        "content_hash": "hash123",
        "content_type": models.CONTENT_TEXT,
        "content": "legacy content",
        "preview": "legacy content",
        "source_app": "test",
        "source_window": "test window",
        "classification": models.CLASS_PLAIN,
        "tags": None,
        "is_pinned": 0,
        "is_kept": 0,
        "is_sensitive": 0,
        "expires_at": None,
        "deleted_at": None,
        "duplicate_of": None,
    })

    # When deserialized, should not raise KeyError and should default to False
    clip = storage._row_to_clip(row)
    assert clip.id == "clip-legacy-1"
    assert clip.is_saved_to_phone is False

    # Check status badges
    badges = clip_metadata.status_badges(clip, storage=storage)
    assert "Saved to Phone" not in badges
    assert "From Phone" not in badges


def test_legacy_receipt_missing_mobile_fields_loads_safely():
    """Prove a legacy receipt without mobile fields loads without crashing."""
    event = {
        "id": "evt-legacy-1",
        "created_at": "2026-06-16T01:00:00+00:00",
        "event_type": models.EVENT_CAPTURED,
        "clip_id": "clip-legacy-1",
        "details": {
            "result": "success",
            "content_hash": "hash123",
        }
    }

    row = event_to_row(event)
    assert row.receipt_id == "evt-legacy-1"
    assert row.source is None
    assert row.route is None
    assert row.details == {"result": "success", "content_hash": "hash123"}

    # Verify formatting does not crash
    detail_text = format_detail_text(row)
    assert "Receipt ID: evt-legacy-1" in detail_text
    assert "Source" not in detail_text
    assert "Route" not in detail_text


from PIL import Image
from io import BytesIO


def _make_png() -> bytes:
    img = Image.new("RGB", (8, 6), "red")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_desktop_clip_status_badges(vault, tmp_path, monkeypatch):
    """Prove standard desktop clips derive On PC (for images) and never From Phone."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    
    # Standard text clip has no On PC badge (only images/screenshots have stored assets)
    text_clip = vault.capture("desktop capture", source_app="Notepad")
    text_badges = clip_metadata.status_badges(text_clip, storage=vault.storage)
    assert "On PC" not in text_badges
    assert "From Phone" not in text_badges
    assert "Saved to Phone" not in text_badges

    # Image clip has On PC badge
    image_clip = vault.capture_image(_make_png(), width=8, height=6, source_app="SnippingTool.exe")
    image_badges = clip_metadata.status_badges(image_clip, storage=vault.storage)
    assert "On PC" in image_badges
    assert "From Phone" not in image_badges
    assert "Saved to Phone" not in image_badges


def test_mobile_share_clip_status_badges(vault):
    """Prove mobile-share clips derive From Phone badge."""
    clip = vault.capture_mobile_share(
        "mobile capture",
        source_app="Chrome",
        source_window="Pixel 8",
    )
    
    # Assert From Phone is present
    badges = clip_metadata.status_badges(clip, storage=vault.storage)
    assert "From Phone" in badges
    assert "Saved to Phone" not in badges


def test_mobile_inbox_routing_excludes_non_mobile_clips(vault):
    """Prove only capture_mode=mobile_share routes to Mobile Inbox."""
    desktop_clip = vault.capture("desktop clip")
    mobile_share_clip = vault.capture_mobile_share("mobile shared clip", source_app="Chrome")
    
    # Create another clip with manual save hotkey capture mode
    manual_clip = vault.capture("manual clip", capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY)
    
    inbox = vault.list_mobile_inbox()
    inbox_ids = [clip.id for clip in inbox]
    
    assert mobile_share_clip.id in inbox_ids
    assert desktop_clip.id not in inbox_ids
    assert manual_clip.id not in inbox_ids


def test_failed_mobile_transfer_receipt_excludes_success_fields(vault):
    """Prove failed mobile transfer receipt has success=False and no success fields."""
    device = PairedDevice(
        device_id="device-123",
        device_name="Pixel 8",
        created_at=models.now_iso(),
        token_hash="tokenhash",
    )
    
    record_failed_mobile_transfer(
        vault,
        device,
        item_type="text",
        source_app="Chrome",
        source_device="Pixel 8",
        error="Could not save item to vault.",
    )
    
    recent_events = vault.events.recent(5)
    failed_event = next(
        e for e in recent_events
        if e["event_type"] == models.EVENT_MOBILE_INBOX_RECEIVED
        and e["details"].get("transfer_status") == TRANSFER_STATUS_FAILED
    )
    
    details = failed_event["details"]
    assert details["success"] is False
    assert details["transfer_status"] == TRANSFER_STATUS_FAILED
    assert details["error"] == "Could not save item to vault."
    
    # Prove success fields are excluded
    assert "clip_id" not in details
    assert "safe_id" not in details
    assert "safe_name" not in details
    assert "hash" not in details
