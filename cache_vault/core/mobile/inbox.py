"""Mobile-to-PC inbox — paired send-to-desktop for Cache Vault Mobile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import models, sensitive
from .. import clip_metadata
from ..capture_receipts import record_capture_receipt

if TYPE_CHECKING:
    from ..vault import Vault
    from .models import PairedDevice


ALLOWED_ITEM_TYPES = frozenset({"text", "url"})
ALLOWED_USER_ACTIONS = frozenset({"send_to_pc"})


@dataclass(frozen=True)
class InboxSendResult:
    ok: bool
    clip_id: str | None = None
    receipt_id: str | None = None
    safe_id: str | None = None
    safe_name: str | None = None
    warning: str | None = None
    error: str | None = None

    def to_response(self) -> dict[str, Any]:
        body: dict[str, Any] = {"success": self.ok}
        if self.clip_id:
            body["desktop_item_id"] = self.clip_id
            body["clip_id"] = self.clip_id
        if self.receipt_id:
            body["receipt_id"] = self.receipt_id
        if self.safe_id:
            body["safe_id"] = self.safe_id
        if self.safe_name:
            body["safe_name"] = self.safe_name
        if self.warning:
            body["warning"] = self.warning
        if self.error:
            body["error"] = self.error
        return body


def validate_send_payload(payload: dict | None) -> tuple[dict | None, str | None]:
    if not payload or not isinstance(payload, dict):
        return None, "JSON body required."
    content = (payload.get("content") or "").strip()
    if not content:
        return None, "content is required."
    item_type = (payload.get("item_type") or "text").strip().lower()
    if item_type not in ALLOWED_ITEM_TYPES:
        return None, f"Unsupported item_type: {item_type}"
    action = (payload.get("user_action") or "send_to_pc").strip().lower()
    if action not in ALLOWED_USER_ACTIONS:
        return None, f"Unsupported user_action: {action}"
    return payload, None


def receive_mobile_send(
    vault: Vault,
    device: PairedDevice,
    payload: dict,
) -> InboxSendResult:
    """Store a mobile-shared item in the desktop vault with receipts."""
    content = (payload.get("content") or "").strip()
    source_app = (payload.get("source_app") or device.device_name or "Mobile").strip()
    source_device = (payload.get("source_device_name") or device.device_name or "").strip()
    source_url = (payload.get("source_url") or "").strip() or None
    safe_id = (payload.get("safe_id") or payload.get("safe_name") or "").strip() or None

    sens = sensitive.detect(content)
    warning = None
    if sens.is_sensitive:
        warning = "Sensitive-looking content received from mobile. Stored locally with masking."

    clip = vault.capture_mobile_share(
        content,
        source_app=source_app,
        source_window=source_device or None,
        source_url=source_url,
        safe_id=safe_id,
        device_name=device.device_name,
        device_id=device.device_id,
        item_type=(payload.get("item_type") or "text").strip().lower(),
    )
    if clip is None:
        return InboxSendResult(ok=False, error="Could not save item to vault.")

    receipt_id = clip.id
    record_capture_receipt(
        vault.events,
        action=models.ACTION_MOBILE_INBOX_RECEIVED,
        event_type=models.EVENT_MOBILE_INBOX_RECEIVED,
        success=True,
        clip_id=clip.id,
        safe_id=clip.safe_id,
        safe_name=clip.safe_name,
        capture_mode=models.CAPTURE_MOBILE_SHARE,
        source_app=source_app,
        content_hash=clip.content_hash,
        item_type=clip.classification,
        warning=warning,
    )
    return InboxSendResult(
        ok=True,
        clip_id=clip.id,
        receipt_id=receipt_id,
        safe_id=clip.safe_id,
        safe_name=clip.safe_name,
        warning=warning,
    )
