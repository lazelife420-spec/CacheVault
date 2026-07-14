"""File + event receipts for clipboard capture actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import models
from .editable_copies import write_file_receipt

if TYPE_CHECKING:
    from .events import EventLog


def _receipt_base(
    *,
    action: str,
    success: bool,
    clip_id: str | None = None,
    safe_id: str | None = None,
    safe_name: str | None = None,
    capture_mode: str | None = None,
    source_app: str | None = None,
    content_hash: str | None = None,
    item_type: str | None = None,
    warning: str | None = None,
    error: str | None = None,
    source_device: str | None = None,
    paired_device_id: str | None = None,
    transfer_status: str | None = None,
) -> dict:
    body = {
        "action": action,
        "timestamp": models.now_iso(),
        "success": success,
        "clip_id": clip_id,
        "safe_id": safe_id,
        "safe_name": safe_name,
        "capture_mode": capture_mode,
        "source_app": source_app,
        "hash": content_hash,
        "item_type": item_type,
        "source_device": source_device,
        "paired_device_id": paired_device_id,
        "transfer_status": transfer_status,
    }
    if warning:
        body["warning"] = warning[:200]
    if error:
        body["error"] = error[:200]
    return {k: v for k, v in body.items() if v is not None}


def record_capture_receipt(
    events: EventLog,
    *,
    action: str,
    event_type: str,
    success: bool,
    clip_id: str | None = None,
    safe_id: str | None = None,
    safe_name: str | None = None,
    capture_mode: str | None = None,
    source_app: str | None = None,
    content_hash: str | None = None,
    item_type: str | None = None,
    warning: str | None = None,
    error: str | None = None,
    source_device: str | None = None,
    paired_device_id: str | None = None,
    transfer_status: str | None = None,
) -> None:
    payload = _receipt_base(
        action=action,
        success=success,
        clip_id=clip_id,
        safe_id=safe_id,
        safe_name=safe_name,
        capture_mode=capture_mode,
        source_app=source_app,
        content_hash=content_hash,
        item_type=item_type,
        warning=warning,
        error=error,
        source_device=source_device,
        paired_device_id=paired_device_id,
        transfer_status=transfer_status,
    )
    write_file_receipt(action, payload)
    events.record(event_type, clip_id, payload)


def record_armed_receipt(
    events: EventLog,
    *,
    safe_id: str,
    safe_name: str,
) -> None:
    record_capture_receipt(
        events,
        action=models.ACTION_CLIPBOARD_NEXT_COPY_ARMED,
        event_type=models.EVENT_CLIPBOARD_NEXT_COPY_ARMED,
        success=True,
        safe_id=safe_id,
        safe_name=safe_name,
        capture_mode=models.CAPTURE_ARMED_NEXT_COPY,
    )


def record_ignored_receipt(
    events: EventLog,
    *,
    source_app: str | None = None,
    content_hash: str | None = None,
    item_type: str | None = None,
) -> None:
    record_capture_receipt(
        events,
        action=models.ACTION_CLIPBOARD_NEXT_COPY_IGNORED,
        event_type=models.EVENT_CLIPBOARD_NEXT_COPY_IGNORED,
        success=True,
        capture_mode=models.CAPTURE_AUTO,
        source_app=source_app,
        content_hash=content_hash,
        item_type=item_type,
    )


def record_sensitive_blocked(
    events: EventLog,
    *,
    source_app: str | None = None,
    content_hash: str | None = None,
    reason: str = "",
) -> None:
    record_capture_receipt(
        events,
        action="clipboard_sensitive_not_auto_saved",
        event_type=models.EVENT_CLIPBOARD_SENSITIVE_BLOCKED,
        success=False,
        capture_mode=models.CAPTURE_AUTO,
        source_app=source_app,
        content_hash=content_hash,
        warning="Sensitive-looking clipboard item was not auto-saved.",
        error=reason[:120] if reason else None,
    )
