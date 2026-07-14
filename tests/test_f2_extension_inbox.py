"""Integration tests for F2 browser extension batch link capture."""

from __future__ import annotations

import pytest
from cache_vault.core import models
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog


@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


def _enable(vault):
    vault.settings.mobile_access_enabled = True


def _pair(bridge, vault, device_id="extension-1", name="Chrome Extension"):
    _enable(vault)
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }


def test_extension_send_batch_links_to_vault(vault, mobile_bridge):
    """Verify browser extension can send a batch of links to the Vault inbox."""
    device, token = _pair(mobile_bridge, vault)
    before = len(vault.list_clips())

    payload = {
        "item_type": "url",
        "user_action": "send_to_pc",
        "content": "https://example.com/link1\nhttps://example.com/link2",
        "source_app": "Browser Extension",
        "source_device_name": "Edge",
        "source_url": "https://google.com/search?q=test",
        "safe_id": "inbox",
    }

    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=payload,
    )

    assert code == 200
    assert body["success"] is True
    assert body["desktop_item_id"]
    assert len(vault.list_clips()) == before + 1

    # Verify the saved clip content & classification
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    assert clip.classification == models.CLASS_LINK
    assert clip.content == "https://example.com/link1\nhttps://example.com/link2"
    assert clip.source_app == "Browser Extension"
    assert clip.source_window == "Edge"
    assert clip.source_url == "https://google.com/search?q=test"

    # Verify capture receipt recorded in events
    events = vault.events.recent(50)

    # Find the received receipt event
    recv_event = None
    for ev in events:
        if ev.get("event_type") == models.EVENT_MOBILE_INBOX_RECEIVED:
            recv_event = ev
            break

    assert recv_event is not None
    details = recv_event["details"]
    assert details.get("success") is True
    assert details.get("capture_mode") == models.CAPTURE_MOBILE_SHARE
