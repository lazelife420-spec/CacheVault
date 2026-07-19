"""File + event receipts for Vault Cleanup Suggestions actions.

Mirrors capture_receipts.py / macro_receipts.py's convention exactly: a
JSON file under Receipts/ via write_file_receipt, plus a DB event via
EventLog.record so the action shows up in the existing "Stamped Receipts"
ledger UI, not just as an unreferenced file.

Privacy: never includes full clip content. Only clip_id, a shortened
content-hash fingerprint, classification, and per-item action/protection
reason -- matching the review's explicit privacy requirement.

Terminology: this receipt describes a move to Recently Removed, never a
permanent deletion. ``permanent_deletions`` and ``disk_bytes_reclaimed``
are always 0 here -- soft_delete is DB-only (confirmed directly against
storage.py), so no disk space is freed by this action. ``bytes_moved`` is
deliberately not called "recoverable" or "freed".
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from . import clip_metadata, models
from .editable_copies import write_file_receipt

if TYPE_CHECKING:
    from .cleanup_actions import CleanupSelection
    from .events import EventLog
    from .models import Clip

RULE_VERSIONS_KEY = "cleanup_suggestions_rule_version"


def record_cleanup_receipt(
    events: EventLog,
    *,
    rule_version: int,
    selections: list["CleanupSelection"],
    moved_clip_ids: list[str],
    skipped_protected: list[str],
    skipped_missing: list[str],
    bytes_moved: int,
    by_id: dict[str, "Clip"],
    kept_count: int | None = None,
    ignored_count: int | None = None,
) -> Path:
    groups_reviewed = len({(sel.category, sel.fingerprint) for sel in selections})
    items_reviewed = sum(len(sel.clip_ids) for sel in selections)

    item_records = []
    for clip_id in moved_clip_ids:
        clip = by_id.get(clip_id)
        item_records.append({
            "clip_id": clip_id,
            "content_hash": clip_metadata.shorten_hash(clip.content_hash) if clip else None,
            "classification": clip.classification if clip else None,
        })

    body = {
        "action": models.ACTION_CLEANUP_APPLIED,
        "timestamp": models.now_iso(),
        "success": True,
        RULE_VERSIONS_KEY: rule_version,
        "categories": sorted({sel.category for sel in selections}),
        "groups_reviewed": groups_reviewed,
        "items_reviewed": items_reviewed,
        "moved_count": len(moved_clip_ids),
        "kept_count": kept_count,
        "ignored_count": ignored_count,
        "protected_excluded_count": len(skipped_protected),
        "missing_skipped_count": len(skipped_missing),
        "bytes_moved": bytes_moved,
        "items": item_records,
        "protected_excluded_clip_ids": list(skipped_protected),
        "missing_clip_ids": list(skipped_missing),
        "destination": "recently_removed",
        "restoration_possible": True,
        "permanent_deletions": 0,
        "disk_bytes_reclaimed": 0,
    }
    body = {k: v for k, v in body.items() if v is not None}

    path = write_file_receipt(models.ACTION_CLEANUP_APPLIED, body)
    events.record(models.EVENT_CLEANUP_APPLIED, None, body)
    return path


def record_scan_receipt(
    events: EventLog,
    *,
    rule_version: int,
    duplicate_group_count: int,
    repeated_text_group_count: int,
    tiny_image_count: int,
    missing_or_damaged_count: int,
    largest_asset_count: int,
    redundant_bytes_identified: int,
    cancelled: bool,
) -> Path:
    """Lightweight receipt for a completed (or cancelled) scan itself --
    separate from the mutation receipt above, since scanning never
    changes any data.
    """
    body = {
        "action": "cleanup_scan_completed",
        "timestamp": models.now_iso(),
        "success": not cancelled,
        RULE_VERSIONS_KEY: rule_version,
        "duplicate_screenshot_groups": duplicate_group_count,
        "repeated_text_groups": repeated_text_group_count,
        "tiny_images": tiny_image_count,
        "missing_or_damaged_assets": missing_or_damaged_count,
        "largest_assets_shown": largest_asset_count,
        "redundant_bytes_identified": redundant_bytes_identified,
        "cancelled": cancelled,
    }
    path = write_file_receipt("cleanup_scan_completed", body)
    events.record(models.EVENT_CLEANUP_SCAN_COMPLETED, None, body)
    return path
