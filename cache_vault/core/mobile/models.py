"""Mobile Access data models — pairing and receipts."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from .. import models


# Default LAN port for the read-only mobile API (documented in settings UI).
DEFAULT_MOBILE_PORT = 8742

# Mobile bridge API version (see docs/MOBILE_API_CONTRACT.md).
MOBILE_API_VERSION = "1"

# When Mobile Access is enabled and bind host is empty, listen on all interfaces.
DEFAULT_BIND_HOST = "0.0.0.0"

# Honest product terminology for the mobile foundation.
PHONE_VAULT_LABEL = "Phone Vault"
MOBILE_INBOX_LABEL = "Mobile Inbox"
FROM_PHONE_LABEL = "From Phone"
SAVED_TO_PHONE_LABEL = "Saved to Phone"
ON_PC_LABEL = "On PC"
LAN_PAIRED_LABEL = "LAN paired"

TRANSFER_STATUS_COMPLETED = "completed"
TRANSFER_STATUS_FAILED = "failed"

DEVICE_STATUS_PAIRED = "Paired"
DEVICE_STATUS_ONLINE = "Online"
DEVICE_STATUS_OFFLINE = "Offline"
DEVICE_STATUS_WAITING_APPROVAL = "Waiting for phone approval"
DEVICE_STATUS_REVOKED = "Revoked"


def hash_token(token: str) -> str:
    """SHA-256 fingerprint of a device token. Plaintext is never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def sanitize_device_name(device_name: str | None) -> str:
    clean = (device_name or "Android device").strip()
    return clean or "Android device"


@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    created_at: str
    token_hash: str
    last_seen_at: str | None = None
    revoked_at: str | None = None
    app_version: str | None = None
    platform: str | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PairedDevice:
        return cls(
            device_id=data["device_id"],
            device_name=sanitize_device_name(data.get("device_name")),
            created_at=data["created_at"],
            token_hash=data["token_hash"],
            last_seen_at=data.get("last_seen_at"),
            revoked_at=data.get("revoked_at"),
            app_version=data.get("app_version"),
            platform=data.get("platform"),
        )


@dataclass
class MobileAccessReceipt:
    """Stamped receipt for a mobile API request (accepted or rejected)."""
    timestamp: str
    action: str
    route: str
    result: str
    device_id: str | None = None
    device_name: str | None = None
    clip_id: str | None = None
    reason: str | None = None
    remote_ip: str | None = None
    suggested_fix: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def make(cls, *, action: str, route: str, result: str, **kw) -> MobileAccessReceipt:
        reason = kw.get("reason")
        if kw.get("suggested_fix") is None and reason:
            from .connection_doctor import suggested_fix_for_reason
            kw["suggested_fix"] = suggested_fix_for_reason(reason)
        return cls(timestamp=models.now_iso(), action=action, route=route,
                   result=result, **kw)


def is_mobile_inbox_clip(clip) -> bool:
    """True when a clip belongs in the desktop Mobile Inbox."""
    return getattr(clip, "capture_mode", None) == models.CAPTURE_MOBILE_SHARE


def is_from_phone_clip(clip) -> bool:
    """True when a clip originated on a paired phone."""
    return getattr(clip, "capture_mode", None) in (
        models.CAPTURE_MOBILE,
        models.CAPTURE_MOBILE_SHARE,
    )


def pc_status_labels(clip, *, storage=None) -> list[str]:
    """Return status labels backed only by persisted or explicit data."""
    labels: list[str] = []
    if storage and hasattr(clip, "id") and storage.has_clip_asset(clip.id):
        labels.append(ON_PC_LABEL)
    if is_from_phone_clip(clip):
        labels.append(FROM_PHONE_LABEL)
    if bool(getattr(clip, "is_saved_to_phone", False)):
        labels.append(SAVED_TO_PHONE_LABEL)
    if bool(getattr(clip, "lan_paired", False)):
        labels.append(LAN_PAIRED_LABEL)
    return labels


def paired_device_status(device: PairedDevice, *, online_window_seconds: int = 120) -> str:
    """Return a truthful connection label from persisted pairing metadata only."""
    if device.revoked_at:
        return DEVICE_STATUS_REVOKED
    if not device.last_seen_at:
        return DEVICE_STATUS_WAITING_APPROVAL
    try:
        last_seen = datetime.fromisoformat(device.last_seen_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
    except Exception:  # noqa: BLE001
        return DEVICE_STATUS_PAIRED
    age_seconds = (now - last_seen).total_seconds()
    if age_seconds <= max(1, int(online_window_seconds)):
        return DEVICE_STATUS_ONLINE
    return DEVICE_STATUS_OFFLINE
