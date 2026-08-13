"""Desktop Mobile Access bridge — read-only API, pairing, receipts."""

import json
import time
from pathlib import Path

import pytest
from unittest.mock import MagicMock

from cache_vault import brand
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


def test_status_byline_matches_brand_constant(vault, mobile_bridge):
    # Guards against the byline drifting back into a hardcoded literal
    # that no longer follows brand.py when it changes.
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert body["byline"] == brand.MOBILE_BYLINE


def test_public_pair_device_returns_token_without_logging_plaintext(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST",
        "/mobile/v1/pair-device",
        {},
        remote_ip="192.168.0.44",
        body={
            "client": "cachevault-android",
            "device_id": "phone-auto-1",
            "device_name": "Galaxy S",
            "app_version": "0.1.5",
            "build": 15,
            "protocol": 1,
            "platform": "android",
            "device": {"name": "Galaxy S23", "model": "SM-S911W"},
        },
    )
    assert code == 200
    assert body["device_id"] == "phone-auto-1"
    assert body["device_name"] == "Galaxy S"
    assert body["token"]
    assert body["compatible"] is True
    assert body["update_required"] is False
    stored = vault.settings.paired_devices[0]
    assert stored["device_id"] == "phone-auto-1"
    assert stored["token_hash"] != body["token"]
    assert stored["platform"] == "android"
    assert stored["protocol"] == 1
    assert stored["build"] == 15
    assert stored["device_model"] == "SM-S911W"
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


# ---------------------------------------------------------------------------
# MobileAccessController Unit Tests (PR M1)
# ---------------------------------------------------------------------------

def test_controller_enable_persists(vault, mobile_bridge, tmp_path):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    # Enable
    res = controller.enable(vault.settings)
    assert res.success is True
    assert vault.settings.mobile_access_enabled is True

    # Reload from disk and verify
    disk = Settings.load(vault.settings._persist_path)
    assert disk.mobile_access_enabled is True

    # Teardown
    controller.disable(vault.settings)


