"""Mobile-to-PC inbox — paired image send tests."""

import base64
import json
from io import BytesIO

import pytest
from PIL import Image

from cache_vault.core import models
from cache_vault.core.mobile import inbox as inbox_mod
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.inbox import validate_send_payload
from cache_vault.core.mobile.receipts import MobileReceiptLog


@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


def _pair(bridge, vault, device_id="phone-1", name="Test Pixel"):
    vault.settings.mobile_access_enabled = True
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {"X-Device-Id": device_id, "Authorization": f"Bearer {token}"}


def _png_bytes(size=(8, 6), color=(12, 34, 56)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _image_payload(**overrides) -> dict:
    body = {
        "item_type": "image",
        "mime_type": "image/png",
        "content_b64": base64.b64encode(_png_bytes()).decode("ascii"),
        "original_name": "photo.png",
        "source_app": "Photos",
        "source_device_name": "Test Pixel",
        "safe_id": "default",
        "user_action": "send_to_pc",
    }
    body.update(overrides)
    return body


def test_image_send_creates_image_clip_with_asset(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(),
    )
    assert code == 200, body
    assert body["success"] is True
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    assert clip.content_type == models.CONTENT_IMAGE
    assert clip.capture_mode == models.CAPTURE_MOBILE_SHARE
    assert vault.storage.has_clip_asset(clip.id)


def test_image_send_appears_in_mobile_inbox(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    before = len(vault.list_mobile_inbox())
    mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(),
    )
    assert len(vault.list_mobile_inbox()) == before + 1


def test_image_asset_bytes_round_trip(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    png = _png_bytes(size=(10, 4), color=(200, 100, 50))
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(content_b64=base64.b64encode(png).decode("ascii")),
    )
    assert code == 200
    clip_id = body["desktop_item_id"]
    code, asset = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip_id}/asset", _auth(device.device_id, token))
    assert code == 200
    # Asset endpoint returns the exact stored image bytes.
    assert asset.data == png
    assert asset.content_type.startswith("image/")


def test_image_send_rejects_unsupported_mime(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(mime_type="image/tiff"),
    )
    assert code == 400
    assert "image type" in (body.get("message") or body.get("error") or "").lower()


def test_image_send_rejects_bad_base64(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(content_b64="!!!not-valid-base64!!!"),
    )
    assert code == 400


def test_image_send_rejects_non_image_payload(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    fake = base64.b64encode(b"this is plainly not an image").decode("ascii")
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(content_b64=fake),
    )
    assert code == 400
    assert "image" in (body.get("error") or "").lower()


def test_image_send_rejects_oversize(vault, mobile_bridge, monkeypatch):
    device, token = _pair(mobile_bridge, vault)
    monkeypatch.setattr(inbox_mod, "MAX_MOBILE_IMAGE_BYTES", 64)
    big = _png_bytes(size=(64, 64))  # > 64 bytes once encoded as PNG
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_image_payload(content_b64=base64.b64encode(big).decode("ascii")),
    )
    assert code == 400
    assert "too large" in (body.get("error") or "").lower()


def test_image_receipt_has_no_raw_bytes(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    payload = _image_payload()
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=payload,
    )
    assert code == 200
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "ok"
    # The base64 image data must never be written into a receipt.
    assert payload["content_b64"] not in json.dumps(rec)


def test_validate_image_requires_mime_and_b64():
    payload, err = validate_send_payload({"item_type": "image"})
    assert payload is None
    assert "image type" in err.lower()
    payload, err = validate_send_payload({"item_type": "image", "mime_type": "image/png"})
    assert payload is None
    assert "content_b64" in err
