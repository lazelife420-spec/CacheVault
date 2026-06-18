"""Stamped Receipts parsing, display, and export — proof ledger helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .. import brand
from ..core import models

ACTION_LABELS: dict[str, str] = {
    models.EVENT_CAPTURED: "Captured Clip",
    models.EVENT_COPIED_AGAIN: "Copied Again",
    models.EVENT_EXPORTED: "Exported",
    models.EVENT_ASSET_PERSISTED: "Asset Requested",
    models.EVENT_PINNED: "Pinned",
    models.EVENT_UNPINNED: "Unpinned",
    models.EVENT_FAVORITED: "Favorited",
    models.EVENT_UNFAVORITED: "Unfavorited",
    models.EVENT_MOVED_COLLECTION: "Moved to Collection",
    models.EVENT_RESTORED: "Restored",
    models.EVENT_PERMANENTLY_REMOVED: "Permanently Removed",
    models.EVENT_KEPT: "Marked Keep",
    models.EVENT_EXPIRED: "Expired",
    models.EVENT_DELETED: "Deleted",
    models.EVENT_REVEALED_SENSITIVE: "Revealed Sensitive",
    models.EVENT_CLEARED_SENSITIVE: "Cleared Sensitive",
    # mobile-style actions when stored in details
    "mobile_access": "Mobile Access",
    "get_asset": "Asset Requested",
    "asset_requested": "Asset Requested",
    "save_requested": "Save Requested",
    "share_requested": "Share Requested",
    "copy_requested": "Copy Requested",
    "duplicate_review": "Duplicate Review",
    models.EVENT_DUPLICATE_REVIEW: "Duplicate Review",
    models.EVENT_USAGE_MERGED: "Usage Merged",
    models.EVENT_EDITABLE_COPY_CREATED: "Editable Copy Created",
    models.EVENT_EDITABLE_COPY_SAVED: "Editable Copy Saved",
    models.EVENT_EDITABLE_HTML_COPY_CREATED: "HTML Bundle Copy Created",
    models.EVENT_EDITABLE_HTML_COPY_SAVED: "HTML Bundle Copy Saved",
    "editable_copy_created": "Editable Copy Created",
    "editable_copy_saved": "Editable Copy Saved",
    "editable_html_copy_created": "HTML Bundle Copy Created",
    models.EVENT_EXPORT_ZIP_CREATED: "Export Zip Created",
    models.EVENT_ITEM_EXPORTED: "Item Exported",
    models.EVENT_CLIPBOARD_AUTO_SAVED: "Clipboard Auto Saved",
    models.EVENT_CLIPBOARD_MANUAL_SAVED: "Clipboard Manual Saved",
    models.EVENT_CLIPBOARD_NEXT_COPY_ARMED: "Next Copy Armed",
    models.EVENT_CLIPBOARD_NEXT_COPY_SAVED: "Next Copy Saved",
    models.EVENT_CLIPBOARD_NEXT_COPY_IGNORED: "Next Copy Ignored",
    models.EVENT_CLIPBOARD_SENSITIVE_BLOCKED: "Sensitive Not Auto-Saved",
    models.EVENT_ITEM_MOVED_TO_SAFE: "Moved to Safe",
    models.EVENT_SAFE_CREATED: "Safe Created",
    "clipboard_auto_saved": "Clipboard Auto Saved",
    "clipboard_manual_saved": "Clipboard Manual Saved",
    "clipboard_next_copy_armed": "Next Copy Armed",
    "clipboard_next_copy_saved": "Next Copy Saved",
    "clipboard_next_copy_ignored": "Next Copy Ignored",
    "clipboard_sensitive_not_auto_saved": "Sensitive Not Auto-Saved",
    "item_moved_to_safe": "Moved to Safe",
    "safe_created": "Safe Created",
    "export_zip_created": "Export Zip Created",
    "list_clips": "Mobile Access",
    "get_clip": "Mobile Access",
    "search": "Mobile Access",
    "copy": "Copy Requested",
    "share": "Share Requested",
    "save": "Save Requested",
    "item_copied_clean": "Copied Clean Format",
    "item_context_action_used": "Context Action",
    "receipt_summary_copied": "Receipt Summary Copied",
}

FILTER_ALL = "All"
FILTER_TODAY = "Today"
FILTER_WEEK = "This Week"
FILTER_CAPTURED = "Captured"
FILTER_COPIED = "Copied Again"
FILTER_EXPORTS = "Exports"
FILTER_MOBILE = "Mobile Access"
FILTER_ASSETS = "Assets"
FILTER_DUPLICATE = "Duplicate Review"
FILTER_ERRORS = "Errors"

FILTER_CAPTURE_RULES = "Capture Rules"

FILTERS = (
    FILTER_ALL,
    FILTER_TODAY,
    FILTER_WEEK,
    FILTER_CAPTURED,
    FILTER_CAPTURE_RULES,
    FILTER_COPIED,
    FILTER_EXPORTS,
    FILTER_MOBILE,
    FILTER_ASSETS,
    FILTER_DUPLICATE,
    FILTER_ERRORS,
)

_LEGACY_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s+(\S+)(?:\s+(.*))?$"
)

_FORBIDDEN_DETAIL_KEYS = frozenset({
    "content", "token", "authorization", "bearer", "password", "secret",
})


@dataclass
class ReceiptRow:
    receipt_id: str
    timestamp: str
    action_raw: str
    action_label: str
    item_label: str
    content_type: str
    result: str
    proof_hash: str
    clip_id: str | None = None
    preview: str | None = None
    source: str | None = None
    route: str | None = None
    reason: str | None = None
    details: dict = field(default_factory=dict)
    legacy: bool = False


def humanize_action(action: str) -> str:
    if not action:
        return "Legacy Receipt"
    return ACTION_LABELS.get(action, action.replace("_", " ").title())


def shorten_hash(value: str) -> str:
    value = (value or "").strip()
    if len(value) <= 12:
        return value or "—"
    return f"{value[:4]}…{value[-5:]}"


def _safe_preview(text: str | None, *, sensitive: bool = False) -> str | None:
    if not text:
        return None
    if sensitive:
        return "(sensitive — hidden)"
    text = text.strip()
    if len(text) > 80:
        return text[:77] + "…"
    return text


def _infer_content_type(clip, details: dict) -> str:
    if clip is not None:
        return (clip.content_type or clip.classification or "text").upper()
    for key in ("content_type", "classification", "mime_type"):
        val = details.get(key)
        if val:
            return str(val).upper()
    return "—"


def _infer_result(action: str, details: dict) -> str:
    raw = details.get("result")
    if raw in ("ok", "success", "denied", "error"):
        return {"ok": "Success", "success": "Success", "denied": "Denied",
                "error": "Error"}[raw]
    if action in (models.EVENT_DELETED, models.EVENT_EXPIRED,
                  models.EVENT_PERMANENTLY_REMOVED):
        return "Success"
    if details.get("reason"):
        return "Error"
    return "Success"


def _proof_hash(event: dict, clip, details: dict) -> str:
    if clip is not None and clip.content_hash:
        return clip.content_hash
    for key in ("content_hash", "asset_sha256", "sha256", "token_hash"):
        val = details.get(key)
        if val:
            return str(val)
    return event.get("id", "")


def _item_label(action: str, clip, clip_id: str | None) -> str:
    if clip is not None:
        if clip.content_type == models.CONTENT_IMAGE:
            return "Image clip"
        if clip.classification == models.CLASS_LINK:
            return "Link clip"
        if clip.classification == models.CLASS_CODE:
            return "Code clip"
        return "Text clip"
    if action in (models.EVENT_EXPORTED,):
        return "Export"
    if clip_id:
        return f"Clip {shorten_hash(clip_id)}"
    return "—"


def _parse_timestamp(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def parse_legacy_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    m = _LEGACY_LINE_RE.match(line)
    if not m:
        return None
    ts, action, rest = m.group(1), m.group(2), (m.group(3) or "").strip()
    clip_id = None
    proof = rest
    if rest and " " in rest:
        parts = rest.split()
        if len(parts[0]) >= 8 and all(c in "abcdef0123456789" for c in parts[0].lower()):
            clip_id = parts[0]
            proof = parts[0]
    return {
        "id": proof[:32] or "legacy",
        "created_at": ts.replace(" ", "T") + "+00:00",
        "event_type": action,
        "clip_id": clip_id,
        "details": {},
        "_legacy": True,
    }


def event_to_row(event: dict, clip=None) -> ReceiptRow:
    details = dict(event.get("details") or {})
    action = event.get("event_type") or ""
    clip_id = event.get("clip_id")
    sensitive = bool(getattr(clip, "is_sensitive", False)) if clip else False
    preview = None
    if clip is not None:
        preview = _safe_preview(clip.preview or clip.content, sensitive=sensitive)
    proof = _proof_hash(event, clip, details)
    source = details.get("source_app") or details.get("device_name")
    route = details.get("route")
    reason = details.get("reason")
    return ReceiptRow(
        receipt_id=event.get("id", ""),
        timestamp=event.get("created_at", ""),
        action_raw=action,
        action_label=humanize_action(action),
        item_label=_item_label(action, clip, clip_id),
        content_type=_infer_content_type(clip, details),
        result=_infer_result(action, details),
        proof_hash=proof,
        clip_id=clip_id,
        preview=preview,
        source=str(source) if source else None,
        route=str(route) if route else None,
        reason=str(reason) if reason else None,
        details={k: v for k, v in details.items()
                 if k.lower() not in _FORBIDDEN_DETAIL_KEYS},
        legacy=bool(event.get("_legacy")),
    )


def rows_from_events(
    events: list[dict],
    *,
    get_clip: Callable[[str], Any] | None = None,
) -> list[ReceiptRow]:
    out: list[ReceiptRow] = []
    for event in events:
        clip = None
        cid = event.get("clip_id")
        if cid and get_clip:
            try:
                clip = get_clip(cid)
            except Exception:  # noqa: BLE001
                clip = None
        out.append(event_to_row(event, clip))
    return out


def _matches_filter(row: ReceiptRow, flt: str, now: datetime | None = None) -> bool:
    if flt == FILTER_ALL:
        return True
    now = now or datetime.now(timezone.utc)
    ts = _parse_timestamp(row.timestamp)
    if flt == FILTER_TODAY:
        if ts is None:
            return False
        return ts.date() == now.date()
    if flt == FILTER_WEEK:
        if ts is None:
            return False
        return ts >= now - timedelta(days=7)
    if flt == FILTER_CAPTURED:
        return row.action_raw == models.EVENT_CAPTURED
    if flt == FILTER_CAPTURE_RULES:
        return row.action_raw in {
            models.EVENT_CLIPBOARD_AUTO_SAVED,
            models.EVENT_CLIPBOARD_MANUAL_SAVED,
            models.EVENT_CLIPBOARD_NEXT_COPY_ARMED,
            models.EVENT_CLIPBOARD_NEXT_COPY_SAVED,
            models.EVENT_CLIPBOARD_NEXT_COPY_IGNORED,
            models.EVENT_CLIPBOARD_SENSITIVE_BLOCKED,
            models.EVENT_ITEM_MOVED_TO_SAFE,
            models.EVENT_SAFE_CREATED,
            "clipboard_auto_saved",
            "clipboard_manual_saved",
            "clipboard_next_copy_armed",
            "clipboard_next_copy_saved",
            "clipboard_next_copy_ignored",
            "clipboard_sensitive_not_auto_saved",
            "item_moved_to_safe",
            "safe_created",
        }
    if flt == FILTER_COPIED:
        return row.action_raw == models.EVENT_COPIED_AGAIN
    if flt == FILTER_EXPORTS:
        return row.action_raw == models.EVENT_EXPORTED
    if flt == FILTER_MOBILE:
        return row.action_raw in {"mobile_access", "list_clips", "get_clip", "search", "copy", "share", "save"}
    if flt == FILTER_ASSETS:
        return row.action_raw in {models.EVENT_ASSET_PERSISTED, "get_asset", "asset_requested"}
    if flt == FILTER_DUPLICATE:
        return row.action_raw == "duplicate_review"
    if flt == FILTER_ERRORS:
        return row.result in ("Error", "Denied")
    return True


def filter_rows(
    rows: list[ReceiptRow],
    *,
    flt: str = FILTER_ALL,
    query: str = "",
    now: datetime | None = None,
) -> list[ReceiptRow]:
    q = (query or "").strip().lower()
    out: list[ReceiptRow] = []
    for row in rows:
        if not _matches_filter(row, flt, now):
            continue
        if q:
            hay = " ".join(filter(None, [
                row.action_raw, row.action_label, row.proof_hash,
                row.clip_id or "", row.content_type, row.item_label,
                row.source or "", row.route or "", row.reason or "",
            ])).lower()
            if q not in hay:
                continue
        out.append(row)
    return out


def format_list_line(row: ReceiptRow) -> str:
    ts = (row.timestamp or "")[:19].replace("T", " ")
    return (
        f"{ts} | {row.action_label} | {row.item_label} | "
        f"{row.content_type} | {row.result} | {shorten_hash(row.proof_hash)}"
    )


def format_detail_text(row: ReceiptRow) -> str:
    lines = [
        f"Receipt ID: {row.receipt_id}",
        f"Timestamp: {(row.timestamp or '')[:19].replace('T', ' ')}",
        f"Action: {row.action_label}",
        f"Result: {row.result}",
    ]
    if row.clip_id:
        lines.append(f"Clip ID: {row.clip_id}")
    if row.content_type and row.content_type != "—":
        lines.append(f"Content type: {row.content_type}")
    if row.preview:
        lines.append(f"Preview: {row.preview}")
    lines.append(f"Full hash: {row.proof_hash}")
    if row.source:
        lines.append(f"Source/device: {row.source}")
    if row.route:
        lines.append(f"Route: {row.route}")
    if row.reason:
        lines.append(f"Reason: {row.reason}")
    if row.legacy:
        lines.append("Note: Parsed from legacy receipt format.")
    return "\n".join(lines)


def format_receipt_copy(row: ReceiptRow) -> str:
    return (
        f"{brand.PRODUCT_NAME}™\n"
        f"{brand.STUDIO_FOOTER}\n"
        f"{format_list_line(row)}\n"
        f"{brand.RECEIPT_NOTE}"
    )


def _branding_header() -> str:
    return (
        f"{brand.PRODUCT_NAME}™\n"
        f"{brand.STUDIO_FOOTER}\n"
        f"{brand.RECEIPT_NOTE}\n"
    )


def export_rows_txt(rows: list[ReceiptRow]) -> str:
    parts = [_branding_header(), ""]
    for row in rows:
        parts.append(format_list_line(row))
    return "\n".join(parts) + "\n"


def export_rows_json(rows: list[ReceiptRow]) -> str:
    payload = {
        "product": brand.PRODUCT_NAME,
        "studio": brand.STUDIO_FOOTER,
        "receipt_note": brand.RECEIPT_NOTE,
        "receipts": [
            {
                "receipt_id": r.receipt_id,
                "timestamp": r.timestamp,
                "action": r.action_label,
                "action_raw": r.action_raw,
                "result": r.result,
                "proof_hash": r.proof_hash,
                "clip_id": r.clip_id,
                "content_type": r.content_type,
                "preview": r.preview,
                "source": r.source,
                "route": r.route,
                "reason": r.reason,
            }
            for r in rows
        ],
    }
    return json.dumps(payload, indent=2)


def export_rows_html(rows: list[ReceiptRow]) -> str:
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;")
    body = "\n".join(
        f"<tr><td>{esc((r.timestamp or '')[:19])}</td>"
        f"<td>{esc(r.action_label)}</td>"
        f"<td>{esc(r.item_label)}</td>"
        f"<td>{esc(r.content_type)}</td>"
        f"<td>{esc(r.result)}</td>"
        f"<td>{esc(shorten_hash(r.proof_hash))}</td></tr>"
        for r in rows
    )
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{esc(brand.TERM_STAMPED_RECEIPTS)}</title></head><body>"
        f"<h1>{esc(brand.PRODUCT_NAME)}™</h1>"
        f"<p>{esc(brand.STUDIO_FOOTER)}</p>"
        f"<p><em>{esc(brand.RECEIPT_NOTE)}</em></p>"
        f"<table border='1' cellpadding='6'>"
        f"<tr><th>Time</th><th>Action</th><th>Item</th>"
        f"<th>Type</th><th>Result</th><th>Proof</th></tr>"
        f"{body}</table></body></html>"
    )


def export_rows(rows: list[ReceiptRow], fmt: str) -> str:
    fmt = (fmt or "txt").lower().lstrip(".")
    if fmt == "json":
        return export_rows_json(rows)
    if fmt == "html":
        return export_rows_html(rows)
    return export_rows_txt(rows)
