"""Vault Cleanup Suggestions v1 -- read-only scan engine (Stage A).

Detects five deterministic suggestion categories without mutating any data:
exact duplicate screenshots, exact repeated text, tiny images, missing/
damaged assets, and largest managed assets.

Nothing in this module writes to the database or filesystem, deletes
anything, or touches a file outside CacheVault's own managed-asset
directory. Mutation (moving items to Recently Removed) is a later stage.

Managed-asset boundary
-----------------------
A clip counts as a "managed image asset" only when it has a row in
``clip_assets`` (``VaultStorage.has_clip_asset``). A clipboard-copied file
path whose text happens to end in ``.jpg``/``.png`` etc. is a *path-only
image reference* -- ``ClipKinds``-style classification may call it an image
reference, but CacheVault owns no bytes for it. Categories A, C, D, and E
only ever consider clips with a real ``clip_assets`` row; a path-only
reference's external file is never opened, hashed, validated, or touched.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import cleanup_store, image_assets, models
from .models import Clip
from .storage import VaultStorage
from .vault_macros import MacroStore

# Bumped whenever detection, keeper-order, or protection logic changes in a
# way that should invalidate previously-recorded "ignore" decisions. Stored
# alongside each decision (Stage B) so stale ignores can be re-surfaced.
RULE_VERSION = 1

CATEGORY_DUPLICATE_SCREENSHOT = "exact_duplicate_screenshot"
CATEGORY_REPEATED_TEXT = "repeated_text"
CATEGORY_TINY_IMAGE = "tiny_image"
CATEGORY_MISSING_ASSET = "missing_asset"
CATEGORY_LARGEST_ASSET = "largest_asset"

CATEGORIES = (
    CATEGORY_DUPLICATE_SCREENSHOT,
    CATEGORY_REPEATED_TEXT,
    CATEGORY_TINY_IMAGE,
    CATEGORY_MISSING_ASSET,
    CATEGORY_LARGEST_ASSET,
)

CONFIDENCE_SAFE = "safe"
CONFIDENCE_REVIEW = "review"
CONFIDENCE_CAUTION = "caution"

# Both dimensions must be strictly below this to flag as "tiny". Exactly
# 64x64 is NOT flagged -- see test_cleanup_suggestions.py for the boundary
# proof the design review asked for.
TINY_IMAGE_MAX_PX = 64

DEFAULT_LARGEST_ASSETS_LIMIT = 50

# Conservative "just captured, don't suggest touching it yet" window. Not a
# duplicate of Smart Folders' 7-day "Recent" filter (that's a browsing view,
# not a removal-protection rule) -- this is deliberately much shorter.
RECENT_PROTECTION_MINUTES = 15


def format_bytes(n: int) -> str:
    """Human-readable byte count for cleanup-suggestions UI copy. Shared so
    the Home card and the review screen render identical strings.
    """
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


class ScanCancelled(Exception):
    """Raised by a detector when ``cancel_check`` reports a cancellation request."""


def _check_cancel(cancel_check: Callable[[], bool]) -> None:
    if cancel_check():
        raise ScanCancelled()


# --- protection -------------------------------------------------------------


@dataclass
class ProtectionStatus:
    protected: bool
    reasons: list[str] = field(default_factory=list)


def _editable_copy_clip_ids(conn: sqlite3.Connection) -> set[str]:
    """Every clip id that has a live editable-copy reference -- one bulk
    query, not one per candidate item.

    This is the one cross-feature reference the audit found to be a real,
    persisted, queryable relationship -- everything else (events, receipts,
    mobile API payloads, export manifests) is audit-only history, not a
    live "in use elsewhere" signal.

    Measured impact of the per-item version this replaced: 1230 of 1233
    total SQL statements in a full scan against a ~1855-clip fixture came
    from this single check (found during independent review of draft PR
    #67) -- both ``evaluate_protection`` (once per candidate item) and
    ``_keeper_sort_key`` (again, once per item, during every duplicate-
    screenshot-group sort) queried it individually. Bulk-loading it here,
    alongside ``_managed_asset_rows`` and ``cleanup_store.load_active_decisions``,
    brings scan cost back to O(1) queries regardless of vault size.

    Takes a raw connection (not a VaultStorage) so a background scan thread
    can pass a dedicated read-only connection instead of the shared,
    possibly-concurrently-written-to ``storage.conn``.
    """
    try:
        rows = conn.execute("SELECT DISTINCT clip_id FROM editable_copies").fetchall()
        return {row["clip_id"] for row in rows}
    except sqlite3.OperationalError:
        # Table doesn't exist yet (feature never used on this vault) --
        # nothing to protect against.
        return set()


def _macro_content_hashes(macro_store: MacroStore | None) -> set[str]:
    """Best-effort "this clip's text matches a saved macro/text-expansion
    body" signal.

    Macros do not store a clip_id back-reference (confirmed by audit --
    ``vault_macros.py``'s "create macro from clip" copies text by value at
    creation time, then the two records are fully independent). Content-hash
    matching is therefore approximate: two different clips with identical
    text would both match the same macro. Callers must label this as
    best-effort, not an exact reference.
    """
    if macro_store is None:
        return set()
    try:
        macros = macro_store.load_all()
    except Exception:  # noqa: BLE001 -- macros.json is optional, never fatal to a scan
        return set()
    return {m.content_hash() for m in macros if m.body}


def evaluate_protection(
    clip: Clip,
    *,
    editable_copy_clip_ids: set[str],
    macro_content_hashes: set[str],
    recent_cutoff_iso: str | None,
) -> ProtectionStatus:
    """Determine whether [clip] must be protected from cleanup suggestions.

    [editable_copy_clip_ids] is bulk-preloaded once per scan (see
    ``_editable_copy_clip_ids``) rather than queried per clip here.

    Deliberately does NOT implement a "has notes" rule -- CacheVault has no
    notes feature (confirmed by audit), so that rule cannot be truthfully
    evaluated and is omitted rather than fabricated.

    Deliberately does NOT implement "current clipboard item" or "active
    export" protection -- neither has a reliable identifier in this
    codebase today (the only candidate, ``latest_clip()``, is an
    approximation the design review explicitly rejected). Omitted rather
    than approximated.
    """
    reasons: list[str] = []
    if clip.is_pinned:
        reasons.append("Favorite")
    if clip.collection:
        reasons.append(f'In collection "{clip.collection}"')
    if clip.content_hash and clip.content_hash in macro_content_hashes:
        reasons.append("Matches a saved macro/text-expansion (best-effort content match)")
    if clip.id in editable_copy_clip_ids:
        reasons.append("Referenced by an editable copy")
    if recent_cutoff_iso is not None:
        created = clip.created_at or ""
        used = clip.last_used_at or ""
        if created >= recent_cutoff_iso or used >= recent_cutoff_iso:
            reasons.append("Captured or used recently")
    return ProtectionStatus(protected=bool(reasons), reasons=reasons)


# --- managed-asset boundary --------------------------------------------------


def _managed_asset_rows(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    """All ``clip_assets`` rows keyed by clip_id -- the sole authority for
    "is this clip a managed image asset". One bulk query, not N+1 lookups.
    """
    rows = conn.execute(
        "SELECT clip_id, asset_id, mime_type, file_ext, size_bytes, sha256, "
        "storage_name, width, height FROM clip_assets"
    ).fetchall()
    return {row["clip_id"]: row for row in rows}


# --- shared scan context ------------------------------------------------------


@dataclass
class ScanContext:
    """Precomputed, shared-across-categories state so each detector doesn't
    redo the same bulk queries.
    """

    storage: VaultStorage
    conn: sqlite3.Connection
    live_clips: list[Clip]
    asset_rows: dict[str, sqlite3.Row]
    macro_content_hashes: set[str]
    editable_copy_clip_ids: set[str]
    recent_cutoff_iso: str | None
    cancel_check: Callable[[], bool]
    scan_generation: str
    decisions: dict[tuple[str, str, str, str], "cleanup_store.CleanupDecision"]

    def protection_for(self, clip: Clip) -> ProtectionStatus:
        return evaluate_protection(
            clip,
            editable_copy_clip_ids=self.editable_copy_clip_ids,
            macro_content_hashes=self.macro_content_hashes,
            recent_cutoff_iso=self.recent_cutoff_iso,
        )

    def is_item_suppressed(self, category: str, clip_id: str) -> bool:
        """Should this clip be hidden from [category]'s results because of
        a previously-recorded Keep / Keep forever / Ignore decision?

        Item-scoped decisions are keyed by the clip's own id as both the
        fingerprint and the clip_id column (see cleanup_screen.py's
        _fingerprint_for) -- stable across rescans and restarts since a
        clip's id never changes, and never accidentally shared with an
        unrelated clip that merely has matching bytes/text/dimensions.
        """
        key = (category, cleanup_store.SCOPE_ITEM, clip_id, clip_id)
        decision = self.decisions.get(key)
        return cleanup_store.is_decision_suppressed(
            decision, current_scan_generation=self.scan_generation,
        )

    def is_group_suppressed(self, category: str, fingerprint: str) -> bool:
        """Group-scoped suppression, checked against the group's *final*
        fingerprint (computed from its post-suppression membership). The
        review dialog's "Ignore suggestion" action records exactly this
        scope for the two grouped categories (see cleanup_screen.py's
        _group_fingerprints_for_selection / _decide_selected) -- Keep and
        Keep forever remain item-scoped (see _fingerprint_for), since those
        protect a specific clip rather than dismissing the suggestion.
        """
        key = (category, cleanup_store.SCOPE_GROUP, fingerprint, cleanup_store.GROUP_CLIP_ID_SENTINEL)
        decision = self.decisions.get(key)
        return cleanup_store.is_decision_suppressed(
            decision, current_scan_generation=self.scan_generation,
        )


def build_scan_context(
    storage: VaultStorage,
    *,
    conn: sqlite3.Connection | None = None,
    macro_store: MacroStore | None = None,
    recent_cutoff_iso: str | None = None,
    cancel_check: Callable[[], bool] | None = None,
    scan_generation: str | None = None,
) -> ScanContext:
    """[conn], if given, is used for every query instead of ``storage.conn``
    -- pass a dedicated read-only connection (``storage.reader_connection()``)
    when scanning from a background thread, since ``storage.conn`` may be
    concurrently written to by the main thread. Defaults to ``storage.conn``
    for callers that already know they're single-threaded (tests, CLI).

    [scan_generation], if given, is used as-is rather than minting a fresh
    one -- callers doing a "quiet" rescan immediately after a Keep/Keep
    forever/Ignore decision reuse the scan that's currently on screen, so a
    "keep" decision (scoped to the scan_generation it was recorded under)
    still suppresses on that immediate refresh. A genuinely new user-
    initiated scan always gets a fresh generation, which is what makes
    "keep" (unlike "keep forever") stop suppressing on the next real scan.
    """
    cancel_check = cancel_check or (lambda: False)
    active_conn = conn or storage.conn
    return ScanContext(
        storage=storage,
        conn=active_conn,
        live_clips=storage.list_clips(conn=active_conn),
        asset_rows=_managed_asset_rows(active_conn),
        macro_content_hashes=_macro_content_hashes(macro_store),
        editable_copy_clip_ids=_editable_copy_clip_ids(active_conn),
        recent_cutoff_iso=recent_cutoff_iso,
        cancel_check=cancel_check,
        scan_generation=scan_generation or models.new_id(),
        decisions=cleanup_store.load_active_decisions(active_conn),
    )


# --- suggestion dataclasses ---------------------------------------------------


@dataclass
class SuggestionItem:
    clip: Clip
    protection: ProtectionStatus
    asset_size_bytes: int = 0
    asset_width: int | None = None
    asset_height: int | None = None
    asset_missing: bool = False
    asset_zero_byte: bool = False
    asset_undecodable: bool = False


@dataclass
class SuggestionGroup:
    category: str
    fingerprint: str
    items: list[SuggestionItem]
    confidence: str
    recommended_keeper_id: str | None = None
    evidence: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def redundant_bytes(self) -> int:
        """Bytes represented by non-keeper items in this group.

        This is "redundant bytes identified", NOT "disk space reclaimed" --
        moving items to Recently Removed does not delete the underlying
        asset file (soft_delete is DB-only, confirmed against
        cache_vault/core/storage.py directly). Callers must use this value
        only under language like "redundant bytes identified" /
        "bytes represented by selected items", never "recoverable" or
        "free up N MB".
        """
        if self.recommended_keeper_id is None:
            return 0
        return sum(
            it.asset_size_bytes for it in self.items if it.clip.id != self.recommended_keeper_id
        )

    @property
    def preselectable_ids(self) -> list[str]:
        """Non-keeper, non-protected item ids -- the only ones this feature
        is ever allowed to preselect. Protected items and the keeper itself
        are never preselected, matching "never suggest removing every copy"
        and "never preselect protected items".
        """
        if self.recommended_keeper_id is None:
            return []
        return [
            it.clip.id
            for it in self.items
            if it.clip.id != self.recommended_keeper_id and not it.protection.protected
        ]


@dataclass
class CleanupScanResult:
    rule_version: int
    duplicate_screenshot_groups: list[SuggestionGroup] = field(default_factory=list)
    repeated_text_groups: list[SuggestionGroup] = field(default_factory=list)
    tiny_images: list[SuggestionItem] = field(default_factory=list)
    missing_or_damaged: list[SuggestionItem] = field(default_factory=list)
    largest_assets: list[SuggestionItem] = field(default_factory=list)
    cancelled: bool = False
    # Identifies the scan run that produced this result. A "keep" decision
    # records the generation it was made under and only suppresses while
    # that generation is reused (an immediate quiet rescan after the
    # decision); a genuinely fresh scan mints a new generation, which is
    # what makes "keep" (unlike "keep forever"/"ignored") stop suppressing
    # on the next real scan. See build_scan_context / ScanContext.
    scan_generation: str = ""

    @property
    def total_groups(self) -> int:
        return len(self.duplicate_screenshot_groups) + len(self.repeated_text_groups)

    @property
    def total_reviewable_items(self) -> int:
        return (
            sum(g.count for g in self.duplicate_screenshot_groups)
            + sum(g.count for g in self.repeated_text_groups)
            + len(self.tiny_images)
            + len(self.missing_or_damaged)
        )

    @property
    def redundant_bytes_identified(self) -> int:
        """Sum of redundant bytes across duplicate groups only -- the one
        category with a real "these bytes are redundant copies" claim.
        Tiny/missing/largest are visibility categories, not redundancy
        claims, and never contribute here.
        """
        return sum(g.redundant_bytes for g in self.duplicate_screenshot_groups)


# --- Category A: exact duplicate screenshots ---------------------------------


def _keeper_sort_key(item: SuggestionItem, ctx: ScanContext) -> tuple:
    """Recommended keeper order (highest priority first, so this key is
    used with reverse=True):
    favorite > collection member > referenced by another feature >
    most recently used > newest.

    "Has notes" is intentionally absent -- no notes feature exists.
    """
    clip = item.clip
    is_favorite = 1 if clip.is_pinned else 0
    in_collection = 1 if clip.collection else 0
    referenced = 1 if clip.id in ctx.editable_copy_clip_ids else 0
    last_used = clip.last_used_at or clip.updated_at or clip.created_at or ""
    return (is_favorite, in_collection, referenced, last_used, clip.created_at or "")


def find_duplicate_screenshot_groups(ctx: ScanContext) -> list[SuggestionGroup]:
    """Group managed image clips by exact asset SHA-256. Reuses the hash
    already computed and stored at capture time (``clip_assets.sha256`` /
    ``clips.content_hash``, which are the same value for image clips) --
    never rehashes.
    """
    by_hash: dict[str, list[Clip]] = {}
    for clip in ctx.live_clips:
        _check_cancel(ctx.cancel_check)
        row = ctx.asset_rows.get(clip.id)
        if row is None:
            continue  # not a managed asset -- path-only reference or non-image clip
        chash = row["sha256"] or clip.content_hash
        if not chash:
            continue
        by_hash.setdefault(chash, []).append(clip)

    groups: list[SuggestionGroup] = []
    for chash, clips in by_hash.items():
        _check_cancel(ctx.cancel_check)
        if len(clips) < 2:
            continue
        items = []
        for clip in clips:
            if ctx.is_item_suppressed(CATEGORY_DUPLICATE_SCREENSHOT, clip.id):
                continue
            row = ctx.asset_rows[clip.id]
            items.append(
                SuggestionItem(
                    clip=clip,
                    protection=ctx.protection_for(clip),
                    asset_size_bytes=int(row["size_bytes"] or 0),
                    asset_width=row["width"],
                    asset_height=row["height"],
                )
            )
        # A group is only a "duplicate" once its unsuppressed membership is
        # recomputed -- suppressing all-but-one copy leaves nothing left to
        # call a duplicate, and the group must disappear rather than show a
        # single lonely "copy".
        if len(items) < 2:
            continue
        items.sort(key=lambda it: _keeper_sort_key(it, ctx), reverse=True)
        keeper = items[0]
        member_ids = sorted(it.clip.id for it in items)
        fingerprint = models.content_hash(chash + "|" + ",".join(member_ids))
        if ctx.is_group_suppressed(CATEGORY_DUPLICATE_SCREENSHOT, fingerprint):
            continue
        groups.append(
            SuggestionGroup(
                category=CATEGORY_DUPLICATE_SCREENSHOT,
                fingerprint=fingerprint,
                items=items,
                confidence=CONFIDENCE_SAFE,
                recommended_keeper_id=keeper.clip.id,
                evidence={"sha256": chash, "copies": len(items)},
            )
        )
    groups.sort(key=lambda g: g.redundant_bytes, reverse=True)
    return groups


# --- Category B: exact repeated text clips -----------------------------------


def _line_ending_normalized_hash(content: str) -> str:
    """Normalize ONLY line endings (CRLF/CR -> LF) before hashing. Does not
    strip, casefold, or otherwise touch whitespace/case -- the design review
    was explicit that arbitrary whitespace must not be ignored and no
    semantic similarity is allowed. This is intentionally stricter than
    ``clip_metadata.normalized_hash`` (which also strips + casefolds), so
    that function is not reused here.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return models.content_hash(normalized)


def find_repeated_text_groups(ctx: ScanContext) -> list[SuggestionGroup]:
    by_hash: dict[str, list[Clip]] = {}
    for clip in ctx.live_clips:
        _check_cancel(ctx.cancel_check)
        if clip.content_type == models.CONTENT_IMAGE:
            continue
        if clip.id in ctx.asset_rows:
            continue  # belongs to the managed-image population, not text
        norm = _line_ending_normalized_hash(clip.content or "")
        by_hash.setdefault(norm, []).append(clip)

    groups: list[SuggestionGroup] = []
    for norm, clips in by_hash.items():
        _check_cancel(ctx.cancel_check)
        if len(clips) < 2:
            continue
        items = [
            SuggestionItem(clip=clip, protection=ctx.protection_for(clip))
            for clip in clips
            if not ctx.is_item_suppressed(CATEGORY_REPEATED_TEXT, clip.id)
        ]
        # Same rule as duplicate screenshots: fewer than 2 unsuppressed
        # copies left means it's no longer a "repeated" text clip.
        if len(items) < 2:
            continue
        # Recommend keeping the newest or a protected copy; never preselect
        # protected entries (handled by SuggestionGroup.preselectable_ids).
        items.sort(key=lambda it: (it.protection.protected, it.clip.created_at or ""), reverse=True)
        keeper = items[0]
        member_ids = sorted(it.clip.id for it in items)
        fingerprint = models.content_hash(norm + "|" + ",".join(member_ids))
        if ctx.is_group_suppressed(CATEGORY_REPEATED_TEXT, fingerprint):
            continue
        groups.append(
            SuggestionGroup(
                category=CATEGORY_REPEATED_TEXT,
                fingerprint=fingerprint,
                items=items,
                confidence=CONFIDENCE_REVIEW,
                recommended_keeper_id=keeper.clip.id,
                evidence={"normalized_hash": norm, "captures": len(items)},
            )
        )
    groups.sort(key=lambda g: g.count, reverse=True)
    return groups


# --- Category C: tiny-image review -------------------------------------------


def find_tiny_images(
    ctx: ScanContext, *, max_px: int = TINY_IMAGE_MAX_PX
) -> list[SuggestionItem]:
    """Managed images where both dimensions are strictly below [max_px].

    Exactly max_px x max_px is NOT flagged -- "below a threshold" means
    strictly less than, not less-than-or-equal. See
    test_cleanup_suggestions.py for the explicit boundary proof.
    """
    items: list[SuggestionItem] = []
    by_id = {c.id: c for c in ctx.live_clips}
    for clip_id, row in ctx.asset_rows.items():
        _check_cancel(ctx.cancel_check)
        clip = by_id.get(clip_id)
        if clip is None:
            continue
        w, h = row["width"], row["height"]
        if not w or not h:
            continue
        if w < max_px and h < max_px:
            if ctx.is_item_suppressed(CATEGORY_TINY_IMAGE, clip.id):
                continue
            items.append(
                SuggestionItem(
                    clip=clip,
                    protection=ctx.protection_for(clip),
                    asset_size_bytes=int(row["size_bytes"] or 0),
                    asset_width=w,
                    asset_height=h,
                )
            )
    items.sort(key=lambda it: (it.asset_width or 0) * (it.asset_height or 0))
    return items


# --- Category D: missing or damaged assets -----------------------------------


def _validate_asset_file(storage_name: str) -> tuple[bool, bool, bool]:
    """Cheap, per-scan-safe validation: existence, zero-byte, decodability.

    Deliberately does NOT recompute or compare SHA-256 against the stored
    hash -- that full-file rehash only happens in ``deep_validate_asset``,
    invoked explicitly by the user, never swept automatically on every scan.

    Returns (missing, zero_byte, undecodable).
    """
    path = image_assets.assets_dir() / storage_name
    if not path.is_file():
        return True, False, False
    size = path.stat().st_size
    if size == 0:
        return False, True, False
    try:
        data = path.read_bytes()
    except OSError:
        return True, False, False
    if not image_assets.is_decodable_image(data):
        return False, False, True
    return False, False, False


def find_missing_or_damaged_assets(ctx: ScanContext) -> list[SuggestionItem]:
    items: list[SuggestionItem] = []
    by_id = {c.id: c for c in ctx.live_clips}
    for clip_id, row in ctx.asset_rows.items():
        _check_cancel(ctx.cancel_check)
        clip = by_id.get(clip_id)
        if clip is None:
            continue
        missing, zero_byte, undecodable = _validate_asset_file(row["storage_name"])
        if not (missing or zero_byte or undecodable):
            continue
        if ctx.is_item_suppressed(CATEGORY_MISSING_ASSET, clip.id):
            continue
        items.append(
            SuggestionItem(
                clip=clip,
                protection=ctx.protection_for(clip),
                asset_size_bytes=int(row["size_bytes"] or 0),
                asset_width=row["width"],
                asset_height=row["height"],
                asset_missing=missing,
                asset_zero_byte=zero_byte,
                asset_undecodable=undecodable,
            )
        )
    return items


def deep_validate_asset(storage: VaultStorage, clip_id: str) -> dict:
    """Explicit, user-invoked deep validation for one asset: recomputes the
    SHA-256 of the on-disk bytes and compares it against the trusted stored
    hash. Never called automatically during a scan.
    """
    row = storage.get_asset_record(clip_id)
    if row is None:
        return {"clip_id": clip_id, "status": "no_asset_record"}
    path = image_assets.assets_dir() / row.storage_name
    if not path.is_file():
        return {"clip_id": clip_id, "status": "missing"}
    data = path.read_bytes()
    if not data:
        return {"clip_id": clip_id, "status": "zero_byte"}
    actual_hash = models.bytes_hash(data)
    if actual_hash != row.sha256:
        return {"clip_id": clip_id, "status": "hash_mismatch", "expected": row.sha256, "actual": actual_hash}
    if not image_assets.is_decodable_image(data):
        return {"clip_id": clip_id, "status": "undecodable"}
    return {"clip_id": clip_id, "status": "ok"}


# --- Category E: largest managed assets --------------------------------------


def find_largest_assets(
    ctx: ScanContext, *, limit: int = DEFAULT_LARGEST_ASSETS_LIMIT
) -> list[SuggestionItem]:
    """Visibility only -- never a redundancy claim, never preselected.

    The review dialog never offers Keep/Keep forever/Ignore actions for
    this category (it has no selection controls at all -- see
    cleanup_screen.py's ``can_select``), so no decision can be recorded
    against it through the UI today. The suppression check below is kept
    anyway for consistency with every other category and in case a
    decision is ever recorded against it by another path.
    """
    items: list[SuggestionItem] = []
    by_id = {c.id: c for c in ctx.live_clips}
    for clip_id, row in ctx.asset_rows.items():
        _check_cancel(ctx.cancel_check)
        clip = by_id.get(clip_id)
        if clip is None:
            continue
        if ctx.is_item_suppressed(CATEGORY_LARGEST_ASSET, clip.id):
            continue
        items.append(
            SuggestionItem(
                clip=clip,
                protection=ctx.protection_for(clip),
                asset_size_bytes=int(row["size_bytes"] or 0),
                asset_width=row["width"],
                asset_height=row["height"],
            )
        )
    items.sort(key=lambda it: it.asset_size_bytes, reverse=True)
    return items[:limit]


# --- orchestration ------------------------------------------------------------


def run_scan(
    storage: VaultStorage,
    *,
    conn: sqlite3.Connection | None = None,
    macro_store: MacroStore | None = None,
    recent_cutoff_iso: str | None = None,
    largest_assets_limit: int = DEFAULT_LARGEST_ASSETS_LIMIT,
    tiny_image_max_px: int = TINY_IMAGE_MAX_PX,
    cancel_check: Callable[[], bool] | None = None,
    scan_generation: str | None = None,
) -> CleanupScanResult:
    """Run all five detectors read-only. Checks cancellation between
    categories (and each detector checks between its own groups/items too).
    Never mutates the database or filesystem.

    Every previously-recorded Keep / Keep forever / Ignore decision is
    applied *before* groups, counts, and byte totals are computed -- a
    suppressed candidate never contributes to a group's size, the
    reviewable-item count, or redundant/represented bytes, and a group left
    with fewer than 2 unsuppressed copies disappears entirely. See
    ScanContext.is_item_suppressed / is_group_suppressed.

    [conn], if given, is used for every query instead of ``storage.conn`` --
    see ``build_scan_context`` for why a background-thread caller must pass
    a dedicated read-only connection here.

    [scan_generation], if given, is reused as-is (see build_scan_context);
    otherwise a fresh one is minted and returned on the result so the
    caller can pass it back into ``record_decision`` for a "keep" made
    against this exact scan.
    """
    cancel_check = cancel_check or (lambda: False)
    ctx = build_scan_context(
        storage,
        conn=conn,
        macro_store=macro_store,
        recent_cutoff_iso=recent_cutoff_iso,
        cancel_check=cancel_check,
        scan_generation=scan_generation,
    )
    result = CleanupScanResult(rule_version=RULE_VERSION, scan_generation=ctx.scan_generation)
    try:
        result.duplicate_screenshot_groups = find_duplicate_screenshot_groups(ctx)
        _check_cancel(cancel_check)
        result.repeated_text_groups = find_repeated_text_groups(ctx)
        _check_cancel(cancel_check)
        result.tiny_images = find_tiny_images(ctx, max_px=tiny_image_max_px)
        _check_cancel(cancel_check)
        result.missing_or_damaged = find_missing_or_damaged_assets(ctx)
        _check_cancel(cancel_check)
        result.largest_assets = find_largest_assets(ctx, limit=largest_assets_limit)
    except ScanCancelled:
        result.cancelled = True
    return result
