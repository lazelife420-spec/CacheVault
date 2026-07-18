"""Vault Cleanup Suggestions v1 -- decision persistence (Stage B).

Per-item and per-group Keep / Keep forever / Ignore decisions, keyed by a
stable fingerprint so re-scans don't treat an unchanged group as new, and
so a group whose membership *does* change is correctly treated as new
(the caller recomputes the fingerprint each scan -- see
cleanup_suggestions.py's group fingerprints, which incorporate exact
membership, not just the shared content hash).

Decision semantics
-------------------
- ``keep``: suppress for the current scan result only. Tied to the scan
  that produced it (``scan_generation``) -- the next scan run is not
  suppressed by it.
- ``keep_forever``: persistent, item-level protection. Survives rescans,
  rule-version bumps, and restarts. Only cleared by an explicit
  un-keep-forever action.
- ``ignored``: suppress the current stable group/item until its
  membership or evidence changes. No separate invalidation logic is
  needed here -- the fingerprint itself encodes membership/evidence, so
  a changed group simply doesn't match this decision's stored fingerprint
  anymore and is treated as a fresh suggestion.
- ``removed``: historical outcome record only (the item was actually
  moved to Recently Removed). Not an active suppression rule by itself --
  a removed clip has ``deleted_at`` set and won't be produced by the scan
  engine's ``live_clips`` in the first place.
- ``rule_excluded``: intentionally NOT stored here. A whole-category
  opt-out is a global preference, not a per-item/per-group decision --
  it belongs in Settings (see Stage D), matching how scan thresholds are
  handled.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import models
from .storage import VaultStorage

DECISION_KEEP = "keep"
DECISION_KEEP_FOREVER = "keep_forever"
DECISION_IGNORED = "ignored"
DECISION_REMOVED = "removed"

SCOPE_ITEM = "item"
SCOPE_GROUP = "group"

_GROUP_CLIP_ID_SENTINEL = ""  # not NULL -- see storage.py's UNIQUE constraint note


@dataclass
class CleanupDecision:
    category: str
    scope: str
    fingerprint: str
    clip_id: str
    decision: str
    rule_version: int
    decided_at: str
    scan_generation: str | None


def record_decision(
    storage: VaultStorage,
    *,
    category: str,
    scope: str,
    fingerprint: str,
    decision: str,
    rule_version: int,
    clip_id: str | None = None,
    scan_generation: str | None = None,
) -> None:
    """Persist (or overwrite) a decision. Upserts on the same natural key
    (category, scope, fingerprint, clip_id) a rescan/re-decision would use.
    """
    cid = clip_id or _GROUP_CLIP_ID_SENTINEL
    storage.conn.execute(
        """
        INSERT INTO clip_cleanup_decisions (
            category, scope, fingerprint, clip_id, decision, rule_version,
            decided_at, scan_generation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(category, scope, fingerprint, clip_id) DO UPDATE SET
            decision = excluded.decision,
            rule_version = excluded.rule_version,
            decided_at = excluded.decided_at,
            scan_generation = excluded.scan_generation
        """,
        (category, scope, fingerprint, cid, decision, rule_version, models.now_iso(), scan_generation),
    )
    storage.conn.commit()


def get_decision(
    storage: VaultStorage,
    *,
    category: str,
    scope: str,
    fingerprint: str,
    clip_id: str | None = None,
) -> CleanupDecision | None:
    cid = clip_id or _GROUP_CLIP_ID_SENTINEL
    row = storage.conn.execute(
        "SELECT * FROM clip_cleanup_decisions "
        "WHERE category = ? AND scope = ? AND fingerprint = ? AND clip_id = ?",
        (category, scope, fingerprint, cid),
    ).fetchone()
    if row is None:
        return None
    return CleanupDecision(
        category=row["category"],
        scope=row["scope"],
        fingerprint=row["fingerprint"],
        clip_id=row["clip_id"],
        decision=row["decision"],
        rule_version=row["rule_version"],
        decided_at=row["decided_at"],
        scan_generation=row["scan_generation"],
    )


def is_suppressed(
    storage: VaultStorage,
    *,
    category: str,
    scope: str,
    fingerprint: str,
    clip_id: str | None = None,
    current_scan_generation: str | None = None,
) -> bool:
    """Should this item/group be hidden from the current scan result?

    ``keep_forever`` always suppresses. ``ignored`` suppresses as long as
    the fingerprint still matches (membership/evidence unchanged -- the
    caller is responsible for recomputing the fingerprint fresh each scan).
    ``keep`` only suppresses within the same scan_generation it was
    recorded under; a new scan run is not suppressed by an old "keep".
    ``removed`` never suppresses (it's a historical record, not a live
    filter -- the clip is already gone from live_clips by then anyway).
    """
    decision = get_decision(
        storage, category=category, scope=scope, fingerprint=fingerprint, clip_id=clip_id,
    )
    if decision is None:
        return False
    if decision.decision == DECISION_KEEP_FOREVER:
        return True
    if decision.decision == DECISION_IGNORED:
        return True
    if decision.decision == DECISION_KEEP:
        if current_scan_generation is None:
            return True
        return decision.scan_generation == current_scan_generation
    return False  # DECISION_REMOVED or anything unrecognized -- not an active filter


def clear_decision(
    storage: VaultStorage,
    *,
    category: str,
    scope: str,
    fingerprint: str,
    clip_id: str | None = None,
) -> None:
    """Explicit un-keep-forever / un-ignore action."""
    cid = clip_id or _GROUP_CLIP_ID_SENTINEL
    storage.conn.execute(
        "DELETE FROM clip_cleanup_decisions "
        "WHERE category = ? AND scope = ? AND fingerprint = ? AND clip_id = ?",
        (category, scope, fingerprint, cid),
    )
    storage.conn.commit()


def record_removed(
    storage: VaultStorage,
    *,
    category: str,
    scope: str,
    fingerprint: str,
    clip_id: str,
    rule_version: int,
    scan_generation: str | None = None,
) -> None:
    """Historical record: this specific item was moved to Recently Removed
    as part of a cleanup action. Not an active suppression rule -- see
    ``is_suppressed``.
    """
    record_decision(
        storage,
        category=category,
        scope=scope,
        fingerprint=fingerprint,
        clip_id=clip_id,
        decision=DECISION_REMOVED,
        rule_version=rule_version,
        scan_generation=scan_generation,
    )
