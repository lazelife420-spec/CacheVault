"""Mobile Access bridge — gated read-only HTTP API for Cache Vault Mobile."""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING
from urllib.parse import unquote

from .. import models, search
from ..settings import Settings
from ..storage import FILTER_ALL, FILTER_FAVORITES, FILTER_RECENTLY_REMOVED, FILTER_SEARCH_ALL
from . import api as api_mod
from .api import BinaryResponse
from .models import (
    DEFAULT_BIND_HOST,
    DEFAULT_MOBILE_PORT,
    MOBILE_API_VERSION,
    MobileAccessReceipt,
    PairedDevice,
    hash_token,
    new_device_token,
)
from .receipts import MobileReceiptLog
from .discovery import MobileDiscovery

if TYPE_CHECKING:
    from ..vault import Vault

_CLIP_ID_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)$")

# Reject POST bodies larger than this before reading them. Image sends are
# capped at 10 MB decoded; base64 + JSON overhead fits comfortably under 20 MB.
MAX_POST_BODY_BYTES = 20 * 1024 * 1024


class MobileBridge:
    """Desktop-side read-only API for paired Android devices."""

    def __init__(self, vault: Vault, *, receipt_log: MobileReceiptLog | None = None,
                 discovery: MobileDiscovery | None = None):
        self.vault = vault
        self.receipts = receipt_log or MobileReceiptLog()
        self.discovery = discovery or MobileDiscovery()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._listen_host: str | None = None
        self._listen_port: int | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    def _endpoint(self, settings: Settings) -> tuple[str, int]:
        host = (settings.mobile_access_bind_host or DEFAULT_BIND_HOST).strip()
        port = int(settings.mobile_access_port or DEFAULT_MOBILE_PORT)
        return host, port

    def needs_sync(self, settings: Settings | None = None) -> bool:
        """True when listener state must change to match settings."""
        settings = settings or self.vault.settings
        host, port = self._endpoint(settings)
        want = bool(settings.mobile_access_enabled)
        if want != self.is_running:
            return True
        if want and (self._listen_host != host or self._listen_port != port):
            return True
        return False

    def sync(self, settings: Settings | None = None) -> None:
        """Start or stop the listener to match ``settings``."""
        settings = settings or self.vault.settings
        if not self.needs_sync(settings):
            return
        host, port = self._endpoint(settings)
        self.stop()
        if settings.mobile_access_enabled:
            self._start(host, port)

    def stop(self) -> None:
        try:
            self.discovery.stop()
        except Exception:  # noqa: BLE001
            pass
        srv = self._server
        self._server = None
        self._listen_host = None
        self._listen_port = None
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:  # noqa: BLE001
                pass
            try:
                srv.server_close()
            except Exception:  # noqa: BLE001
                pass
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.25)

    def _start(self, host: str, port: int) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:  # noqa: D401
                pass  # never log request bodies or clip content

            def do_GET(self) -> None:
                code, body = bridge.handle(
                    "GET", self.path, dict(self.headers),
                    remote_ip=self.client_address[0],
                )
                if isinstance(body, BinaryResponse):
                    self.send_response(code)
                    self.send_header("Content-Type", body.content_type)
                    self.send_header("Content-Length", str(len(body.data)))
                    self.end_headers()
                    self.wfile.write(body.data)
                    return
                payload = json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0) or 0)
                if length > MAX_POST_BODY_BYTES:
                    self._json(413, {"error": "payload_too_large",
                                     "message": "Request body too large."})
                    return
                raw = self.rfile.read(length) if length else b""
                body = None
                if raw:
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError:
                        body = None
                code, resp = bridge.handle(
                    "POST", self.path, dict(self.headers),
                    remote_ip=self.client_address[0],
                    body=body,
                )
                self._json(code, resp)

            def do_PUT(self) -> None:
                code, body = bridge.handle(
                    "PUT", self.path, dict(self.headers))
                self._json(code, body)

            def do_PATCH(self) -> None:
                code, body = bridge.handle(
                    "PATCH", self.path, dict(self.headers))
                self._json(code, body)

            def do_DELETE(self) -> None:
                code, body = bridge.handle(
                    "DELETE", self.path, dict(self.headers))
                self._json(code, body)

            def _json(self, code: int, body: dict) -> None:
                payload = json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        try:
            self._server = ThreadingHTTPServer((host, port), Handler)
        except OSError:
            self._server = None
            return
        self._listen_host = host
        self._listen_port = port
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="mobile-bridge", daemon=True)
        self._thread.start()
        import socket as _socket
        host_name = _socket.gethostname()
        threading.Thread(
            target=lambda: self.discovery.start(port, pc_name=host_name),
            name="mobile-discovery",
            daemon=True,
        ).start()

    # --- pairing (desktop-side) ------------------------------------------------
    def pair_device(self, device_id: str, device_name: str,
                    settings: Settings | None = None) -> tuple[PairedDevice, str]:
        """Register a device and return ``(record, plaintext_token)`` once."""
        settings = settings or self.vault.settings
        token = new_device_token()
        device = PairedDevice(
            device_id=device_id.strip(),
            device_name=(device_name or "Android device").strip(),
            created_at=models.now_iso(),
            token_hash=hash_token(token),
        )
        settings.paired_devices = [
            d for d in settings.paired_devices
            if d.get("device_id") != device.device_id
        ]
        settings.paired_devices.append(device.to_dict())
        settings.save()
        return device, token

    def revoke_device(self, device_id: str, settings: Settings | None = None) -> bool:
        settings = settings or self.vault.settings
        changed = False
        now = models.now_iso()
        updated: list[dict] = []
        for raw in settings.paired_devices:
            d = PairedDevice.from_dict(raw)
            if d.device_id == device_id and d.revoked_at is None:
                d.revoked_at = now
                changed = True
            updated.append(d.to_dict())
        if changed:
            settings.paired_devices = updated
            settings.save()
        return changed

    def revoke_all_active(self, settings: Settings | None = None) -> int:
        """Revoke every active paired device. Returns count revoked."""
        count = 0
        for d in self.active_devices(settings):
            if self.revoke_device(d.device_id, settings):
                count += 1
        return count

    def _refresh_paired_devices_from_disk(self) -> None:
        """Reload paired devices from disk so pairing/revoke works without restart."""
        path = getattr(self.vault.settings, "_persist_path", None)
        if path is None:
            return
        fresh = Settings.load(path)
        self.vault.settings.paired_devices = list(fresh.paired_devices)

    def _paired_devices_for_auth(self) -> list[dict]:
        self._refresh_paired_devices_from_disk()
        return self.vault.settings.paired_devices

    def active_devices(self, settings: Settings | None = None) -> list[PairedDevice]:
        if settings is None:
            self._refresh_paired_devices_from_disk()
        settings = settings or self.vault.settings
        out = []
        for raw in settings.paired_devices:
            d = PairedDevice.from_dict(raw)
            if d.is_active:
                out.append(d)
        return out

    # --- request handling ------------------------------------------------------
    def handle(self, method: str, path: str, headers: dict,
               remote_ip: str | None = None,
               body: dict | None = None) -> tuple[int, dict | BinaryResponse]:
        """Process one HTTP request. Used by the server and unit tests."""
        path_only, query = api_mod.parse_query(unquote(path))
        family = api_mod.route_family(path_only)
        action = api_mod.action_for_route(family or path_only, method)
        header_device_id = headers.get("X-Device-Id") or headers.get("x-device-id")

        if not self.vault.settings.mobile_access_enabled:
            rec = api_mod.reject_receipt(
                path_only, action, "denied", "mobile_access_disabled",
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 503, {"error": "mobile_access_disabled",
                         "message": "Mobile Access is disabled."}

        allowed_post = (
            method == "POST"
            and (
                family in api_mod.RECEIPT_POST_ROUTES
                or family in api_mod.INBOX_POST_ROUTES
            )
        )
        if method != "GET" and not allowed_post:
            rec = api_mod.reject_receipt(
                path_only, action, "denied", "method_not_allowed",
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 405, {"error": "method_not_allowed",
                         "message": "Read-only API: GET only except inbox send."}

        if api_mod.is_forbidden_route(path_only):
            rec = api_mod.reject_receipt(
                path_only, action, "denied", "forbidden_route",
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 404, {"error": "not_found"}

        device, auth_reason = self._authenticate(headers)
        if device is None:
            rec = api_mod.reject_receipt(
                path_only, action, "denied", auth_reason or "unpaired",
                device_id=header_device_id, remote_ip=remote_ip)
            self.receipts.record(rec)
            return 401, {"error": "unauthorized", "message": auth_reason}

        if family is None:
            rec = self._ok_receipt(path_only, action, device)
            self.receipts.record(rec)
            return 404, {"error": "not_found"}

        with self.vault.storage._lock:
            if method == "POST" and family in api_mod.INBOX_POST_ROUTES:
                status, resp_body = self._dispatch_inbox_post(
                    family, path_only, device, body or {})
            elif method == "POST":
                status, resp_body = self._dispatch_receipt_post(
                    family, path_only, device)
            else:
                status, resp_body = self._dispatch_get(
                    family, path_only, query, device)
        clip_id = self._clip_id_from_response(resp_body, path_only)
        rec = MobileAccessReceipt.make(
            action=action, route=path_only,
            result="ok" if status < 400 else "error",
            device_id=device.device_id, device_name=device.device_name,
            clip_id=clip_id,
            remote_ip=remote_ip,
            reason=None if status < 400 else (
                resp_body.get("error") if isinstance(resp_body, dict) else "error"
            ),
        )
        self.receipts.record(rec)
        self._touch_device(device)
        return status, resp_body

    @staticmethod
    def _clip_id_from_response(body: dict | BinaryResponse,
                               path: str) -> str | None:
        if isinstance(body, BinaryResponse):
            return body.clip_id
        if not isinstance(body, dict):
            return None
        clip_id = body.get("clip_id")
        if clip_id is None and isinstance(body.get("clip"), dict):
            clip_id = body["clip"].get("id")
        if clip_id is None and "clips" in body and len(body["clips"]) == 1:
            clip_id = body["clips"][0].get("id")
        if clip_id is None:
            m = re.match(r"^/mobile/v1/clips/([a-f0-9]+)(?:/asset)?$", path)
            if m:
                clip_id = m.group(1)
        return clip_id

    def _ok_receipt(self, route: str, action: str, device: PairedDevice):
        return MobileAccessReceipt.make(
            action=action, route=route, result="denied",
            device_id=device.device_id, device_name=device.device_name,
            reason="not_found")

    def _authenticate(self, headers: dict) -> tuple[PairedDevice | None, str | None]:
        device_id = headers.get("X-Device-Id") or headers.get("x-device-id")
        auth = headers.get("Authorization") or headers.get("authorization") or ""
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not device_id or not token:
            return None, "Pairing required. Send X-Device-Id and Authorization Bearer token."
        th = hash_token(token)
        for raw in self._paired_devices_for_auth():
            d = PairedDevice.from_dict(raw)
            if d.device_id != device_id:
                continue
            if d.revoked_at is not None:
                return None, "Device revoked."
            if d.token_hash != th:
                return None, "Invalid device token."
            return d, None
        return None, "Unpaired device."

    def _touch_device(self, device: PairedDevice) -> None:
        now = models.now_iso()
        settings = self.vault.settings
        updated = []
        for raw in settings.paired_devices:
            d = PairedDevice.from_dict(raw)
            if d.device_id == device.device_id:
                d.last_seen_at = now
            updated.append(d.to_dict())
        settings.paired_devices = updated
        settings.save()

    def _dispatch_get(self, family: str, path: str, query: dict,
                      device: PairedDevice) -> tuple[int, dict | BinaryResponse]:
        from ... import __version__

        storage = self.vault.storage

        if family == "/mobile/v1/status":
            return 200, {
                "product": "Cache Vault",
                "byline": "A Proof Foundry companion app",
                "mobile_api_version": MOBILE_API_VERSION,
                "mobile_access_enabled": True,
                "cache_vault_version": __version__,
                "device_id": device.device_id,
                "read_only": True,
            }

        if family == "/mobile/v1/clips":
            clips = self.vault.list_clips(FILTER_ALL)
            return 200, {
                "clips": [api_mod.clip_to_api(c, storage=storage) for c in clips],
                "count": len(clips),
            }

        if family == "/mobile/v1/clips/{id}":
            m = _CLIP_ID_RE.match(path)
            clip_id = m.group(1) if m else ""
            clip = storage.get_clip(clip_id)
            if clip is None:
                return 404, {"error": "not_found", "clip_id": clip_id}
            return 200, {
                "clip": api_mod.clip_to_api(clip, full_content=True, storage=storage),
            }

        if family == "/mobile/v1/clips/{id}/asset":
            m = re.match(r"^/mobile/v1/clips/([a-f0-9]+)/asset$", path)
            clip_id = m.group(1) if m else ""
            clip = storage.get_clip(clip_id)
            if clip is None:
                return 404, {"error": "not_found", "clip_id": clip_id}
            if clip.content_type != models.CONTENT_IMAGE:
                return 404, {
                    "error": "asset_not_available",
                    "clip_id": clip_id,
                    "message": "This clip has no image asset.",
                }
            if not api_mod.clip_has_asset(clip, storage):
                return 404, {
                    "error": "asset_not_available",
                    "clip_id": clip_id,
                    "message": "No retrievable image asset for this clip.",
                }
            loaded = storage.load_clip_asset_bytes(clip_id)
            if loaded is None:
                return 404, {
                    "error": "asset_not_available",
                    "clip_id": clip_id,
                    "message": "Image file missing on PC.",
                }
            data, mime = loaded
            return 200, BinaryResponse(data=data, content_type=mime, clip_id=clip_id)

        if family == "/mobile/v1/search":
            q = (query.get("q") or [""])[0]
            sq = search.parse(q, FILTER_SEARCH_ALL)
            clips = self.vault.list_clips(sq)
            return 200, {
                "clips": [api_mod.clip_to_api(c, storage=storage) for c in clips],
                "count": len(clips),
                "q": q,
            }

        if family == "/mobile/v1/collections":
            return 200, {"collections": self.vault.list_collections()}

        if family == "/mobile/v1/favorites":
            clips = self.vault.list_clips(FILTER_FAVORITES)
            return 200, {
                "clips": [api_mod.clip_to_api(c, storage=storage) for c in clips],
                "count": len(clips),
            }

        if family == "/mobile/v1/recently-removed":
            clips = self.vault.list_clips(FILTER_RECENTLY_REMOVED)
            return 200, {
                "clips": [api_mod.clip_to_api(c, storage=storage) for c in clips],
                "count": len(clips),
            }

        if family == "/mobile/v1/inbox":
            clips = self.vault.list_mobile_inbox()
            return 200, {
                "items": [api_mod.clip_to_api(c, storage=storage) for c in clips],
                "count": len(clips),
            }

        return 404, {"error": "not_found"}

    def _dispatch_inbox_post(self, family: str, path: str,
                             device: PairedDevice,
                             payload: dict) -> tuple[int, dict]:
        from . import inbox as inbox_mod

        if family != "/mobile/v1/inbox/send":
            return 404, {"error": "not_found"}
        valid, err = inbox_mod.validate_send_payload(payload)
        if valid is None:
            return 400, {"error": "invalid_payload", "message": err}
        result = inbox_mod.receive_mobile_send(self.vault, device, valid)
        if not result.ok:
            return 400, result.to_response()
        return 200, result.to_response()

    def _dispatch_receipt_post(self, family: str, path: str,
                               device: PairedDevice) -> tuple[int, dict]:
        """Log copy/share receipts without mutating vault state."""
        m = re.match(r"^/mobile/v1/clips/([a-f0-9]+)/(copy|share|save)$", path)
        if m is None:
            return 404, {"error": "not_found"}
        clip_id = m.group(1)
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return 404, {"error": "not_found", "clip_id": clip_id}
        return 200, {"ok": True, "clip_id": clip_id, "action": family.split("/")[-1]}

    @staticmethod
    def allowed_routes() -> frozenset[str]:
        return (
            api_mod.READ_ONLY_ROUTES
            | api_mod.RECEIPT_POST_ROUTES
            | api_mod.INBOX_POST_ROUTES
        )
