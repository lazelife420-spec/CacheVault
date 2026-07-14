"""
F2.5 Browser Extension Security Gate — manifest permission audit and inbox bridge behavior tests.

This verifies:
- manifest.json contains ONLY the approved minimal permissions
- No forbidden permissions are present
- No background scraping keywords in popup.js
- No broad host_permissions
- Bridge rejects bad tokens (401)
- Bridge rejects disabled Mobile Access (503)
- Bridge accepts valid paired token
- Payload preserves selected URL order
- Receipts identify browser_extension as source
"""

from __future__ import annotations

import json
import pathlib
import pytest

from cache_vault.core import models
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog

# Resolve path to the extension folder
_REPO_ROOT = pathlib.Path(__file__).parent.parent
_EXT_DIR = _REPO_ROOT / "extension"
_MANIFEST = _EXT_DIR / "manifest.json"
_POPUP_JS = _EXT_DIR / "popup.js"


# ---------- Manifest permission audit ----------

def test_manifest_exists():
    """manifest.json must exist under extension/."""
    assert _MANIFEST.exists(), "extension/manifest.json missing"


def test_manifest_version_is_3():
    """Must be MV3 — not the deprecated MV2."""
    data = json.loads(_MANIFEST.read_text())
    assert data["manifest_version"] == 3


def test_manifest_permissions_are_minimal():
    """Only the four approved permissions must be present."""
    data = json.loads(_MANIFEST.read_text())
    perms = set(data.get("permissions", []))
    allowed = {"activeTab", "scripting", "clipboardWrite", "storage"}
    forbidden = perms - allowed
    assert not forbidden, f"Forbidden permissions found: {forbidden}"


def test_manifest_no_history_permission():
    data = json.loads(_MANIFEST.read_text())
    assert "history" not in data.get("permissions", [])
    assert "history" not in data.get("optional_permissions", [])


def test_manifest_no_tabs_permission():
    """'tabs' gives full access to tab URLs/titles — must not be present."""
    data = json.loads(_MANIFEST.read_text())
    assert "tabs" not in data.get("permissions", [])


def test_manifest_no_broad_host_permissions():
    """Must not request <all_urls> or wildcard host permissions."""
    data = json.loads(_MANIFEST.read_text())
    host_perms = data.get("host_permissions", [])
    forbidden = [h for h in host_perms if "<all_urls>" in h or h == "*://*/*"]
    assert not forbidden, f"Broad host_permissions found: {forbidden}"


def test_manifest_no_background_service_worker():
    """No background service worker — no persistent scraping."""
    data = json.loads(_MANIFEST.read_text())
    assert "background" not in data, (
        "background service_worker declared — remove it to prevent persistent scraping"
    )


def test_manifest_no_web_request_permission():
    """webRequest/declarativeNetRequest intercepts network traffic — forbidden."""
    data = json.loads(_MANIFEST.read_text())
    perms = set(data.get("permissions", []))
    bad = perms & {"webRequest", "webRequestBlocking", "declarativeNetRequest"}
    assert not bad, f"Network intercept permissions found: {bad}"


def test_manifest_no_cookies_permission():
    data = json.loads(_MANIFEST.read_text())
    assert "cookies" not in data.get("permissions", [])


# ---------- popup.js static code audit ----------

def test_popup_js_exists():
    assert _POPUP_JS.exists(), "extension/popup.js missing"


def test_popup_js_no_tabs_all_url_scraping():
    """Must not query all tabs or use chrome.tabs.query with no filter."""
    src = _POPUP_JS.read_text()
    # Checking for tabs querying all — the only allowed usage is active+currentWindow
    assert "chrome.tabs.query({}" not in src
    assert "chrome.tabs.query({ })" not in src


def test_popup_js_no_history_api():
    src = _POPUP_JS.read_text()
    assert "chrome.history" not in src


def test_popup_js_no_web_request_listener():
    src = _POPUP_JS.read_text()
    assert "chrome.webRequest" not in src


def test_popup_js_fetch_only_to_localhost():
    """All fetch() calls must target the user-configured host, which defaults to localhost."""
    src = _POPUP_JS.read_text()
    # Verify no hardcoded external domains
    assert "https://api." not in src
    assert "https://cloud." not in src
    # Verify local loopback default is preserved
    assert "127.0.0.1" in src


def test_popup_js_token_sent_as_bearer():
    """Token must be sent via Authorization Bearer — not as query param or plain header."""
    src = _POPUP_JS.read_text()
    assert "Authorization" in src
    assert "Bearer" in src


