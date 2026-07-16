"""Repository tests for VaultStorage.list_clips/count_clips paging.

Before this, the shell fetched every matching clip and sliced the first
MAX_VISIBLE_CLIPS in Python -- with ~1,700 clips that meant materializing
every row into a Clip object on every refresh just to keep 120 of them.
``list_clips(limit=..., offset=...)`` now applies the page in SQL, and
``count_clips`` is the paired total-count query using the exact same
WHERE clause (via the shared ``_build_where`` helper) so paging and
filtering can't drift apart.
"""

from __future__ import annotations

import sqlite3

from cache_vault.core import search
from cache_vault.core.settings import Settings
from cache_vault.core.storage import FILTER_FAVORITES, VaultStorage
from cache_vault.core.vault import Vault


def _seed_via_vault(n: int = 30, favorites: int = 0):
    v = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    ids = []
    for i in range(n):
        clip = v.capture(f"clip-{i:03d}", force=True)
        ids.append(clip.id)
    for cid in ids[:favorites]:
        v.set_pinned(cid, True)
    return v


def test_list_clips_limit_returns_only_the_requested_page():
    v = _seed_via_vault(30)
    page = v.storage.list_clips(limit=10)
    assert len(page) == 10


def test_list_clips_offset_advances_through_pages_without_gaps_or_dupes():
    v = _seed_via_vault(25)
    seen_ids = set()
    offset = 0
    page_size = 7
    while True:
        page = v.storage.list_clips(limit=page_size, offset=offset)
        if not page:
            break
        ids = [c.id for c in page]
        assert not (seen_ids & set(ids)), "pages must not overlap"
        seen_ids.update(ids)
        offset += page_size
    assert len(seen_ids) == 25


def test_list_clips_limit_none_preserves_original_fetch_everything_behavior():
    v = _seed_via_vault(15)
    everything = v.storage.list_clips()
    assert len(everything) == 15


def test_count_clips_matches_len_of_unlimited_list_clips_for_favorites_filter():
    v = _seed_via_vault(12, favorites=3)
    query = search.SearchQuery(filter_name=FILTER_FAVORITES)
    assert v.storage.count_clips(query) == len(v.storage.list_clips(query)) == 3


def test_count_clips_ignores_limit_and_counts_the_full_match_set():
    v = _seed_via_vault(20)
    total = v.storage.count_clips()
    paged = v.storage.list_clips(limit=5)
    assert total == 20
    assert len(paged) == 5


def test_list_clips_and_count_clips_agree_across_a_text_search_filter():
    v = _seed_via_vault(18)
    query = search.SearchQuery(text="clip-01")
    matched = v.storage.list_clips(query)
    assert v.storage.count_clips(query) == len(matched)
    # clip-010..clip-017 match the "clip-01" substring.
    assert len(matched) == 8


def test_paged_results_are_a_prefix_of_the_unlimited_ordering():
    """limit=N must return the same first N rows as the unlimited query in
    the same order, not just any N matching rows."""
    v = _seed_via_vault(20)
    everything = v.storage.list_clips()
    page = v.storage.list_clips(limit=5)
    assert [c.id for c in page] == [c.id for c in everything[:5]]


def test_reader_connection_sees_committed_writes(tmp_path):
    """A background-thread reader connection against a real file-backed DB
    must see data written and committed through the main connection."""
    storage = VaultStorage(tmp_path / "vault.db")
    vault = Vault(storage=storage, settings=Settings())
    vault.capture("hello from main connection", force=True)

    with storage.reader_connection() as reader:
        assert reader is not storage.conn
        rows = storage.list_clips(conn=reader)
        assert len(rows) == 1
        assert rows[0].content == "hello from main connection"

    storage.close()


def test_reader_connection_is_read_only(tmp_path):
    storage = VaultStorage(tmp_path / "vault.db")
    raised = False
    with storage.reader_connection() as reader:
        try:
            reader.execute(
                "INSERT INTO clips (id, created_at, updated_at) VALUES ('x','y','z')"
            )
        except sqlite3.OperationalError:
            raised = True
    assert raised, "a reader_connection() must not be able to write"
    storage.close()


def test_reader_connection_falls_back_to_shared_conn_for_memory_db():
    storage = VaultStorage(":memory:")
    with storage.reader_connection() as reader:
        assert reader is storage.conn
    storage.close()
