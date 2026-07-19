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
from .selection import dedupe_preserve_order
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


def _protect_duplicate_group_keepers(
    ctx, to_move: list[tuple[CleanupSelection, str]], result: CleanupApplyResult,
) -> list[tuple[CleanupSelection, str]]:
    """Defense-in-depth: never let a mutation remove every live copy of a
    duplicate-screenshot OR repeated-text group, even from a selection that
    didn't come through the review dialog's UI (whose disabled keeper
    checkbox is the *only* thing preventing this today -- confirmed by
    independent review of draft PR #67 to have no mutation-layer backstop).

    Both grouped categories share the identical recommended_keeper_id /
    disabled-checkbox design, so both need the same guard -- an earlier
    version of this function covered duplicate screenshots only, leaving
    repeated-text groups exposed to the exact same "wipe every copy" gap
    (caught live by a follow-up narrow re-review: a crafted selection
    naming all 3 members of a repeated_text group moved all 3, zero
    survivors, skipped_protected empty).

    Recomputes current, live group membership and keeper order fresh (the
    exact same find_duplicate_screenshot_groups / find_repeated_text_groups
    the scan engine uses, against this mutation's own freshly-built [ctx])
    rather than trusting anything about which items the caller labeled as
    a "group". If every member of a real group is present in [to_move],
    the recommended keeper is pulled out and reported as skipped/protected
    so at least one copy always survives; every other selected item in
    that group still moves normally.
    """
    from .cleanup_suggestions import (
        CATEGORY_DUPLICATE_SCREENSHOT,
        CATEGORY_REPEATED_TEXT,
        find_duplicate_screenshot_groups,
        find_repeated_text_groups,
    )

    grouped_finders = {
        CATEGORY_DUPLICATE_SCREENSHOT: find_duplicate_screenshot_groups,
        CATEGORY_REPEATED_TEXT: find_repeated_text_groups,
    }
    categories_in_play = {sel.category for sel, _ in to_move} & grouped_finders.keys()
    if not categories_in_play:
        return to_move

    moving_ids = {clip_id for _sel, clip_id in to_move}
    protected_keeper_ids: set[str] = set()
    for category in categories_in_play:
        for group in grouped_finders[category](ctx):
            member_ids = {it.clip.id for it in group.items}
            if member_ids and member_ids <= moving_ids and group.recommended_keeper_id is not None:
                protected_keeper_ids.add(group.recommended_keeper_id)

    if not protected_keeper_ids:
        return to_move

    kept: list[tuple[CleanupSelection, str]] = []
    for sel, clip_id in to_move:
        if sel.category in grouped_finders and clip_id in protected_keeper_ids:
            result.skipped_protected.append(clip_id)
            continue
        kept.append((sel, clip_id))
    return kept


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

    Every protection is re-derived fresh, right here, immediately before
    mutating -- never trusted from the scan snapshot the review screen was
    built from. This includes the "recently captured/used" window: a prior
    version of this function called ``build_scan_context`` with no
    ``recent_cutoff_iso``, so a clip that became recently-used *after* the
    scan but *before* the user confirmed the move (a real, if narrow, race
    -- e.g. re-copying the item in another window while the confirm dialog
    is open) was not re-checked and could be moved anyway. Confirmed live
    during independent review of draft PR #67; fixed by computing the same
    cutoff the scan engine uses, fresh, at call time. Also re-checks any
    "keep forever" decision recorded against the clip since the scan (e.g.
    the user marked it protected in one window while an older, now-stale
    selection from another window still names it) -- a "keep" (the
    temporary, current-scan-only decision) deliberately does NOT block a
    move here, since the fresh scan_generation this mutation loads decisions
    under will never match an older "keep"'s recorded generation.

    Cancellation is only honored *before* the mutating transaction starts
    (see module docstring on cache_vault/core/cleanup_suggestions.py's
    ScanCancelled) -- once the loop of UPDATEs begins, it either commits in
    full or rolls back in full on an unexpected exception. There is no
    partial-commit path.
    """
    # Local import: cleanup_suggestions doesn't import this module, so this
    # avoids a needless import-time coupling for callers that only ever
    # scan and never mutate.
    from datetime import datetime, timedelta, timezone

    from .cleanup_suggestions import RECENT_PROTECTION_MINUTES, build_scan_context

    cancel_check = cancel_check or (lambda: False)
    result = CleanupApplyResult()

    mutation_cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(minutes=RECENT_PROTECTION_MINUTES)
    ).isoformat()
    ctx = build_scan_context(storage, recent_cutoff_iso=mutation_cutoff_iso)
    by_id = {c.id: c for c in ctx.live_clips}
    asset_bytes = {cid: int(row["size_bytes"] or 0) for cid, row in ctx.asset_rows.items()}

    # Dedup first, across every selection combined, keeping first-seen
    # order -- a clip_id repeated within one CleanupSelection or across
    # two different ones must only ever be evaluated/moved once. Without
    # this, a crafted or accidentally-doubled selection double-counts one
    # clip in moved_count/bytes_moved/the receipt (issue #68, confirmed by
    # a regression test asserting a duplicated id does not inflate any of
    # selected/moved/receipt counts).
    flattened = dedupe_preserve_order(
        ((sel, clip_id) for sel in selections for clip_id in sel.clip_ids),
        key=lambda pair: pair[1],
    )

    to_move: list[tuple[CleanupSelection, str]] = []
    for sel, clip_id in flattened:
        clip = by_id.get(clip_id)
        if clip is None:
            result.skipped_missing.append(clip_id)
            continue
        protection = ctx.protection_for(clip)
        if protection.protected or ctx.is_item_suppressed(sel.category, clip_id):
            result.skipped_protected.append(clip_id)
            continue
        to_move.append((sel, clip_id))

    to_move = _protect_duplicate_group_keepers(ctx, to_move, result)
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
