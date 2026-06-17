"""File + event receipts for Vault Macros actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import models
from .editable_copies import write_file_receipt

if TYPE_CHECKING:
    from .events import EventLog

FORBIDDEN_RECEIPT_KEYS = frozenset({"body", "content", "secret", "password", "token"})


def _scrub(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in FORBIDDEN_RECEIPT_KEYS}


def record_macro_receipt(
    events: EventLog,
    *,
    action: str,
    event_type: str,
    success: bool = True,
    macro_id: str | None = None,
    safe_id: str | None = None,
    safe_name: str | None = None,
    smart_type: str | None = None,
    template_id: str | None = None,
    warning: str | None = None,
    error: str | None = None,
    extra: dict | None = None,
) -> None:
    body = {
        "action": action,
        "timestamp": models.now_iso(),
        "success": success,
        "macro_id": macro_id,
        "safe_id": safe_id,
        "safe_name": safe_name,
        "smart_type": smart_type,
        "template_id": template_id,
    }
    if warning:
        body["warning"] = warning[:200]
    if error:
        body["error"] = error[:200]
    if extra:
        body.update(_scrub(extra))
    body = {k: v for k, v in body.items() if v is not None}
    write_file_receipt(action, body)
    events.record(event_type, macro_id, body)