def test_controller_enable_starts_bridge_and_mdns(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    mobile_bridge.discovery.is_advertising = True
    controller = MobileAccessController(vault, mobile_bridge)

    res = controller.enable(vault.settings)
    assert res.success is True
    assert controller.listening is True
    assert controller.advertising is True

    # Teardown
    controller.disable(vault.settings)


def test_controller_disable_stops_all_and_enforces_invariant(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()

    # Mock transitions
    def mock_stop():
        mobile_bridge.discovery.is_advertising = False
    mobile_bridge.discovery.stop = mock_stop

    controller = MobileAccessController(vault, mobile_bridge)

    controller.enable(vault.settings)
    assert controller.listening is True

    controller.disable(vault.settings)
    assert controller.enabled is False
    assert controller.listening is False
    assert controller.advertising is False
    assert vault.settings.mobile_access_enabled is False


def test_controller_enable_failure_rolls_back(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()

    # Bind another server to a random free port to force conflict
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.listen(1)

    vault.settings.mobile_access_port = port

    try:
        controller = MobileAccessController(vault, mobile_bridge)
        res = controller.enable(vault.settings)
        assert res.success is False
        assert "already in use" in res.error

        # Verify desired_enabled remains True (intent preserved), but runtime listener is stopped
        assert controller.enabled is True
        assert controller.listening is False
        assert vault.settings.mobile_access_enabled is True
    finally:
        s.close()


def test_controller_subscribe_notifies(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    snapshots = []
    def subscriber(state):
        snapshots.append(state)

    controller.subscribe(subscriber)

    controller.enable(vault.settings)
    assert len(snapshots) >= 1
    assert snapshots[-1].enabled is True
    assert snapshots[-1].listening is True

    controller.disable(vault.settings)
    assert snapshots[-1].enabled is False
    assert snapshots[-1].listening is False

    # Cleanup
    controller.unsubscribe(subscriber)


def test_controller_sync_startup(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    # Settings enabled, runtime off
    vault.settings.mobile_access_enabled = True
    assert controller.listening is False

    controller.sync(vault.settings)
    assert controller.listening is True

    # Teardown
    controller.disable(vault.settings)


def test_controller_sync_startup_disabled(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    vault.settings.mobile_access_enabled = False
    controller.sync(vault.settings)
    assert controller.listening is False


def test_bridge_handle_stops_if_disabled(vault, mobile_bridge):
    mobile_bridge.discovery = MagicMock()
    # Simulate a running bridge when settings are disabled
    vault.settings.mobile_access_enabled = True
    mobile_bridge._start("127.0.0.1", vault.settings.mobile_access_port)
    assert mobile_bridge.is_running is True

    # Change settings to disabled
    vault.settings.mobile_access_enabled = False

    # Request should trigger force-stop invariant
    mobile_bridge.handle("GET", "/mobile/v1/status", {})
    assert mobile_bridge.is_running is False


def test_relative_timestamp_formats():
    from cache_vault.core.mobile.mobile_access_controller import relative_timestamp
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    assert relative_timestamp("") == "Never"
    assert relative_timestamp(None) == "Never"

    just_now = now.isoformat()
    assert relative_timestamp(just_now) == "Just now"

    two_mins_ago = (now - timedelta(minutes=2)).isoformat()
    assert relative_timestamp(two_mins_ago) == "2 minutes ago"

    one_hour_ago = (now - timedelta(hours=1)).isoformat()
    assert relative_timestamp(one_hour_ago) == "1 hour ago"

    three_hours_ago = (now - timedelta(hours=3)).isoformat()
    assert relative_timestamp(three_hours_ago) == "3 hours ago"

    five_days_ago = (now - timedelta(days=5)).isoformat()
    assert relative_timestamp(five_days_ago) == "5 days ago"

    # Invalid format fallback
    assert relative_timestamp("2026-07-12T06:36:44.09281") == "2026-07-12 06:36:44"


def test_mobile_access_naming(vault, mobile_bridge):
    from cache_vault.modules.mobile_bridge import MobileBridgeModule
    module = MobileBridgeModule(bridge_ref=mobile_bridge)

    assert module.name == "Mobile Access"
    assert module.description == "Phone sync via LAN for paired Android devices"
    assert module.get_settings_schema()[0].label == "Mobile Access"


def test_disabled_routes_not_red(vault, mobile_bridge):
    from cache_vault.modules.mobile_bridge import MobileBridgeModule
    module = MobileBridgeModule(bridge_ref=mobile_bridge)

    # Force disabled state
    vault.settings.mobile_access_enabled = False

    rows = module.get_status_rows()
    sync_row = next(r for r in rows if r.label == "Phone Sync")
    disc_row = next(r for r in rows if r.label == "LAN Discovery")

    assert sync_row.value_getter().startswith("Not running")
    assert sync_row.level == "info"  # Not warning or error
    assert disc_row.value_getter().startswith("Not running")
    assert disc_row.level == "info"


# ---------------------------------------------------------------------------
# Strengthened Lifecycle Unit Tests (PR M1)
# ---------------------------------------------------------------------------

def test_controller_save_is_idempotent(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    # Initial enable
    res = controller.enable(vault.settings)
    assert res.success is True
    initial_server = mobile_bridge._server
    initial_thread = mobile_bridge._thread

    # Repeated save / enable with same config
    res2 = controller.enable(vault.settings)
    assert res2.success is True
    assert mobile_bridge._server is initial_server, "Must not recreate server if unchanged"
    assert mobile_bridge._thread is initial_thread, "Must not spawn new thread if unchanged"

    controller.disable(vault.settings)


def test_controller_port_change_performs_restart(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    # Enable on default port
    controller.enable(vault.settings)
    assert controller.listening is True
    port1 = mobile_bridge._listen_port

    # Change port and trigger restart
    vault.settings.mobile_access_port = port1 + 1
    res = controller.restart(vault.settings)
    assert res.success is True
    assert controller.listening is True
    assert mobile_bridge._listen_port == port1 + 1

    controller.disable(vault.settings)


def test_controller_rapid_toggle_leaves_no_orphans(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    for _ in range(5):
        controller.enable(vault.settings)
        controller.disable(vault.settings)

    assert controller.listening is False
    assert mobile_bridge._server is None
    assert mobile_bridge._thread is None


def test_network_invariants_actually_bind_and_close(vault, mobile_bridge):
    from cache_vault.core.mobile.mobile_access_controller import MobileAccessController
    mobile_bridge.discovery = MagicMock()
    controller = MobileAccessController(vault, mobile_bridge)

    # Get a random free port first to ensure we don't conflict with another running instance
    import socket
    dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy.bind(("127.0.0.1", 0))
    free_port = dummy.getsockname()[1]
    dummy.close()

    vault.settings.mobile_access_port = free_port
    port = free_port

    # Off => LAN port connection fails
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    with pytest.raises(OSError):
        s.connect(("127.0.0.1", port))
    s.close()

    # On => Connection succeeds / health responds
    res = controller.enable(vault.settings)
    assert res.success is True
    assert mobile_bridge.verify_listening() is True

    # Verify we can connect to the port
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.settimeout(0.5)
    s2.connect(("127.0.0.1", port))
    s2.close()

    # Off again => connection fails
    controller.disable(vault.settings)
    s3 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s3.settimeout(0.2)
    with pytest.raises(OSError):
        s3.connect(("127.0.0.1", port))
    s3.close()


# ---------------------------------------------------------------------------
# Version Compatibility Handshake (PR M2)
# ---------------------------------------------------------------------------

def _pair_body(**overrides):
    body = {
        "client": "cachevault-android",
        "device_id": "phone-compat-1",
        "device_name": "Galaxy S23",
        "app_version": "0.1.5",
        "build": 15,
        "protocol": 1,
        "platform": "android",
        "device": {"name": "Galaxy S23", "model": "SM-S911W"},
    }
    body.update(overrides)
    return body


def test_compatible_protocol_accepted(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {}, body=_pair_body())
    assert code == 200
    assert body["compatible"] is True
    assert body["update_required"] is False
    assert body["token"]


def test_minimum_supported_app_version_accepted(vault, mobile_bridge):
    """The lower bound is inclusive: a phone on exactly the minimum
    supported version must still be accepted, not rejected."""
    from cache_vault.core.mobile.compatibility import MINIMUM_MOBILE_VERSION
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {},
        body=_pair_body(app_version=MINIMUM_MOBILE_VERSION))
    assert code == 200
    assert body["compatible"] is True


def test_old_protocol_returns_426(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {},
        body=_pair_body(protocol=0))
    assert code == 426
    assert body["error"] == "mobile_update_required"
    assert body["compatible"] is False
    assert body["update_required"] is True
    assert vault.settings.paired_devices == [], "an incompatible client must not be paired"


def test_missing_protocol_returns_structured_incompatibility(vault, mobile_bridge):
    """Unknown/missing protocol is treated conservatively (rejected), and the
    rejection is the same structured 426 body — never a generic 401/403/500."""
    _enable(vault)
    payload = _pair_body()
    del payload["protocol"]
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {}, body=payload)
    assert code == 426
    assert body["error"] == "mobile_update_required"
    assert body["client_protocol"] is None
    assert vault.settings.paired_devices == []


def test_future_unsupported_protocol_rejected(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {},
        body=_pair_body(protocol=99))
    assert code == 426
    assert body["compatible"] is False


def test_valid_token_plus_incompatible_protocol_still_rejected(vault, mobile_bridge):
    """A device that paired while compatible must still be blocked once its
    stored protocol falls outside the server's supported range — a valid
    token alone does not grant access; protocol compatibility is checked
    independently on every request."""
    _enable(vault)
    _, token = mobile_bridge.pair_device(
        "phone-drift", "Drift Phone", app_version="0.1.5", platform="android",
        protocol=0)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth("phone-drift", token))
    assert code == 426
    assert body["error"] == "mobile_update_required"


def test_invalid_token_rejected_before_protected_action(vault, mobile_bridge):
    """An invalid token must fail with 401 even for a device whose protocol
    would also be incompatible — auth is checked first, so version checks
    never mask an authentication failure."""
    _enable(vault)
    mobile_bridge.pair_device(
        "phone-both-bad", "Bad Phone", app_version="0.1.5", platform="android",
        protocol=0)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status",
        _auth("phone-both-bad", "totally-wrong-token"))
    assert code == 401
    assert body["error"] == "unauthorized"


def test_device_metadata_stored_and_displayed(vault, mobile_bridge):
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {}, body=_pair_body())
    assert code == 200
    stored = vault.settings.paired_devices[0]
    assert stored["app_version"] == "0.1.5"
    assert stored["build"] == 15
    assert stored["protocol"] == 1
    assert stored["device_model"] == "SM-S911W"


def test_compatibility_state_updates_on_reconnect(vault, mobile_bridge):
    """A phone paired under an old protocol becomes compatible again after
    the app updates and resends its handshake as headers on reconnect,
    without needing to fully re-pair."""
    _enable(vault)
    device, token = mobile_bridge.pair_device(
        "phone-upgrading", "Upgrading Phone", app_version="0.1.0",
        platform="android", protocol=0)
    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 426

    headers = _auth(device.device_id, token)
    headers["X-App-Version"] = "0.1.5"
    headers["X-Protocol-Version"] = "1"
    code, body = mobile_bridge.handle("GET", "/mobile/v1/status", headers)
    assert code == 200
    assert body["compatible"] is True
    assert vault.settings.paired_devices[0]["protocol"] == 1
    assert vault.settings.paired_devices[0]["app_version"] == "0.1.5"


def test_last_seen_updates_for_compatible_mobile_client(vault, mobile_bridge):
    _enable(vault)
    device, token = mobile_bridge.pair_device(
        "phone-touch", "Touch Phone", app_version="0.1.5",
        platform="android", protocol=1)
    assert vault.settings.paired_devices[0]["last_seen_at"] is None
    code, _ = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert vault.settings.paired_devices[0]["last_seen_at"] is not None


def test_update_required_client_cannot_send_clips(vault, mobile_bridge):
    _enable(vault)
    device, token = mobile_bridge.pair_device(
        "phone-blocked-send", "Blocked Phone", app_version="0.1.0",
        platform="android", protocol=0)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", _auth(device.device_id, token),
        body={"item_type": "text", "user_action": "send_to_pc", "text": "hi"})
    assert code == 426
    assert body["error"] == "mobile_update_required"


def test_disabled_mobile_access_still_rejects_incompatible_client(vault, mobile_bridge):
    """Mobile Access being off must mask everything, including compatibility
    state — the disabled check stays the very first gate, before any
    protocol/token evaluation."""
    device, token = mobile_bridge.pair_device(
        "phone-disabled-gate", "Disabled Gate Phone", app_version="0.1.0",
        platform="android", protocol=0)
    vault.settings.mobile_access_enabled = False
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 503
    assert body["error"] == "mobile_access_disabled"


def test_regression_existing_compatible_companion_still_pairs(vault, mobile_bridge):
    """A same-protocol Android companion must keep pairing and operating
    normally after the M2 compatibility handshake lands."""
    _enable(vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/pair-device", {}, body=_pair_body())
    assert code == 200
    token = body["token"]
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/clips", _auth("phone-compat-1", token))
    assert code == 200


def test_regression_minimum_version_never_exceeds_real_shipped_android_version():
    """MINIMUM_MOBILE_VERSION is a floor, not an aspirational target — it must
    never accidentally exceed the Android app's actual current versionName,
    or the real production app would be locked out by its own desktop.
    Guards against exactly this: an earlier draft of this constant ("0.1.5")
    was above the real shipped versionName ("0.1.3-rc6")."""
    import re
    from cache_vault.core.mobile.compatibility import (
        MINIMUM_MOBILE_VERSION, evaluate_compatibility, parse_version,
    )
    gradle_path = (
        Path(__file__).resolve().parent.parent
        / "android" / "app" / "build.gradle.kts"
    )
    text = gradle_path.read_text(encoding="utf-8")
    m = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    assert m, "could not find versionName in android/app/build.gradle.kts"
    shipped_version = m.group(1)
    result = evaluate_compatibility(1, shipped_version)
    assert result.compatible is True, (
        f"real shipped Android version {shipped_version!r} is rejected by "
        f"MINIMUM_MOBILE_VERSION={MINIMUM_MOBILE_VERSION!r} — the floor must "
        f"be at or below every already-released build"
    )
    assert parse_version(shipped_version) >= parse_version(MINIMUM_MOBILE_VERSION)


def test_regression_cli_device_unaffected_by_compat_gate(vault, mobile_bridge):
    """The desktop CLI pairs itself as a PairedDevice with no ``platform``
    set (see cache_vault/cli.py) and never sends protocol info — it must not
    be swept into the Android version-compatibility gate."""
    _enable(vault)
    device, token = mobile_bridge.pair_device("cli-local", "Cache Vault CLI")
    assert device.platform is None
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/status", _auth(device.device_id, token))
    assert code == 200
    assert "compatible" not in body


def test_endpoint_migration_retains_pairing_without_repairing(vault, mobile_bridge):
    """Pairing identity (deviceId + token) is independent of network endpoint.

    When desktop LAN IP or port changes (e.g., DHCP migration from .11 to .12),
    rediscovering the desktop PC endpoint allows browsing and sending without
    re-pairing.
    """
    _enable(vault)
    device, token = mobile_bridge.pair_device("s23-test-device", "Galaxy S23")
    headers = _auth(device.device_id, token)

    # Initial endpoint request (e.g. 192.168.0.11:8742)
    code_status, body_status = mobile_bridge.handle("GET", "/mobile/v1/status", headers, remote_ip="192.168.0.11")
    assert code_status == 200

    # Endpoint migration occurs (desktop moves to 192.168.0.12)
    code_clips, body_clips = mobile_bridge.handle("GET", "/mobile/v1/clips", headers, remote_ip="192.168.0.12")
    assert code_clips == 200

    # Send-to-PC from new endpoint succeeds with original credentials
    send_payload = {
        "content": "Migration validation payload",
        "device_id": device.device_id,
        "device_name": device.device_name,
    }
    code_send, body_send = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", headers, body=send_payload, remote_ip="192.168.0.12"
    )
    assert code_send == 200
    assert body_send["success"] is True
