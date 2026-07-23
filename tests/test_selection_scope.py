"""Commit 1: visible vs. matching selection scope.

Covers the headless (Tk-independent) parts of the new selection layer:
the shared dedup helper, the query-signature/staleness machinery, the
id-only/chunked storage APIs, and SelectionScope's resolver contract.
Shell-level keyboard wiring (Ctrl+A / Ctrl+Shift+A / Escape / text-entry
guard) is covered separately in tests/test_shell_selection_keys.py.
"""

from __future__ import annotations

import pytest

from cache_vault.core import models
from cache_vault.core.models import Clip
from cache_vault.core.search import SearchQuery
from cache_vault.core.selection import (
    MatchingSelection,
    SelectionResolution,
    SelectionScope,
    dedupe_preserve_order,
    query_signature,
)
from cache_vault.core.storage import VaultStorage


# --- dedupe_preserve_order ------------------------------------------------


def test_dedupe_preserve_order_drops_repeats_keeps_first_seen_order():
    assert dedupe_preserve_order(["a", "b", "a", "c", "b", "a"]) == ["a", "b", "c"]


def test_dedupe_preserve_order_empty_and_no_dupes_are_noop():
    assert dedupe_preserve_order([]) == []
    assert dedupe_preserve_order(["x", "y", "z"]) == ["x", "y", "z"]


def test_dedupe_preserve_order_with_key_function_for_pairs():
    pairs = [("sel1", "a"), ("sel1", "a"), ("sel2", "a"), ("sel1", "b")]
    out = dedupe_preserve_order(pairs, key=lambda p: p[1])
    # First occurrence of each clip_id wins; whole pair is kept.
    assert out == [("sel1", "a"), ("sel1", "b")]


# --- query_signature -------------------------------------------------------


def test_query_signature_stable_for_unchanged_context():
    q1 = SearchQuery(filter_name="all", text="foo", sort=models.SORT_NEWEST_ADDED)
    q2 = SearchQuery(filter_name="all", text="foo", sort=models.SORT_NEWEST_ADDED)
    assert query_signature("all", q1) == query_signature("all", q2)


def test_query_signature_changes_with_search_text():
    base = SearchQuery(filter_name="all")
    changed = SearchQuery(filter_name="all", text="hello")
    assert query_signature("all", base) != query_signature("all", changed)


def test_query_signature_changes_with_type_filter():
    base = SearchQuery(filter_name="all")
    changed = SearchQuery(filter_name="all", type_filter=models.CLASS_LINK)
    assert query_signature("all", base) != query_signature("all", changed)


def test_query_signature_changes_with_date_filter():
    base = SearchQuery(filter_name="all")
    changed = SearchQuery(filter_name="all", date_added_preset="today")
    assert query_signature("all", base) != query_signature("all", changed)


def test_query_signature_changes_with_navigation_key():
    q = SearchQuery(filter_name="favorites")
    assert query_signature("favorites", q) != query_signature("screenshots", q)


def test_query_signature_changes_with_sort():
    base = SearchQuery(filter_name="all", sort=models.SORT_NEWEST_ADDED)
    changed = SearchQuery(filter_name="all", sort=models.SORT_OLDEST_ADDED)
    assert query_signature("all", base) != query_signature("all", changed)


def test_query_signature_changes_with_collection():
    base = SearchQuery(filter_name="all")
    changed = SearchQuery(filter_name="all", collection="Work")
    assert query_signature("all", base) != query_signature("all", changed)


def test_query_signature_changes_with_active_vs_recently_removed():
    from cache_vault.core.storage import FILTER_ALL, FILTER_RECENTLY_REMOVED

    q_active = SearchQuery(filter_name=FILTER_ALL)
    q_removed = SearchQuery(filter_name=FILTER_RECENTLY_REMOVED)
    assert query_signature("all", q_active) != query_signature("recently_removed", q_removed)


def test_query_signature_none_query_is_its_own_distinct_value():
    q = SearchQuery(filter_name="all")
    assert query_signature("home", None) != query_signature("home", q)
    assert query_signature("home", None) == query_signature("home", None)


# --- MatchingSelection.is_stale --------------------------------------------


