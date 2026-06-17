"""Mobile-to-PC inbox — paired send endpoint tests."""

import json

import pytest

from cache_vault.core import models
from cache_vault.core.mobile.api import READ_ONLY_ROUTES, is_forbidden_route
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.inbox import validate_send_payload
from cache_vault.core.mobile.receipts import MobileReceiptLog


@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


def _enable(vault):
    vault.settings.mobile_access_enabled = True


def _pair(bridge, vault, device_id="phone-1", name="Test Pixel"):
    _enable(vault)
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }


def _send_payload(**overrides):
    body = {
        "item_type": "text",
        "content": "Hello from mobile inbox test",
        "source_app": "Chrome",
        "source_device_name": "Test Pixel",
        "safe_id": "default",
        "user_action": "send_to_pc",
    }
    body.update(overrides)
    return body


def test_paired_mobile_inbox_send_succeeds(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    before = len(vault.list_clips())
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(),
    )
    assert code == 200
    assert body["success"] is True
    assert body["desktop_item_id"]
    assert body["safe_name"]
    assert len(vault.list_clips()) == before + 1


def test_invalid_token_rejected_for_inbox(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        {**_auth(device.device_id, "bad-token")},
        body=_send_payload(),
    )
    assert code == 401
    assert body["error"] == "unauthorized"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "denied"


def test_mobile_send_creates_vault_item(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content="Unique mobile payload 12345"),
    )
    assert code == 200
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    assert "Unique mobile payload" in clip.content


def test_mobile_send_assigns_safe_metadata(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content="Safe assign test", safe_id="default"),
    )
    assert code == 200
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip.safe_id == "default"
    assert clip.safe_name


def test_mobile_send_capture_mode_is_mobile_share(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content="capture mode test"),
    )
    assert code == 200
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip.capture_mode == models.CAPTURE_MOBILE_SHARE


def test_receipt_created_without_full_sensitive_content(vault, mobile_bridge, tmp_path):
    device, token = _pair(mobile_bridge, vault)
    secret = "password=supersecret123456789"
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content=secret),
    )
    assert code == 200
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "ok"
    assert secret not in json.dumps(rec)


def test_read_only_routes_still_read_only(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    before = len(vault.list_clips())
    headers = _auth(device.device_id, token)
    for path in READ_ONLY_ROUTES:
        if path == "/mobile/v1/inbox":
            continue
        mobile_bridge.handle("GET", path, headers)
    assert len(vault.list_clips()) == before


def test_destructive_mobile_operations_still_rejected(vault, mobile_bridge):
    _enable(vault)
    for method in ("DELETE", "PUT", "PATCH"):
        code, body = mobile_bridge.handle(method, "/mobile/v1/clips/abc", {})
        assert code == 405
    code, body = mobile_bridge.handle("POST", "/mobile/v1/clips/abc/delete", {})
    assert code in (401, 404, 405)


def test_existing_status_route_works(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert body["mobile_api_version"] == "1"


def test_existing_clips_route_works(vault, mobile_bridge):
    vault.capture("desktop clip")
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/clips", _auth(device.device_id, token))
    assert code == 200
    assert body["count"] >= 1


def test_existing_recently_removed_route_works(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/recently-removed", _auth(device.device_id, token))
    assert code == 200
    assert "clips" in body


def test_safe_metadata_in_mobile_payload(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content="safe meta", safe_id="default"),
    )
    assert code == 200
    clip_id = body["desktop_item_id"]
    code, detail = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip_id}", _auth(device.device_id, token))
    assert code == 200
    assert detail["clip"]["safe_id"] == "default"
    assert detail["clip"]["safe_name"]
    assert detail["clip"]["capture_mode"] == models.CAPTURE_MOBILE_SHARE


def test_inbox_list_route(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body=_send_payload(content="list me"),
    )
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/inbox", _auth(device.device_id, token))
    assert code == 200
    assert body["count"] >= 1
    assert body["items"][0]["capture_mode"] == models.CAPTURE_MOBILE_SHARE


def test_unauthenticated_inbox_send_rejected(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", {}, body=_send_payload())
    assert code == 401


def test_validate_send_payload_requires_content():
    payload, err = validate_send_payload({"item_type": "text"})
    assert payload is None
    assert "content" in err


def test_forbidden_routes_unchanged():
    assert is_forbidden_route("/mobile/v1/clips/abc/delete")
    assert not is_forbidden_route("/mobile/v1/inbox/send")
