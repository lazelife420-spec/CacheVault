"""Explicit paired mobile sends must not be vetoed by ``capture_paused``.

``capture_paused`` pauses *passive* clipboard monitoring. A Send-to-PC from a
paired phone is an explicit, authenticated user action, so it must still land in
the vault. Regression guard for the defect where a paused desktop answered every
mobile send with "Could not save item to vault." while pairing and browsing kept
working, which made the failure look like a phone or network problem.

These tests drive the real bridge so authentication, safe selection and receipt
behaviour are all exercised alongside the pause state.
"""

import base64
from io import BytesIO

import pytest
from PIL import Image

from cache_vault.core import models
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog


@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


@pytest.fixture
def paused_vault(vault):
    vault.settings.capture_paused = True
    return vault


def _pair(bridge, vault, device_id="phone-1", name="Test Pixel"):
    vault.settings.mobile_access_enabled = True
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {"X-Device-Id": device_id, "Authorization": f"Bearer {token}"}


def _text_payload(**overrides):
    body = {
        "item_type": "text",
        "content": "Sent while desktop capture was paused",
        "source_app": "Android Share",
        "source_device_name": "Test Pixel",
        "safe_id": "default",
        "user_action": "send_to_pc",
    }
    body.update(overrides)
    return body


def _png_bytes(size=(8, 6), color=(12, 34, 56)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _image_payload(**overrides):
    body = {
        "item_type": "image",
        "mime_type": "image/png",
        "content_b64": base64.b64encode(_png_bytes()).decode("ascii"),
        "original_name": "photo.png",
        "source_app": "Android Share",
        "source_device_name": "Test Pixel",
        "safe_id": "default",
        "user_action": "send_to_pc",
    }
    body.update(overrides)
    return body


def _received_event(vault, clip_id):
    return next(
        row
        for row in vault.events.recent(20)
        if row["event_type"] == models.EVENT_MOBILE_INBOX_RECEIVED
        and row["clip_id"] == clip_id
        and row["details"].get("action") == models.ACTION_MOBILE_INBOX_RECEIVED
    )


def _send(bridge, device, token, body):
    return bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token), body=body
    )


# --- text sends -------------------------------------------------------------


def test_text_send_creates_item_while_capture_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)
    before = len(paused_vault.list_clips())

    code, body = _send(
        mobile_bridge, device, token,
        _text_payload(content="Paused-desktop text payload 98765"),
    )

    assert paused_vault.settings.capture_paused is True
    assert code == 200, body
    assert body["success"] is True
    assert len(paused_vault.list_clips()) == before + 1

    clip = paused_vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    assert "Paused-desktop text payload 98765" in clip.content
    assert clip.capture_mode == models.CAPTURE_MOBILE_SHARE


def test_text_send_reports_completed_transfer_while_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)

    code, body = _send(mobile_bridge, device, token, _text_payload())

    assert code == 200, body
    details = _received_event(paused_vault, body["desktop_item_id"])["details"]
    assert details["transfer_status"] == "completed"
    assert details["paired_device_id"] == device.device_id


def test_text_send_receipt_result_is_ok_while_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)

    code, _body = _send(mobile_bridge, device, token, _text_payload())

    assert code == 200
    receipt = mobile_bridge.receipts.recent()[-1]
    assert receipt["action"] == "mobile_sent_to_pc"
    assert receipt["result"] == "ok"
    assert not receipt.get("reason")


def test_safe_selection_preserved_while_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)

    code, body = _send(
        mobile_bridge, device, token, _text_payload(safe_id="default")
    )

    assert code == 200, body
    clip = paused_vault.storage.get_clip(body["desktop_item_id"])
    assert clip.safe_id == "default"
    assert clip.safe_name


# --- image sends ------------------------------------------------------------


def test_image_send_creates_item_while_capture_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)

    code, body = _send(mobile_bridge, device, token, _image_payload())

    assert paused_vault.settings.capture_paused is True
    assert code == 200, body
    assert body["success"] is True

    clip = paused_vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    assert clip.content_type == models.CONTENT_IMAGE
    assert clip.capture_mode == models.CAPTURE_MOBILE_SHARE
    assert paused_vault.storage.has_clip_asset(clip.id)


def test_image_send_reports_completed_transfer_while_paused(paused_vault, mobile_bridge):
    device, token = _pair(mobile_bridge, paused_vault)

    code, body = _send(mobile_bridge, device, token, _image_payload())

    assert code == 200, body
    details = _received_event(paused_vault, body["desktop_item_id"])["details"]
    assert details["transfer_status"] == "completed"


# --- guards: behaviour that must NOT change ---------------------------------


def test_ordinary_clipboard_capture_still_blocked_while_paused(paused_vault):
    """Pause must keep vetoing passive capture; only explicit sends bypass it."""
    assert paused_vault.capture("ordinary clipboard text") is None


def test_authentication_still_enforced_while_paused(paused_vault, mobile_bridge):
    """Bypassing the pause must not weaken the auth gate."""
    device, _token = _pair(mobile_bridge, paused_vault)
    before = len(paused_vault.list_clips())

    code, body = _send(mobile_bridge, device, "bad-token", _text_payload())

    assert code == 401
    assert body["error"] == "unauthorized"
    assert len(paused_vault.list_clips()) == before


def test_blank_content_still_rejected_while_paused(paused_vault, mobile_bridge):
    """The pause bypass must not turn empty payloads into vault items."""
    device, token = _pair(mobile_bridge, paused_vault)
    before = len(paused_vault.list_clips())

    code, _body = _send(mobile_bridge, device, token, _text_payload(content="   "))

    assert code != 200
    assert len(paused_vault.list_clips()) == before