def test_matching_selection_is_stale_detects_context_change():
    q = SearchQuery(filter_name="all")
    m = MatchingSelection(
        nav_key="all", query=q, signature=query_signature("all", q),
        resolved_count=5, resolved_at=models.now_iso(),
    )
    assert not m.is_stale("all", q)
    assert m.is_stale("all", SearchQuery(filter_name="all", text="new search"))
    assert m.is_stale("favorites", q)


# --- storage.list_clip_ids / iter_clip_ids ---------------------------------


def _add_clips(storage, n, prefix="clip"):
    ids = []
    for i in range(n):
        c = Clip(content=f"{prefix} {i}", preview=f"{prefix} {i}")
        storage.add_clip(c)
        ids.append(c.id)
    return ids


def test_list_clip_ids_matches_list_clips_ordering_and_filtering(storage):
    ids = _add_clips(storage, 10)
    by_id_query = storage.list_clip_ids(None)
    by_clip_query = [c.id for c in storage.list_clips(None)]
    assert by_id_query == by_clip_query
    assert set(by_id_query) == set(ids)


def test_list_clip_ids_respects_limit_and_offset(storage):
    _add_clips(storage, 10)
    all_ids = storage.list_clip_ids(None)
    page1 = storage.list_clip_ids(None, limit=4, offset=0)
    page2 = storage.list_clip_ids(None, limit=4, offset=4)
    assert page1 == all_ids[:4]
    assert page2 == all_ids[4:8]


def test_iter_clip_ids_yields_all_ids_in_bounded_batches(storage):
    ids = _add_clips(storage, 137)  # deliberately beyond a 120-style render cap
    batches = list(storage.iter_clip_ids(None, batch_size=50))
    assert [len(b) for b in batches] == [50, 50, 37]
    flattened = [cid for batch in batches for cid in batch]
    assert flattened == storage.list_clip_ids(None)
    assert len(flattened) == 137 == len(ids)


def test_iter_clip_ids_empty_query_yields_nothing(storage):
    assert list(storage.iter_clip_ids(None, batch_size=50)) == []


def test_list_clip_ids_never_touches_content_columns(storage, monkeypatch):
    """Sanity check that the SQL genuinely selects only `id` -- not a
    behavioral requirement testable via the public API alone, so this
    inspects the query text the way the existing test suite already
    inspects source for wiring checks elsewhere."""
    import inspect

    from cache_vault.core import storage as storage_module

    source = inspect.getsource(storage_module.VaultStorage.list_clip_ids)
    assert "SELECT id FROM clips" in source
    assert "SELECT *" not in source


# --- SelectionScope ---------------------------------------------------------


def test_selection_scope_starts_in_none_mode(storage):
    scope = SelectionScope(storage)
    assert scope.mode == "none"
    assert scope.matching is None


def test_selection_scope_activate_matching_resolves_fresh_count(storage):
    _add_clips(storage, 25)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all")
    m = scope.activate_matching("all", q)
    assert m.resolved_count == 25
    assert scope.mode == "matching"
    assert scope.matching is m


def test_selection_scope_invalidate_if_stale_clears_on_context_change(storage):
    _add_clips(storage, 5)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all")
    scope.activate_matching("all", q)

    # Unchanged context: nothing invalidated.
    assert scope.invalidate_if_stale("all", q) is False
    assert scope.mode == "matching"

    # Search text changed: matching selection must be dropped, not
    # silently reinterpreted against the new query.
    changed = SearchQuery(filter_name="all", text="something")
    assert scope.invalidate_if_stale("all", changed) is True
    assert scope.mode == "none"
    assert scope.matching is None


def test_selection_scope_invalidate_if_stale_on_navigation_change(storage):
    _add_clips(storage, 5)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="favorites")
    scope.activate_matching("favorites", q)
    assert scope.invalidate_if_stale("screenshots", SearchQuery(filter_name="screenshots")) is True
    assert scope.mode == "none"


def test_selection_scope_invalidate_if_stale_on_sort_change(storage):
    _add_clips(storage, 5)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all", sort=models.SORT_NEWEST_ADDED)
    scope.activate_matching("all", q)
    changed = SearchQuery(filter_name="all", sort=models.SORT_OLDEST_ADDED)
    assert scope.invalidate_if_stale("all", changed) is True


def test_selection_scope_clear_drops_matching_unconditionally(storage):
    _add_clips(storage, 5)
    scope = SelectionScope(storage)
    scope.activate_matching("all", SearchQuery(filter_name="all"))
    scope.clear()
    assert scope.mode == "none"
    assert scope.matching is None


