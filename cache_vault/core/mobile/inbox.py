"""Mobile-to-PC inbox — paired send-to-desktop for Cache Vault Mobile."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import image_assets, models, sensitive
from ..capture_receipts import record_capture_receipt
from .models import (
    TRANSFER_STATUS_COMPLETED,
    TRANSFER_STATUS_FAILED,
)

if TYPE_CHECKING:
    from ..vault import Vault
    from .models import PairedDevice


ALLOWED_ITEM_TYPES = frozenset({"text", "url", "image"})
ALLOWED_USER_ACTIONS = frozenset({"send_to_pc"})

# Cap mobile image sends at 10 MB decoded (binary), independent of base64 size.
MAX_MOBILE_IMAGE_BYTES = 10 * 1024 * 1024


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
    item_type = (payload.get("item_type") or "text").strip().lower()
    if item_type not in ALLOWED_ITEM_TYPES:
        return None, f"Unsupported item_type: {item_type}"
    action = (payload.get("user_action") or "send_to_pc").strip().lower()
    if action not in ALLOWED_USER_ACTIONS:
        return None, f"Unsupported user_action: {action}"
    if item_type == "image":
        mime_type = (payload.get("mime_type") or "").strip().lower()
        if mime_type not in image_assets.ALLOWED_IMAGE_MIME:
            return None, f"Unsupported image type: {mime_type or 'unknown'}"
        if not (payload.get("content_b64") or "").strip():
            return None, "content_b64 is required for images."
    else:
        if not (payload.get("content") or "").strip():
            return None, "content is required."
    return payload, None


def receive_mobile_send(
    vault: Vault,
    device: PairedDevice,
    payload: dict,
) -> InboxSendResult:
    """Store a mobile-shared item in the desktop vault with receipts."""
    item_type = (payload.get("item_type") or "text").strip().lower()
    if item_type == "image":
        return _receive_image(vault, device, payload)
    return _receive_text(vault, device, payload, item_type)


def record_failed_mobile_transfer(
    vault: Vault,
    device: PairedDevice,
    *,
    item_type: str | None,
    source_app: str | None,
    source_device: str | None,
    error: str,
) -> None:
    """Stamp a failed mobile-to-PC transfer without inventing success."""
    record_capture_receipt(
        vault.events,
        action=models.ACTION_MOBILE_INBOX_RECEIVED,
        event_type=models.EVENT_MOBILE_INBOX_RECEIVED,
        success=False,
        capture_mode=models.CAPTURE_MOBILE_SHARE,
        source_app=source_app,
        item_type=item_type,
        error=error,
        source_device=source_device,
        paired_device_id=device.device_id,
        transfer_status=TRANSFER_STATUS_FAILED,
    )


def _receive_text(
    vault: Vault,
    device: PairedDevice,
    payload: dict,
    item_type: str,
) -> InboxSendResult:
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
        item_type=item_type,
    )
    if clip is None:
        error = "Could not save item to vault."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type=item_type,
            source_app=source_app,
            source_device=source_device or device.device_name,
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    return _record_received(vault, clip, source_app, warning, device)


def _receive_image(
    vault: Vault,
    device: PairedDevice,
    payload: dict,
) -> InboxSendResult:
    mime_type = (payload.get("mime_type") or "").strip().lower()
    if mime_type not in image_assets.ALLOWED_IMAGE_MIME:
        error = "Unsupported image type."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=(payload.get("source_app") or device.device_name or "Mobile").strip(),
            source_device=(payload.get("source_device_name") or device.device_name or "").strip(),
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    try:
        image_bytes = base64.b64decode((payload.get("content_b64") or "").strip(), validate=True)
    except (binascii.Error, ValueError):
        error = "Image data was not valid base64."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=(payload.get("source_app") or device.device_name or "Mobile").strip(),
            source_device=(payload.get("source_device_name") or device.device_name or "").strip(),
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    if not image_bytes:
        error = "Image data was empty."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=(payload.get("source_app") or device.device_name or "Mobile").strip(),
            source_device=(payload.get("source_device_name") or device.device_name or "").strip(),
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    if len(image_bytes) > MAX_MOBILE_IMAGE_BYTES:
        error = "Image is too large (max 10 MB)."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=(payload.get("source_app") or device.device_name or "Mobile").strip(),
            source_device=(payload.get("source_device_name") or device.device_name or "").strip(),
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    if not image_assets.is_decodable_image(image_bytes):
        error = "File was not a readable image."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=(payload.get("source_app") or device.device_name or "Mobile").strip(),
            source_device=(payload.get("source_device_name") or device.device_name or "").strip(),
            error=error,
        )
        return InboxSendResult(ok=False, error=error)

    width, height = image_assets.image_dimensions(image_bytes)
    source_app = (payload.get("source_app") or device.device_name or "Mobile").strip()
    source_device = (payload.get("source_device_name") or device.device_name or "").strip()
    original_name = (
        payload.get("original_name") or payload.get("filename") or ""
    ).strip() or None
    safe_id = (payload.get("safe_id") or payload.get("safe_name") or "").strip() or None

    clip = vault.capture_mobile_image_share(
        image_bytes,
        mime_type=mime_type,
        original_name=original_name,
        source_app=source_app,
        source_window=source_device or None,
        safe_id=safe_id,
        device_name=device.device_name,
        device_id=device.device_id,
        width=width,
        height=height,
    )
    if clip is None:
        error = "Could not save image to vault."
        record_failed_mobile_transfer(
            vault,
            device,
            item_type="image",
            source_app=source_app,
            source_device=source_device or device.device_name,
            error=error,
        )
        return InboxSendResult(ok=False, error=error)
    return _record_received(vault, clip, source_app, None, device)


def _record_received(
    vault: Vault,
    clip,
    source_app: str,
    warning: str | None,
    device: PairedDevice | None = None,
) -> InboxSendResult:
    if device and device.device_id == models.CLI_DEVICE_ID:
        # Event and receipt are already logged in vault.capture_mobile_share / capture_mobile_image_share
        pass
    else:
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
            source_device=device.device_name if device else None,
            paired_device_id=device.device_id if device else None,
            transfer_status=TRANSFER_STATUS_COMPLETED,
        )
    return InboxSendResult(
        ok=True,
        clip_id=clip.id,
        receipt_id=clip.id,
        safe_id=clip.safe_id,
        safe_name=clip.safe_name,
        warning=warning,
    )
