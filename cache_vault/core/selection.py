"""Smart selection classification, summaries, and action mappings.

Also owns the "visible vs. matching" selection-scope machinery used by
context-menu/bulk-action commits: a "visible" selection is the concrete,
already-resolved id set the list/grid views track today (unchanged --
see clip_list.py/clip_grid.py). A "matching" selection is everything
satisfying the active nav/search/filter/sort context, represented as an
immutable query descriptor rather than a materialized id list -- ids are
only ever resolved, deduplicated, and processed in bounded batches right
before an action executes, and never just to show a count or a badge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, TypeVar
from cache_vault.core import models


_T = TypeVar("_T")


def dedupe_preserve_order(
    items: Iterable[_T], key: Callable[[_T], Any] | None = None,
) -> list[_T]:
    """Stable de-duplication: drops repeats, keeps first-seen order.

    ``key`` extracts the identity to dedupe on (defaults to the item
    itself), so the same helper works for flat id lists and for
    ``(selection, clip_id)``-style pairs where the clip_id is the
    identity but the whole pair must be kept.

    This is the single shared implementation every mutation/export/count/
    receipt path that consumes a caller-supplied id list must use --
    without it, a selection or input list containing the same id twice
    over-reports moved/deleted/selected counts (see issue #68: the
    Cleanup Suggestions mutation path built its ``to_move`` list without
    deduplicating, so a crafted or accidentally-doubled selection could
    double-count one clip in ``moved_count``/``bytes_moved``/the receipt).
    """
    if key is None:
        key = lambda x: x  # noqa: E731
    seen: set[Any] = set()
    out: list[_T] = []
    for item in items:
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def query_signature(nav_key: str, query: Any | None) -> tuple:
    """A stable, hashable fingerprint of everything that defines "the
    current matching set" for a view: nav/view key, filter name (which
    already encodes active-vs-Recently-Removed/Expired state -- see
    storage.py's ``_build_where``), free-text search, every structured
    filter field (type/source/window/url/domain/collection/sensitive/
    pinned/duplicate-only), and sort field + direction.

    Two calls against an unchanged context always compare equal; a
    change to search text, any filter, the active collection, sort, or
    navigation changes at least one element, so ``!=`` is exactly "the
    view a matching-selection was built against is no longer the current
    view." ``query=None`` (Home / a non-queryable screen) is its own
    distinct signature, not equal to any real query.
    """
    if query is None:
        return (nav_key, None)
    return (
        nav_key,
        query.filter_name,
        query.text,
        query.type_filter,
        query.source,
        query.window,
        query.source_url,
        query.domain,
        query.collection,
        query.sensitive,
        query.pinned,
        query.duplicate_only,
        query.sort,
        query.date_added_preset,
        query.date_used_preset,
        query.date_added_start,
        query.date_added_end,
        query.date_used_start,
        query.date_used_end,
    )


@dataclass(frozen=True)
class MatchingSelection:
    """An immutable descriptor for "every clip matching the active view",
    never a materialized id list. Created by resolving a fresh count at
    activation time (Ctrl+Shift+A); re-validated against the *current*
    context signature, and re-counted, immediately before any action
    consumes it -- a stored count/signature is a snapshot, not a promise.
    """

    nav_key: str
    query: Any  # a search.SearchQuery snapshot; caller must not mutate it after storing
    signature: tuple
    resolved_count: int
    resolved_at: str

    def is_stale(self, current_nav_key: str, current_query: Any | None) -> bool:
        return self.signature != query_signature(current_nav_key, current_query)


@dataclass(frozen=True)
class SelectionResolution:
    """The result of resolving a selection immediately before an action
    executes. ``stale=True`` means the active view no longer matches what
    a matching-selection was built against -- the caller MUST abort
    rather than reinterpret the old selection against the new view.

    For "matching" mode this never carries a materialized id list -- call
    ``iter_ids()`` to fetch deduplicated ids in bounded batches only when
    actually mutating/exporting/counting for a receipt.
    """

    mode: str  # "visible" | "matching" | "none"
    count: int
    stale: bool = False
    visible_ids: list[str] = field(default_factory=list)  # populated only for mode == "visible"
    _storage: Any = field(default=None, repr=False, compare=False)
    _query: Any = field(default=None, repr=False, compare=False)
    _batch_size: int = field(default=500, repr=False, compare=False)

    def iter_ids(self) -> Iterator[list[str]]:
        """Yield deduplicated id batches for this resolution. 'visible'
        mode yields its one already-concrete (and deduplicated) batch.

        'matching' mode streams from a single read-transaction snapshot
        (``storage.clip_id_snapshot``) that pairs a fresh count with
        every id batch computed against the exact same view of the
        table -- not independently-executed LIMIT/OFFSET queries, which
        can skip or duplicate rows if the matching set changes between
        batches. Because the count and every batch come from that one
        snapshot, the total unique ids enumerated is *provably* equal to
        the snapshot's own count, not just usually equal -- enforced
        below rather than assumed. Never call this on a stale resolution.
        """
        if self.stale:
            raise ValueError("cannot resolve ids from a stale selection")
        if self.mode == "visible":
            ids = dedupe_preserve_order(self.visible_ids)
            if ids:
                yield ids
            return
        if self.mode != "matching" or self._storage is None:
            return
        seen: set[str] = set()
        with self._storage.clip_id_snapshot(self._query, batch_size=self._batch_size) as (
            snapshot_count, batches,
        ):
            for batch in batches:
                fresh = [cid for cid in batch if cid not in seen]
                seen.update(fresh)
                if fresh:
                    yield fresh
            if len(seen) != snapshot_count:
                # Both numbers come from the same read transaction, so
                # this can only mean the snapshot machinery itself is
                # broken (e.g. a caller bypassed clip_id_snapshot's
                # transaction boundary) -- not a real-world race, which
                # the transaction already rules out by construction.
                raise AssertionError(
                    f"matching selection resolved {len(seen)} unique ids "
                    f"but its own read snapshot counted {snapshot_count} -- "
                    "snapshot consistency invariant violated"
                )

    def resolve_all_ids(self) -> list[str]:
        """Convenience for callers that genuinely need the full
        deduplicated id list at once (small/bounded selections only --
        prefer ``iter_ids()`` for anything that might be large)."""
        out: list[str] = []
        for batch in self.iter_ids():
            out.extend(batch)
        return out


class SelectionScope:
    """Owns the "matching" half of the selection-scope split for one
    window/session. "Visible" selection stays exactly where it already
    lived (ClipList/ClipGrid's own ``_selected_ids``, mirrored into
    ``_selected_clip_ids`` on the shell) -- this class is purely additive.
    """

    def __init__(self, storage: Any):
        self._storage = storage
        self._matching: MatchingSelection | None = None

    @property
    def mode(self) -> str:
        return "matching" if self._matching is not None else "none"

    @property
    def matching(self) -> MatchingSelection | None:
        return self._matching

    def activate_matching(self, nav_key: str, query: Any) -> MatchingSelection:
        """Ctrl+Shift+A: snapshot the current context and resolve a fresh
        count right now (no ids materialized). Replaces any prior matching
        selection outright rather than merging with it."""
        count = self._storage.count_clips(query)
        selection = MatchingSelection(
            nav_key=nav_key,
            query=query,
            signature=query_signature(nav_key, query),
            resolved_count=count,
            resolved_at=models.now_iso(),
        )
        self._matching = selection
        return selection

    def clear(self) -> None:
        self._matching = None

    def invalidate_if_stale(self, nav_key: str, query: Any | None) -> bool:
        """Called on every refresh (search/filter/sort/nav/collection/
        active-vs-removed change all flow through the same rebuilt query):
        drops a matching selection the instant its context no longer
        matches the current view. Returns True if something was cleared.
        Never silently reinterprets an old matching selection against a
        new view.
        """
        if self._matching is None:
            return False
        if self._matching.is_stale(nav_key, query):
            self._matching = None
            return True
        return False

    def resolve(
        self, nav_key: str, query: Any | None, *,
        visible_ids: list[str] | None = None, batch_size: int = 500,
    ) -> SelectionResolution:
        """The single resolver future bulk actions call immediately before
        mutating/exporting/counting. Re-verifies the stored signature
        against the caller's *current* context; on mismatch returns a
        stale resolution with count=0 and no ids -- the caller must abort
        and tell the user, never reuse the old selection against the new
        view. On a match, re-resolves the exact count fresh (never trusts
        the count cached at activation time).

        The returned ``.count`` is a fast preview (a single ``COUNT(*)``,
        no held transaction) -- fine for display (a confirmation dialog's
        "Move 47 matching items?"), but not itself the value a mutation
        should trust. When a caller actually calls ``iter_ids()`` to
        execute, that call takes its own read-transaction snapshot
        (``storage.clip_id_snapshot``) pairing a fresh count with every
        id batch from the identical view of the table, and verifies the
        two agree -- that snapshot count, not this preview one, is what
        an action must treat as authoritative.
        """
        if self._matching is not None:
            if self._matching.is_stale(nav_key, query):
                return SelectionResolution(mode="matching", count=0, stale=True)
            fresh_count = self._storage.count_clips(query)
            return SelectionResolution(
                mode="matching", count=fresh_count, stale=False,
                _storage=self._storage, _query=query, _batch_size=batch_size,
            )
        ids = dedupe_preserve_order(visible_ids or [])
        return SelectionResolution(mode="visible" if ids else "none", count=len(ids), visible_ids=ids)


@dataclass(frozen=True)
class SelectionSummary:
    """Headless summary of a selection of clips."""
    selected_count: int
    link_count: int
    image_count: int
    text_count: int
    selection_class: str  # "empty", "link_only", "image_only", "text_only", "mixed"
    summary_label: str
    available_actions: list[str] = field(default_factory=list)

    def get_toast_message(self, action: str, format_name: str | None = None) -> str:
        """Build a smart toast message for the selection action."""
        if self.selection_class == "empty":
            return "No items selected."

        if action == "copy":
            if self.selection_class == "link_only":
                fmt = f" as {format_name}" if format_name else ""
                return f"Copied {self.link_count} links{fmt}"
            elif self.selection_class == "image_only":
                return f"Copied {self.image_count} screenshots as PNG"
            elif self.selection_class == "text_only":
                fmt = f" as {format_name}" if format_name else ""
                return f"Copied {self.text_count} text clips{fmt}"
            else:
                return f"Copied {self.selected_count} selected items\n{self.summary_label}"

        elif action == "save_png":
            return f"Saved {self.image_count} screenshots as PNG"

        elif action == "export":
            if self.selection_class == "image_only":
                return f"Exported {self.image_count} screenshots as ZIP"
            elif self.selection_class == "link_only":
                return f"Exported {self.link_count} links"
            elif self.selection_class == "text_only":
                return f"Exported {self.text_count} text clips"
            else:
                return f"Exported mixed bundle\n{self.summary_label}"

        return f"Processed {self.selected_count} items"

    def get_receipt_metadata(self, action_name: str) -> dict[str, Any]:
        """Return metadata for stamped receipts."""
        return {
            "action": action_name,
            "selected_count": self.selected_count,
            "link_count": self.link_count,
            "image_count": self.image_count,
            "text_count": self.text_count,
            "selection_class": self.selection_class,
            "summary": self.summary_label,
        }


def is_image_clip(clip: Any) -> bool:
    """Check if a clip is an image/screenshot."""
    cls = getattr(clip, "classification", None)
    ct = getattr(clip, "content_type", None)
    if ct == models.CONTENT_IMAGE or cls == models.CLASS_IMAGE:
        return True
    if isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower()):
        return True
    return False


def is_link_clip(clip: Any) -> bool:
    """Check if a clip is a link."""
    return getattr(clip, "classification", None) == models.CLASS_LINK


def analyze_selection(clips: list[Any]) -> SelectionSummary:
    """Analyze a list of selected clips and return a SelectionSummary."""
    total = len(clips)
    if total == 0:
        return SelectionSummary(
            selected_count=0,
            link_count=0,
            image_count=0,
            text_count=0,
            selection_class="empty",
            summary_label="No items selected",
            available_actions=[],
        )

    links = 0
    images = 0
    texts = 0

    for clip in clips:
        if is_link_clip(clip):
            links += 1
        elif is_image_clip(clip):
            images += 1
        else:
            texts += 1

    # Classify selection
    if links == total:
        sel_class = "link_only"
        actions = [
            "Copy as Plain List",
            "Copy as Markdown",
            "Copy as Numbered List",
            "Save to Safe",
            "Create Receipt",
        ]
    elif images == total:
        sel_class = "image_only"
        actions = [
            "Copy PNG Files",
            "Save All As PNG",
            "Export ZIP",
            "Copy File Paths",
            "View Proof",
        ]
    elif texts == total:
        sel_class = "text_only"
        # Expose list/receipt options for text-only similar to links
        actions = [
            "Copy as Plain List",
            "Copy as Markdown",
            "Copy as Numbered List",
            "Save to Safe",
            "Create Receipt",
        ]
    else:
        sel_class = "mixed"
        actions = [
            "Export Bundle",
            "Copy Text + Links",
            "Save Screenshots",
            "Create Receipt",
            "Delete Selected",
        ]

    # Build summary label
    parts = []
    if links > 0:
        parts.append(f"{links} link" + ("s" if links != 1 else ""))
    if images > 0:
        parts.append(f"{images} screenshot" + ("s" if images != 1 else ""))
    if texts > 0:
        parts.append(f"{texts} text clip" + ("s" if texts != 1 else ""))

    summary_label = " · ".join(parts)

    return SelectionSummary(
        selected_count=total,
        link_count=links,
        image_count=images,
        text_count=texts,
        selection_class=sel_class,
        summary_label=summary_label,
        available_actions=actions,
    )