def test_selection_scope_resolve_matching_refreshes_exact_count(storage):
    _add_clips(storage, 10)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all")
    scope.activate_matching("all", q)

    # More clips arrive after activation (e.g. new captures) -- resolve()
    # must report the CURRENT count, not the one cached at activation.
    _add_clips(storage, 5, prefix="late")
    resolution = scope.resolve("all", q)
    assert resolution.stale is False
    assert resolution.mode == "matching"
    assert resolution.count == 15


def test_selection_scope_resolve_matching_aborts_when_stale(storage):
    _add_clips(storage, 10)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all")
    scope.activate_matching("all", q)

    stale_resolution = scope.resolve("all", SearchQuery(filter_name="all", text="typed something"))
    assert stale_resolution.stale is True
    assert stale_resolution.count == 0
    # Resolving ids from a stale selection must abort loudly, not
    # silently return an empty (and misleading-looking) result.
    with pytest.raises(ValueError):
        list(stale_resolution.iter_ids())


def test_selection_resolution_iter_ids_raises_on_stale():
    stale = SelectionResolution(mode="matching", count=0, stale=True)
    with pytest.raises(ValueError):
        list(stale.iter_ids())


def test_selection_scope_resolve_matching_ids_are_id_only_and_deduplicated(storage):
    ids = _add_clips(storage, 137)
    scope = SelectionScope(storage)
    q = SearchQuery(filter_name="all")
    scope.activate_matching("all", q)

    resolution = scope.resolve("all", q, batch_size=50)
    assert resolution.count == 137

    resolved = resolution.resolve_all_ids()
    assert len(resolved) == 137
    assert set(resolved) == set(ids)
    assert len(resolved) == len(set(resolved))  # no duplicates


def test_selection_scope_resolve_visible_mode_dedupes_input_ids(storage):
    scope = SelectionScope(storage)
    resolution = scope.resolve("all", None, visible_ids=["a", "b", "a", "c", "b"])
    assert resolution.mode == "visible"
    assert resolution.count == 3
    assert resolution.resolve_all_ids() == ["a", "b", "c"]


def test_selection_scope_resolve_with_no_selection_is_none_mode(storage):
    scope = SelectionScope(storage)
    resolution = scope.resolve("all", None, visible_ids=[])
    assert resolution.mode == "none"
    assert resolution.count == 0
    assert resolution.resolve_all_ids() == []


def test_selection_scope_matching_does_not_materialize_ids_until_resolved(storage):
    """Activating a matching selection over a large set must never build
    an id list -- only a count. Confirmed both behaviorally (no ids
    attribute holds anything) and via source inspection that
    activate_matching never calls list_clip_ids/iter_clip_ids/list_clips."""
    import inspect

    from cache_vault.core import selection as selection_module

    _add_clips(storage, 5000)
    scope = SelectionScope(storage)
    m = scope.activate_matching("all", SearchQuery(filter_name="all"))
    assert m.resolved_count == 5000
    # MatchingSelection itself carries no id list at all -- just the
    # descriptor + a count.
    assert not hasattr(m, "ids") and not hasattr(m, "clip_ids")

    source = inspect.getsource(selection_module.SelectionScope.activate_matching)
    assert "list_clips(" not in source
    assert "list_clip_ids(" not in source
    assert "iter_clip_ids(" not in source
    assert "count_clips(" in source


# --- storage.clip_id_snapshot: read-transaction consistency ----------------
#
# These use a real on-disk VaultStorage (not the in-memory `storage`
# fixture): clip_id_snapshot opens a genuinely separate reader connection
# only for a real database file (see reader_connection's ":memory:" can't
# be reopened by a second connection" fallback) -- WAL snapshot isolation,
# the actual mechanism under test, only applies across two real
# connections. Simulates a writer mutating the table, through the same
# VaultStorage's normal write connection, *while* a snapshot's read
# transaction is still open on its own connection.


def _add_clips_disk(storage, n, prefix="clip"):
    ids = []
    for i in range(n):
        c = Clip(content=f"{prefix} {i}", preview=f"{prefix} {i}")
        storage.add_clip(c)
        ids.append(c.id)
    return ids


