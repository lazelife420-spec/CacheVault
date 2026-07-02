"""Desktop Mobile Access bridge — read-only API, pairing, receipts."""

import json
import time

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


def test_fresh_profile_bridge_off_by_default(vault, tmp_path):
    """A brand-new profile must not start the LAN bridge on first launch.

    Proves the bridge stays OFF (no silent listener) until the user explicitly
    enables Mobile Access.
    """
    fresh = Settings.load(tmp_path / "brand_new_profile.json")
    assert fresh.mobile_access_enabled is False
    log = MobileReceiptLog(tmp_path / "fresh_receipts.json")
    bridge = MobileBridge(vault, receipt_log=log)
    assert bridge.needs_sync(fresh) is False
    bridge.sync(fresh)
    assert bridge.is_running is False


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


def test_public_pair_device_returns_token_without_logging_plaintext(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST",
        "/mobile/v1/pair-device",
        {},
        remote_ip="192.168.0.44",
        body={
            "device_id": "phone-auto-1",
            "device_name": "Galaxy S",
            "app_version": "0.1.0",
            "platform": "android",
        },
    )
    assert code == 200
    assert body["device_id"] == "phone-auto-1"
    assert body["device_name"] == "Galaxy S"
    assert body["token"]
    stored = vault.settings.paired_devices[0]
    assert stored["device_id"] == "phone-auto-1"
    assert stored["token_hash"] != body["token"]
    assert stored["platform"] == "android"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["action"] == "pair_device"
    assert rec["result"] == "ok"
    assert rec["device_id"] == "phone-auto-1"
    assert rec["remote_ip"] == "192.168.0.44"
    assert "token" not in json.dumps(rec).lower()


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
    vault.settings.block_sensitive_auto_capture = False
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


def test_recently_removed_route_is_allowed(vault, mobile_bridge):
    assert not is_forbidden_route("/mobile/v1/recently-removed")
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET",
        "/mobile/v1/recently-removed",
        _auth(device.device_id, token),
    )
    assert code == 200
    assert "clips" in body


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


def test_all_devices_includes_revoked_for_honest_status_display(vault, mobile_bridge):
    """Revoked devices must stay visible (not silently vanish) so the Mobile
    Access UI can show their true Revoked status instead of hiding them."""
    active, _ = _pair(mobile_bridge, vault, device_id="phone-active", name="Active Phone")
    revoked, _ = mobile_bridge.pair_device("phone-revoked", "Old Phone")
    mobile_bridge.revoke_device(revoked.device_id)

    assert {d.device_id for d in mobile_bridge.active_devices()} == {active.device_id}

    all_ids = {d.device_id for d in mobile_bridge.all_devices()}
    assert all_ids == {active.device_id, revoked.device_id}
    revoked_record = next(
        d for d in mobile_bridge.all_devices() if d.device_id == revoked.device_id)
    assert revoked_record.revoked_at is not None


def test_last_seen_updates_on_successful_reconnect(vault, mobile_bridge):
    """last_seen_at starts unset and is stamped by any authenticated request."""
    device, token = _pair(mobile_bridge, vault)
    assert vault.settings.paired_devices[0]["last_seen_at"] is None
    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert vault.settings.paired_devices[0]["last_seen_at"] is not None


def test_repair_with_same_device_id_refreshes_not_duplicates(vault, mobile_bridge):
    """Re-pairing with the phone's remembered device_id refreshes the same
    record (new token) instead of leaving an orphaned duplicate entry."""
    device, old_token = _pair(mobile_bridge, vault)
    assert len(vault.settings.paired_devices) == 1

    new_device, new_token = mobile_bridge.pair_device(device.device_id, device.device_name)
    assert new_device.device_id == device.device_id
    assert len(vault.settings.paired_devices) == 1, (
        "re-pairing the same device_id must refresh, not duplicate")

    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, old_token))
    assert code == 401, "the old, superseded token must no longer authenticate"

    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, new_token))
    assert code == 200


