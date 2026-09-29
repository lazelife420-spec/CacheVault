"""Mobile Access bridge — gated read-only HTTP API for Cache Vault Mobile."""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Callable
from urllib.parse import unquote

from ... import brand
from .. import models, search, vault_lock
from ..settings import Settings
from ..storage import FILTER_ALL, FILTER_FAVORITES, FILTER_RECENTLY_REMOVED, FILTER_SEARCH_ALL
from . import api as api_mod
from .api import BinaryResponse
from .compatibility import ERROR_UPDATE_REQUIRED, evaluate_compatibility
from .models import (
    DEFAULT_BIND_HOST,
    DEFAULT_MOBILE_PORT,
    MOBILE_API_VERSION,
    MobileAccessReceipt,
    PairedDevice,
    hash_token,
    new_device_token,
    sanitize_device_name,
)
from .receipts import MobileReceiptLog
from .discovery import MobileDiscovery

if TYPE_CHECKING:
    from ..vault import Vault

_CLIP_ID_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)$")


def _coerce_int(value) -> int | None:
    """Best-effort int coercion for client-supplied handshake fields.

    Malformed input (wrong type, non-numeric string) must be treated as
    missing, not raise — the compatibility gate then handles it conservatively.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None

# Reject POST bodies larger than this before reading them. Image sends are
# capped at 10 MB decoded; base64 + JSON overhead fits comfortably under 20 MB.
MAX_POST_BODY_BYTES = 20 * 1024 * 1024


from .pairing_offer import PairingOffer, PairingOfferManager
from ..lan_ip import list_lan_ipv4, recommended_lan_ipv4

class MobileBridge:
    """Desktop-side read-only API for paired Android devices."""

    def __init__(self, vault: Vault, *, receipt_log: MobileReceiptLog | None = None,
                 discovery: MobileDiscovery | None = None,
                 lock_state_provider: Callable[[], vault_lock.VaultLockState] | None = None):
        self.vault = vault
        self.receipts = receipt_log or MobileReceiptLog()
        self.discovery = discovery or MobileDiscovery()
        # Without an app-owned session provider, resolve conservatively from
        # persisted settings: an enabled lock means this standalone bridge is
        # still locked because it has no successful UI authentication state.
        self._lock_state_provider = lock_state_provider or (
            lambda: vault_lock.get_vault_lock_state(self.vault.settings)
        )
        self.pairing_offers = PairingOfferManager()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._listen_host: str | None = None
        self._listen_port: int | None = None

    def create_pairing_offer(self, host: str | None = None) -> PairingOffer:
        if host is None:
            host = recommended_lan_ipv4(list_lan_ipv4()) or "127.0.0.1"
        port = self._listen_port or DEFAULT_MOBILE_PORT
        return self.pairing_offers.create_offer(host=host, port=port)

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
        # Verify: after stop the bridge must not appear running.
        if self._server is not None:
            self._server = None

    def verify_listening(self) -> bool:
        """Quick loopback health check — can we connect to our own port?"""
        if self._server is None or self._listen_port is None:
            return False
        import socket as _socket
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", self._listen_port))
            s.close()
            return True
        except OSError:
            return False

    def _start(self, host: str, port: int) -> bool:
        """Bind and start the HTTP listener.  Returns ``True`` on success.

        mDNS is **not** started here — the ``MobileAccessController``
        manages mDNS lifecycle separately so it can be verified independently.
        """
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
            return False
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
        return True

    # --- pairing (desktop-side) ------------------------------------------------
    def pair_device(self, device_id: str, device_name: str,
                    settings: Settings | None = None,
                    *,
                    app_version: str | None = None,
                    platform: str | None = None,
                    protocol: int | None = None,
                    device_model: str | None = None,
                    build: int | None = None) -> tuple[PairedDevice, str]:
        """Register a device and return ``(record, plaintext_token)`` once."""
        settings = settings or self.vault.settings
        token = new_device_token()
        device = PairedDevice(
            device_id=device_id.strip(),
            device_name=sanitize_device_name(device_name),
            created_at=models.now_iso(),
            token_hash=hash_token(token),
            app_version=app_version.strip() if app_version else None,
            platform=platform.strip() if platform else None,
            protocol=protocol,
            device_model=device_model.strip() if device_model else None,
            build=build,
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

    def all_devices(self, settings: Settings | None = None) -> list[PairedDevice]:
        """Every paired device record, including revoked ones.

        Revoked devices stay on disk (see revoke_device) so their status can
        still be shown honestly instead of silently disappearing from view.
        """
        if settings is None:
            self._refresh_paired_devices_from_disk()
        settings = settings or self.vault.settings
        return [PairedDevice.from_dict(raw) for raw in settings.paired_devices]

    # --- request handling ------------------------------------------------------
    def handle(self, method: str, path: str, headers: dict,
               remote_ip: str | None = None,
               body: dict | None = None) -> tuple[int, dict | BinaryResponse]:
        """Process one HTTP request. Used by the server and unit tests."""
        path_only, query = api_mod.parse_query(unquote(path))
        family = api_mod.route_family(path_only)
        action = api_mod.action_for_route(family or path_only, method)
        header_device_id = headers.get("X-Device-Id") or headers.get("x-device-id")

        # Security invariant: if settings say disabled we MUST NOT be running.
        # If we somehow are, force-stop immediately before processing.
        #
        # This must be synchronous. handle() always runs on a
        # ThreadingHTTPServer per-request worker thread (see the Handler
        # class in _start() below) — never the Tk/GUI thread — so blocking
        # here cannot freeze the UI. stop() itself already bounds its own
        # blocking (a shutdown() call plus a 0.25s-timeout thread.join()),
        # and the exact same stop() call is already made synchronously
        # elsewhere in this codebase (MobileAccessController.disable(),
        # invoked directly from GUI callbacks) with no issue. Dispatching
        # this to an unwaited background thread let handle() return its
        # 503 "disabled" response before the stop was guaranteed to have
        # completed, so a caller could observe is_running still True
        # immediately afterward — the exact race this invariant promises
        # not to allow.
        if not self.vault.settings.mobile_access_enabled:
            if self.is_running:
                self.stop()
            rec = api_mod.reject_receipt(
                path_only, action, "denied", "mobile_access_disabled",
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 503, {"error": "mobile_access_disabled",
                         "message": "Mobile Access is disabled."}

        if self._lock_state_provider() == vault_lock.VaultLockState.LOCKED:
            rec = api_mod.reject_receipt(
                path_only, action, "denied", "vault_locked",
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 423, {"error": "vault_locked",
                         "message": "Vault is locked."}

        allowed_post = (
            method == "POST"
            and (
                family in api_mod.RECEIPT_POST_ROUTES
                or family in api_mod.INBOX_POST_ROUTES
                or family in api_mod.PUBLIC_PAIR_POST_ROUTES
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

        if method == "POST" and family in api_mod.PUBLIC_PAIR_POST_ROUTES:
            status, resp_body = self._dispatch_public_pair_post(
                family, path_only, body or {})
            rec = MobileAccessReceipt.make(
                action=action, route=path_only,
                result="ok" if status < 400 else "error",
                device_id=resp_body.get("device_id") if isinstance(resp_body, dict) else None,
                device_name=resp_body.get("device_name") if isinstance(resp_body, dict) else None,
                remote_ip=remote_ip,
                reason=None if status < 400 else (
                    resp_body.get("error") if isinstance(resp_body, dict) else "error"
                ),
            )
            self.receipts.record(rec)
            return status, resp_body

        device, auth_reason = self._authenticate(headers)
        if device is None:
            rec = api_mod.reject_receipt(
                path_only, action, "denied", auth_reason or "unpaired",
                device_id=header_device_id, remote_ip=remote_ip)
            self.receipts.record(rec)
            return 401, {"error": "unauthorized", "message": auth_reason}

        # A valid token authenticates the device but does not, on its own,
        # authorize protected actions — an incompatible protocol/app version
        # blocks every route below, even ones that were previously reachable.
        # Scoped to devices that declared a mobile platform at pairing time:
        # the desktop CLI pairs itself as a PairedDevice too (cli.py) but
        # never participates in the Android version handshake, so it must
        # not be swept into this gate.
        device = self._refresh_device_handshake(device, headers)
        compat = (
            evaluate_compatibility(device.protocol, device.app_version)
            if device.platform
            else None
        )
        if compat is not None and not compat.compatible:
            self._touch_device(device)
            rec = api_mod.reject_receipt(
                path_only, action, "denied", ERROR_UPDATE_REQUIRED,
                device_id=device.device_id, device_name=device.device_name,
                remote_ip=remote_ip)
            self.receipts.record(rec)
            return 426, compat.to_error_response()

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

    def _refresh_device_handshake(self, device: PairedDevice,
                                  headers: dict) -> PairedDevice:
        """Refresh a paired device's protocol/app-version/build from headers.

        Lets an already-paired phone's compatibility state update on
        reconnect (e.g. after the app itself is updated) without requiring a
        full re-pair. Absent headers leave the stored values untouched.
        """
        app_version = headers.get("X-App-Version") or headers.get("x-app-version")
        build = headers.get("X-App-Build") or headers.get("x-app-build")
        protocol = headers.get("X-Protocol-Version") or headers.get("x-protocol-version")
        if app_version is None and build is None and protocol is None:
            return device
        if app_version is not None:
            device.app_version = str(app_version).strip() or device.app_version
        if build is not None:
            coerced = _coerce_int(build)
            if coerced is not None:
                device.build = coerced
        if protocol is not None:
            coerced = _coerce_int(protocol)
            if coerced is not None:
                device.protocol = coerced
        settings = self.vault.settings
        updated = []
        for raw in settings.paired_devices:
            d = PairedDevice.from_dict(raw)
            if d.device_id == device.device_id:
                d.app_version = device.app_version
                d.build = device.build
                d.protocol = device.protocol
            updated.append(d.to_dict())
        settings.paired_devices = updated
        settings.save()
        return device

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
            body = {
                "product": "Cache Vault",
                "byline": brand.MOBILE_BYLINE,
                "mobile_api_version": MOBILE_API_VERSION,
                "mobile_access_enabled": True,
                "cache_vault_version": __version__,
                "device_id": device.device_id,
                "read_only": True,
            }
            if device.platform:
                compat = evaluate_compatibility(device.protocol, device.app_version)
                body.update(compat.to_response())
            return 200, body

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

    def _dispatch_public_pair_post(self, family: str, path: str,
                                   payload: dict) -> tuple[int, dict]:
        if family != "/mobile/v1/pair-device":
            return 404, {"error": "not_found"}
        pairing_token = str(payload.get("pairing_token") or payload.get("token") or "").strip()
        if pairing_token:
            ok, reason = self.pairing_offers.consume_offer(pairing_token)
            if not ok:
                return 400, {
                    "error": "offer_expired_or_used",
                    "reason": reason,
                    "message": "Pairing offer has expired or already been consumed.",
                }

        device_id = str(payload.get("device_id") or "").strip() or models.new_id()
        device_obj = payload.get("device") if isinstance(payload.get("device"), dict) else {}
        device_name = sanitize_device_name(
            payload.get("device_name") or device_obj.get("name"))
        app_version = str(payload.get("app_version") or "").strip() or None
        platform = str(payload.get("platform") or "").strip() or None
        device_model = str(device_obj.get("model") or "").strip() or None
        protocol = _coerce_int(payload.get("protocol"))
        build = _coerce_int(payload.get("build"))

        result = evaluate_compatibility(protocol, app_version)
        if not result.compatible:
            return 426, result.to_error_response()

        device, token = self.pair_device(
            device_id,
            device_name,
            app_version=app_version,
            platform=platform,
            protocol=protocol,
            device_model=device_model,
            build=build,
        )
        response = {
            "device_id": device.device_id,
            "device_name": device.device_name,
            "token": token,
        }
        response.update(result.to_response())
        return 200, response

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
            | api_mod.PUBLIC_PAIR_POST_ROUTES
        )