def test_clip_id_snapshot_count_matches_id_enumeration(tmp_path):
    storage = VaultStorage(tmp_path / "vault.db")
    try:
        _add_clips_disk(storage, 23)
        with storage.clip_id_snapshot(None, batch_size=5) as (count, batches):
            assert count == 23
            resolved = [cid for batch in batches for cid in batch]
        assert len(resolved) == 23
        assert len(set(resolved)) == 23  # no duplicates across batch boundaries
    finally:
        storage.close()


def test_clip_id_snapshot_unaffected_by_concurrent_insert_mid_enumeration(tmp_path):
    """A writer inserting new rows *after* the snapshot's read transaction
    has started, but before enumeration finishes, must not be visible to
    that snapshot -- the enumerated set must exactly match the count taken
    at snapshot-open time, not a partial/inflated view."""
    storage = VaultStorage(tmp_path / "vault.db")
    try:
        original_ids = _add_clips_disk(storage, 12)

        with storage.clip_id_snapshot(None, batch_size=5) as (count, batches):
            assert count == 12
            first_batch = next(batches)
            assert len(first_batch) == 5

            # Concurrent writer: 5 new clips arrive mid-enumeration, via
            # the same VaultStorage's own write connection (a real,
            # separate connection from the snapshot's dedicated reader).
            _add_clips_disk(storage, 5, prefix="late")
            assert storage.count_clips(None) == 17  # the writer's own view is current

            remaining = [cid for batch in batches for cid in batch]

        resolved = first_batch + remaining
        assert len(resolved) == 12  # not 17 -- the late inserts aren't in this snapshot
        assert set(resolved) == set(original_ids)
        assert len(set(resolved)) == len(resolved)

        # After the snapshot closes, a fresh read sees the committed insert.
        assert storage.count_clips(None) == 17
    finally:
        storage.close()


def test_clip_id_snapshot_unaffected_by_concurrent_delete_mid_enumeration(tmp_path):
    """A writer deleting not-yet-enumerated rows mid-snapshot must not
    cause enumeration to skip ahead or under-count -- the snapshot still
    resolves every id that existed when it opened."""
    storage = VaultStorage(tmp_path / "vault.db")
    try:
        original_ids = _add_clips_disk(storage, 12)

        with storage.clip_id_snapshot(None, batch_size=5) as (count, batches):
            assert count == 12
            first_batch = next(batches)

            # Concurrent writer: hard-delete 3 not-yet-read rows.
            to_delete = [cid for cid in original_ids if cid not in first_batch][:3]
            for cid in to_delete:
                storage.conn.execute("DELETE FROM clips WHERE id = ?", (cid,))
            storage.conn.commit()
            assert storage.count_clips(None) == 9  # the writer's own view is current

            remaining = [cid for batch in batches for cid in batch]

        resolved = first_batch + remaining
        assert len(resolved) == 12  # not 9 -- deletes aren't visible to this snapshot
        assert set(resolved) == set(original_ids)

        # After the snapshot closes, a fresh read reflects the deletion.
        assert storage.count_clips(None) == 9
    finally:
        storage.close()


def test_selection_resolution_iter_ids_matching_uses_snapshot_and_matches_count(tmp_path):
    """End-to-end through SelectionScope/SelectionResolution (not just the
    raw storage primitive): resolve_all_ids() for a matching selection
    returns exactly the snapshot count's worth of unique ids, even with a
    concurrent insert arriving mid-resolution."""
    storage = VaultStorage(tmp_path / "vault.db")
    try:
        _add_clips_disk(storage, 11)
        scope = SelectionScope(storage)
        q = SearchQuery(filter_name="all")
        scope.activate_matching("all", q)

        resolution = scope.resolve("all", q, batch_size=4)
        assert resolution.count == 11

        # A batch-size-4 resolution takes 3 batches (4+4+3) -- insert more
        # clips through the storage's own write connection between when
        # iter_ids() opens its snapshot and when it finishes; the
        # resolver must still return exactly 11 unique ids, matching the
        # snapshot it took, not whatever the table looks like by the time
        # enumeration finishes.
        ids = []
        for i, batch in enumerate(resolution.iter_ids()):
            ids.extend(batch)
            if i == 0:
                _add_clips_disk(storage, 4, prefix="late")
        assert len(ids) == 11
        assert len(set(ids)) == 11
    finally:
        storage.close()
