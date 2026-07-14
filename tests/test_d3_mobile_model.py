"""D3 mobile model foundation tests."""

from cache_vault.core import clip_metadata, models
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog
from cache_vault.core.mobile.models import (
    TRANSFER_STATUS_FAILED,
    MOBILE_INBOX_LABEL,
    PHONE_VAULT_LABEL,
)


def _auth(device_id, token):
    return {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }


def _enable(vault):
    vault.settings.mobile_access_enabled = True


def _pair(bridge, vault, device_id="phone-d3", name="Pixel 8"):
    _enable(vault)
    return bridge.pair_device(device_id, name)


def _send_payload(**overrides):
    body = {
        "item_type": "text",
        "content": "hello from the phone vault",
        "source_app": "Chrome",
        "source_device_name": "Pixel 8",
        "safe_id": "default",
        "user_action": "send_to_pc",
    }
    body.update(overrides)
    return body


def test_mobile_labels_are_explicit_terms():
    assert PHONE_VAULT_LABEL == "Phone Vault"
    assert MOBILE_INBOX_LABEL == "Mobile Inbox"


def test_mobile_share_receipt_contains_honest_metadata(vault, tmp_path):
    bridge = MobileBridge(vault, receipt_log=MobileReceiptLog(tmp_path / "mobile_receipts.json"))
    device, token = _pair(bridge, vault)

    code, body = bridge.handle(
        "POST",
        "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_send_payload(),
    )

    assert code == 200, body
    event = next(
        row for row in vault.events.recent(20)
        if row["event_type"] == models.EVENT_MOBILE_INBOX_RECEIVED
        and row["clip_id"] == body["desktop_item_id"]
        and row["details"].get("action") == models.ACTION_MOBILE_INBOX_RECEIVED
    )
    details = event["details"]
    assert details["source_device"] == "Pixel 8"
    assert details["paired_device_id"] == device.device_id
    assert details["capture_mode"] == models.CAPTURE_MOBILE_SHARE
    assert details["item_type"] == models.CLASS_PLAIN
    assert details["transfer_status"] == "completed"
    assert details["timestamp"]


def test_phone_originated_item_derives_from_phone_badge(vault):
    clip = vault.capture_mobile_share(
        "shared from phone",
        source_app="Chrome",
        source_window="Pixel 8",
    )

    badges = clip_metadata.status_badges(clip)
    assert "From Phone" in badges


def test_mobile_inbox_routing_is_deterministic(vault):
    vault.capture("desktop only clip")
    mobile_clip = vault.capture_mobile_share("mobile inbox item", source_app="Chrome")

    items = vault.list_mobile_inbox()

    assert [item.id for item in items] == [mobile_clip.id]
    assert all(item.capture_mode == models.CAPTURE_MOBILE_SHARE for item in items)


def test_pc_only_items_do_not_show_saved_to_phone(vault):
    clip = vault.capture("pc only")

    badges = clip_metadata.status_badges(clip)
    assert "Saved to Phone" not in badges


def test_failed_mobile_transfer_records_failure_status_honestly(vault, tmp_path, monkeypatch):
    bridge = MobileBridge(vault, receipt_log=MobileReceiptLog(tmp_path / "mobile_receipts.json"))
    device, token = _pair(bridge, vault)

    monkeypatch.setattr(vault, "capture_mobile_share", lambda *args, **kwargs: None)
    code, body = bridge.handle(
        "POST",
        "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_send_payload(content="this one will fail"),
    )

    assert code == 400
    assert body["error"] == "Could not save item to vault."
    failure = next(
        row for row in vault.events.recent(20)
        if row["event_type"] == models.EVENT_MOBILE_INBOX_RECEIVED
        and row["details"].get("transfer_status") == TRANSFER_STATUS_FAILED
    )
    assert failure["details"]["success"] is False
    assert failure["details"]["source_device"] == "Pixel 8"
    assert failure["details"]["paired_device_id"] == device.device_id


def test_saved_to_phone_label_requires_real_backing_data():
    clip = models.Clip(content="pc item")
    assert "Saved to Phone" not in clip_metadata.status_badges(clip)
    clip.is_saved_to_phone = True
    assert "Saved to Phone" in clip_metadata.status_badges(clip)


def test_saved_to_phone_state_persists_in_storage(storage):
    clip = models.Clip(
        content="persist me",
        preview="persist me",
        content_hash=models.content_hash("persist me"),
        is_saved_to_phone=True,
    )

    storage.add_clip(clip)
    loaded = storage.get_clip(clip.id)

    assert loaded is not None
    assert loaded.is_saved_to_phone is True
