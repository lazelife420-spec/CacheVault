"""Vault Cleanup Suggestions v1 -- mutation layer (Stage C).

Moves selected, unprotected clips to Recently Removed via the existing
soft-delete path. Confirmed DB-only (a single ``UPDATE clips SET
deleted_at = ...`` per clip, no filesystem mutation -- see
cleanup_suggestions.py's module docstring and storage.py's soft_delete),
so a single transaction (loop of executes + one trailing commit, mirroring
``VaultStorage.prune_history``'s existing bulk-soft-delete pattern) is
genuinely atomic: either every selected clip moves, or none do.

Never permanently deletes anything. Permanent delete remains the existing,
separate ``hard_delete``/``permanently_remove`` action, untouched here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from . import models
from .cleanup_receipts import record_cleanup_receipt
from .cleanup_store import record_removed
from .events import EventLog
from .storage import VaultStorage


@dataclass
class CleanupSelection:
    """One group or bare item the caller chose to move, and which of its
    member clip ids were actually selected.

    This layer re-derives protection and asset state fresh, immediately
    before mutating -- it does not trust that the ids passed in are still
    safe to move (state may have changed since the review screen was
    populated, e.g. the user favorited something in another window).
    """

    category: str
    scope: str
    fingerprint: str
    clip_ids: list[str]


@dataclass
class CleanupApplyResult:
    moved_clip_ids: list[str] = field(default_factory=list)
    skipped_protected: list[str] = field(default_factory=list)
    skipped_missing: list[str] = field(default_factory=list)
    bytes_moved: int = 0
    cancelled: bool = False
    receipt_path: str | None = None

    @property
    def moved_count(self) -> int:
        return len(self.moved_clip_ids)


def apply_cleanup_selection(
    storage: VaultStorage,
    events: EventLog,
    *,
    selections: list[CleanupSelection],
    rule_version: int,
    scan_generation: str | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> CleanupApplyResult:
    """Move every unprotected, still-live clip named in [selections] to
    Recently Removed, record a historical "removed" decision for each, and
    write a cleanup receipt.

    Cancellation is only honored *before* the mutating transaction starts
    (see module docstring on cache_vault/core/cleanup_suggestions.py's
    ScanCancelled) -- once the loop of UPDATEs begins, it either commits in
    full or rolls back in full on an unexpected exception. There is no
    partial-commit path.
    """
    # Local import: cleanup_suggestions doesn't import this module, so this
    # avoids a needless import-time coupling for callers that only ever
    # scan and never mutate.
    from .cleanup_suggestions import build_scan_context

    cancel_check = cancel_check or (lambda: False)
    result = CleanupApplyResult()

    ctx = build_scan_context(storage)
    by_id = {c.id: c for c in ctx.live_clips}
    asset_bytes = {cid: int(row["size_bytes"] or 0) for cid, row in ctx.asset_rows.items()}

    to_move: list[tuple[CleanupSelection, str]] = []
    for sel in selections:
        for clip_id in sel.clip_ids:
            clip = by_id.get(clip_id)
            if clip is None:
                result.skipped_missing.append(clip_id)
                continue
            protection = ctx.protection_for(clip)
            if protection.protected:
                result.skipped_protected.append(clip_id)
                continue
            to_move.append((sel, clip_id))

    if cancel_check():
        result.cancelled = True
        return result

    if to_move:
        try:
            for _sel, clip_id in to_move:
                storage.conn.execute(
                    "UPDATE clips SET deleted_at = ? WHERE id = ?",
                    (models.now_iso(), clip_id),
                )
            storage.conn.commit()
        except Exception:
            storage.conn.rollback()
            raise

    for sel, clip_id in to_move:
        result.moved_clip_ids.append(clip_id)
        result.bytes_moved += asset_bytes.get(clip_id, 0)
        record_removed(
            storage,
            category=sel.category,
            scope=sel.scope,
            fingerprint=sel.fingerprint,
            clip_id=clip_id,
            rule_version=rule_version,
            scan_generation=scan_generation,
        )

    receipt_path = record_cleanup_receipt(
        events,
        rule_version=rule_version,
        selections=selections,
        moved_clip_ids=result.moved_clip_ids,
        skipped_protected=result.skipped_protected,
        skipped_missing=result.skipped_missing,
        bytes_moved=result.bytes_moved,
        by_id=by_id,
    )
    result.receipt_path = str(receipt_path) if receipt_path else None
    return result