def test_repair_after_revoke_succeeds_with_fresh_credential(vault, mobile_bridge):
    device, old_token = _pair(mobile_bridge, vault)
    mobile_bridge.revoke_device(device.device_id)
    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, old_token))
    assert code == 401

    _, new_token = mobile_bridge.pair_device(device.device_id, device.device_name)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, new_token))
    assert code == 200
    assert vault.settings.paired_devices[0]["revoked_at"] is None, (
        "re-pairing must clear the prior revocation for this device_id")


def test_bridge_starts_when_enabled(vault, mobile_bridge):
    # _start() kicks off discovery.start() on its own background thread (so
    # zeroconf registration latency never blocks sync()); the assertion must
    # wait for that thread to run rather than checking immediately.
    _enable(vault)
    discovery = MagicMock()
    bridge = MobileBridge(vault, receipt_log=mobile_bridge.receipts, discovery=discovery)
    bridge.sync(vault.settings)
    try:
        assert bridge.is_running is True
        deadline = time.monotonic() + 2.0
        while discovery.start.call_count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
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


def test_bridge_sync_skips_when_already_matched(vault, mobile_bridge):
    _enable(vault)
    discovery = MagicMock()
    bridge = MobileBridge(vault, receipt_log=mobile_bridge.receipts, discovery=discovery)
    bridge.sync(vault.settings)
    try:
        assert bridge.is_running is True
        discovery.reset_mock()
        assert bridge.needs_sync(vault.settings) is False
        bridge.sync(vault.settings)
        discovery.stop.assert_not_called()
        discovery.start.assert_not_called()
    finally:
        bridge.stop()


def test_token_stored_as_hash_not_plaintext(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    stored = vault.settings.paired_devices[0]
    assert stored["token_hash"] != token
    assert len(stored["token_hash"]) == 64


def test_pair_hot_reload_without_restart(tmp_path, monkeypatch):
    """Pairing saved to disk is accepted while the bridge is already running."""
    from cache_vault.core import models
    from cache_vault.core.mobile.models import PairedDevice, hash_token, new_device_token
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(
        "cache_vault.core.settings.default_settings_path", lambda: settings_path)

    settings = Settings()
    settings.mobile_access_enabled = True
    settings.save(settings_path)
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings.load(settings_path))
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    bridge = MobileBridge(vault, receipt_log=log)

    token = new_device_token()
    device = PairedDevice(
        device_id="phone-hot-reload",
        device_name="Hot Reload Phone",
        created_at=models.now_iso(),
        token_hash=hash_token(token),
    )
    disk = Settings.load(settings_path)
    disk.paired_devices.append(device.to_dict())
    disk.save(settings_path)

    vault.settings.paired_devices = []

    code, body = bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert body["device_id"] == device.device_id


def test_reconnect_succeeds_after_desktop_restart(tmp_path, monkeypatch):
    """A phone's stored credential must keep working after the desktop process
    is fully restarted (fresh Vault/Settings loaded from disk), with no
    re-pairing required — this is the "Connect this time" reconnect path."""
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(
        "cache_vault.core.settings.default_settings_path", lambda: settings_path)

    settings = Settings()
    settings.mobile_access_enabled = True
    settings.save(settings_path)
    before_vault = Vault(storage=VaultStorage(":memory:"), settings=Settings.load(settings_path))
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    before_bridge = MobileBridge(before_vault, receipt_log=log)
    device, token = _pair(before_bridge, before_vault, device_id="restart-phone")

    # Simulate a full desktop restart: brand-new Vault/Settings/MobileBridge
    # instances, loading only what is on disk.
    after_vault = Vault(
        storage=VaultStorage(":memory:"), settings=Settings.load(settings_path))
    after_bridge = MobileBridge(after_vault, receipt_log=log)

    code, body = after_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert body["device_id"] == device.device_id
    assert after_vault.settings.paired_devices[0]["last_seen_at"] is not None
