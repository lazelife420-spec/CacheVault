"""Mobile Access data models — pairing and receipts."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field, asdict

from .. import models


# Default LAN port for the read-only mobile API (documented in settings UI).
DEFAULT_MOBILE_PORT = 8742

# Mobile bridge API version (see docs/MOBILE_API_CONTRACT.md).
MOBILE_API_VERSION = "1"

# When Mobile Access is enabled and bind host is empty, listen on all interfaces.
DEFAULT_BIND_HOST = "0.0.0.0"


def hash_token(token: str) -> str:
    """SHA-256 fingerprint of a device token. Plaintext is never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


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
            device_name=data.get("device_name") or "Android device",
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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def make(cls, *, action: str, route: str, result: str, **kw) -> MobileAccessReceipt:
        return cls(timestamp=models.now_iso(), action=action, route=route,
                   result=result, **kw)
