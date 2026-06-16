"""Desktop Mobile Access bridge — read-only API, pairing, receipts."""

import json

import pytest
from unittest.mock import MagicMock

from cache_vault.core.mobile.api import READ_ONLY_ROUTES, is_forbidden_route
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog
from cache_vault.core.settings import Settings


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


def test_mobile_access_default_off():
    s = Settings()
    assert s.mobile_access_enabled is False
    assert s.mobile_access_bind_host == ""
    assert s.paired_devices == []


def test_server_not_running_when_disabled(vault, mobile_bridge):
    vault.settings.mobile_access_enabled = False
    mobile_bridge.sync(vault.settings)
    assert mobile_bridge.is_running is False


def test_api_unavailable_when_disabled(vault, mobile_bridge):
    vault.settings.mobile_access_enabled = False
    code, body = mobile_bridge.handle("GET", "/mobile/v1/status", {})
    assert code == 503
    assert body["error"] == "mobile_access_disabled"
    assert mobile_bridge.receipts.recent()[-1]["result"] == "denied"


def test_unpaired_request_rejected(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle("GET", "/mobile/v1/clips", {})
    assert code == 401
    assert body["error"] == "unauthorized"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "denied"
    assert rec["reason"]


def test_status_includes_mobile_api_version(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert body["mobile_api_version"] == "1"
    assert body["read_only"] is True
    assert "token" not in json.dumps(body).lower()


def test_paired_read_only_list_clips(vault, mobile_bridge):
    vault.capture("hello mobile")
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/clips", _auth(device.device_id, token))
    assert code == 200
    assert body["count"] >= 1
    assert body["clips"][0]["preview"]
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "ok"
    assert rec["device_id"] == device.device_id


def test_get_clip_by_id(vault, mobile_bridge):
    clip = vault.capture("detail me")
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}", _auth(device.device_id, token))
    assert code == 200
    assert body["clip"]["id"] == clip.id
    assert "detail" in body["clip"]["content"]


def test_sensitive_clip_masks_content_on_list_not_detail(vault, mobile_bridge):
    secret = vault.capture("sk-abc123DEF456ghi789JKL0")
    device, token = _pair(mobile_bridge, vault)
    headers = _auth(device.device_id, token)
    code, body = mobile_bridge.handle("GET", "/mobile/v1/clips", headers)
    assert code == 200
    listed = next(c for c in body["clips"] if c["id"] == secret.id)
    assert listed["is_sensitive"] is True
    assert listed["content"] == ""
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{secret.id}", headers)
    assert code == 200
    assert body["clip"]["is_sensitive"] is True
    assert "sk-abc123" in body["clip"]["content"]


def test_copy_share_receipt_post_does_not_mutate(vault, mobile_bridge):
    clip = vault.capture("copy me")
    device, token = _pair(mobile_bridge, vault)
    headers = _auth(device.device_id, token)
    before = len(vault.list_clips())
    for suffix in ("copy", "share"):
        code, body = mobile_bridge.handle(
            "POST", f"/mobile/v1/clips/{clip.id}/{suffix}", headers)
        assert code == 200
        assert body["ok"] is True
    assert len(vault.list_clips()) == before
    actions = {r["action"] for r in mobile_bridge.receipts.recent(5)}
    assert "copy" in actions
    assert "share" in actions


def test_asset_endpoint_not_available_writes_receipt(vault, mobile_bridge):
    clip = vault.capture("plain text")
    device, token = _pair(mobile_bridge, vault)
    headers = _auth(device.device_id, token)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", headers)
    assert code == 404
    assert body["error"] == "asset_not_available"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["action"] == "get_asset"
    assert rec["clip_id"] == clip.id


def test_save_receipt_post(vault, mobile_bridge):
    clip = vault.capture("save me")
    device, token = _pair(mobile_bridge, vault)
    headers = _auth(device.device_id, token)
    code, body = mobile_bridge.handle(
        "POST", f"/mobile/v1/clips/{clip.id}/save", headers)
    assert code == 200
    assert body["ok"] is True
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["action"] == "save"


def test_read_only_endpoints_do_not_mutate_vault(vault, mobile_bridge):
    vault.capture("immutable")
    before = len(vault.list_clips())
    device, token = _pair(mobile_bridge, vault)
    headers = _auth(device.device_id, token)
    for path in READ_ONLY_ROUTES:
        mobile_bridge.handle("GET", path, headers)
        mobile_bridge.handle("GET", f"{path}?q=test", headers)
    mobile_bridge.handle("GET", "/mobile/v1/clips/notreal", headers)
    assert len(vault.list_clips()) == before


def test_no_delete_or_edit_methods(vault, mobile_bridge):
    _enable(vault)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        code, body = mobile_bridge.handle(method, "/mobile/v1/clips", {})
        assert code == 405
        assert body["error"] == "method_not_allowed"


def test_forbidden_routes_do_not_exist(vault, mobile_bridge):
    _enable(vault)
    for path in (
        "/mobile/v1/clips/abc/delete",
        "/mobile/v1/permanent-remove",
        "/mobile/v1/clips/abc/edit",
    ):
        assert is_forbidden_route(path)
        code, _ = mobile_bridge.handle("GET", path, {})
        assert code in (401, 404)


def test_allowed_routes_only_get(vault, mobile_bridge):
    routes = MobileBridge.allowed_routes()
    assert "/mobile/v1/status" in routes
    assert not any("delete" in r for r in routes)


def test_receipt_written_for_rejected_unpaired(vault, mobile_bridge, tmp_path):
    _enable(vault)
    mobile_bridge.handle("GET", "/mobile/v1/favorites", {})
    rows = json.loads((tmp_path / "mobile_receipts.json").read_text(encoding="utf-8"))
    assert rows[-1]["result"] == "denied"


def test_invalid_token_receipt_includes_device_id_and_suggested_fix(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status",
        {**_auth(device.device_id, "wrong-token"), "X-Device-Id": device.device_id},
        remote_ip="192.168.0.99",
    )
    assert code == 401
    assert "token" in body["message"].lower()
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["device_id"] == device.device_id
    assert rec["remote_ip"] == "192.168.0.99"
    assert rec.get("suggested_fix")
    assert "Re-pair" in rec["suggested_fix"]


def test_revoked_device_rejected(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    mobile_bridge.revoke_device(device.device_id)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 401
    assert "revoked" in body["message"].lower()


def test_bridge_starts_when_enabled(vault, mobile_bridge):
    _enable(vault)
    discovery = MagicMock()
    bridge = MobileBridge(vault, receipt_log=mobile_bridge.receipts, discovery=discovery)
    bridge.sync(vault.settings)
    try:
        assert bridge.is_running is True
        discovery.start.assert_called_once()
    finally:
        bridge.stop()


def test_bridge_survives_port_conflict(vault, mobile_bridge):
    _enable(vault)
    mobile_bridge.sync(vault.settings)
    other = MobileBridge(vault, receipt_log=mobile_bridge.receipts)
    other.sync(vault.settings)  # must not raise when port already bound
    assert mobile_bridge.is_running is True


def test_bridge_stops_discovery_when_disabled(vault, mobile_bridge):
    discovery = MagicMock()
    bridge = MobileBridge(vault, receipt_log=mobile_bridge.receipts, discovery=discovery)
    vault.settings.mobile_access_enabled = True
    bridge.sync(vault.settings)
    vault.settings.mobile_access_enabled = False
    bridge.sync(vault.settings)
    assert discovery.stop.call_count >= 2


def test_token_stored_as_hash_not_plaintext(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    stored = vault.settings.paired_devices[0]
    assert stored["token_hash"] != token
    assert len(stored["token_hash"]) == 64