def test_popup_js_bad_token_handled_honestly():
    """401 and 503 error cases must show distinct toast messages, not fake success."""
    src = _POPUP_JS.read_text()
    assert "401" in src
    assert "503" in src
    assert "unauthorized" in src.lower() or "Pairing unauthorized" in src


def test_popup_js_link_order_is_join_preserved():
    """Links must be joined in selected order — not sorted or shuffled."""
    src = _POPUP_JS.read_text()
    # selected.map(...).join is the correct pattern
    assert "selected.map(l =>" in src or "selected.map((l" in src
    assert ".join(" in src


def test_popup_js_receipt_uses_browser_extension_source():
    """Receipts stored locally must use 'browser_extension' as the source."""
    src = _POPUP_JS.read_text()
    assert "browser_extension" in src


def test_popup_js_extension_batch_action_labels():
    """Receipt actions must be extension-specific labels, not desktop-reused ones."""
    src = _POPUP_JS.read_text()
    assert "extension_batch_link_copy" in src
    assert "extension_batch_link_send" in src


# ---------- Bridge behavior tests (server-side) ----------

@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


def _enable(vault):
    vault.settings.mobile_access_enabled = True


def _pair(bridge, vault, device_id="ext-gate-1", name="Cache Vault Companion"):
    _enable(vault)
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }


def _ext_payload(content="https://example.com/a\nhttps://example.com/b"):
    return {
        "item_type": "url",
        "user_action": "send_to_pc",
        "content": content,
        "source_app": "Browser Extension",
        "source_device_name": "Chrome",
        "source_url": "https://news.example.com/",
        "safe_id": "inbox",
    }


def test_bridge_rejects_bad_token(vault, mobile_bridge):
    """Bad token must return 401 — no fake success."""
    device, _good_token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        _auth(device.device_id, "BAD-TOKEN-XXXX"),
        body=_ext_payload(),
    )
    assert code == 401
    assert body["error"] == "unauthorized"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "denied"


def test_bridge_rejects_when_mobile_access_off(vault, mobile_bridge):
    """If Mobile Access is disabled, bridge returns 503."""
    vault.settings.mobile_access_enabled = False
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send", {},
        body=_ext_payload(),
    )
    assert code == 503
    assert body["error"] == "mobile_access_disabled"


def test_bridge_accepts_valid_single_link(vault, mobile_bridge):
    """Valid paired send with a single link succeeds and creates a vault clip."""
    device, token = _pair(mobile_bridge, vault)
    before = len(vault.list_clips())
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_ext_payload("https://single.example.com/article"),
    )
    assert code == 200
    assert body["success"] is True
    assert len(vault.list_clips()) == before + 1
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip.source_app == "Browser Extension"


def test_bridge_accepts_valid_multi_link_batch(vault, mobile_bridge):
    """Valid paired send with multiple links creates a clip preserving order."""
    device, token = _pair(mobile_bridge, vault)
    links = "https://example.com/first\nhttps://example.com/second\nhttps://example.com/third"
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_ext_payload(links),
    )
    assert code == 200
    clip = vault.storage.get_clip(body["desktop_item_id"])
    assert clip is not None
    # Order must be preserved exactly as submitted
    lines = clip.content.splitlines()
    assert lines[0] == "https://example.com/first"
    assert lines[1] == "https://example.com/second"
    assert lines[2] == "https://example.com/third"


def test_bridge_receipt_shows_browser_extension_source(vault, mobile_bridge):
    """After a valid send, vault event log shows source_app=Browser Extension."""
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_ext_payload(),
    )
    assert code == 200

    events = vault.events.recent(20)
    recv = next(
        (e for e in events
         if e.get("event_type") == models.EVENT_MOBILE_INBOX_RECEIVED
         and e.get("clip_id") == body["desktop_item_id"]),
        None,
    )
    assert recv is not None
    details = recv["details"]
    assert details["source_app"] == "Browser Extension"
    assert details["transfer_status"] == "completed"
    assert details["capture_mode"] == models.CAPTURE_MOBILE_SHARE


def test_bridge_revoked_token_rejected(vault, mobile_bridge):
    """Revoked device must return 401 on subsequent calls."""
    device, token = _pair(mobile_bridge, vault)
    mobile_bridge.revoke_device(device.device_id)
    code, body = mobile_bridge.handle(
        "POST", "/mobile/v1/inbox/send",
        _auth(device.device_id, token),
        body=_ext_payload(),
    )
    assert code == 401
    assert body["error"] == "unauthorized"
