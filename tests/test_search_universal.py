"""
Stream 4 — Cross-view search tests.

Verifies that when search text is present, the query uses FILTER_SEARCH_ALL
which spans both live clips AND Recently Removed (deleted_at IS NOT NULL AND expires_at IS NULL).
"""

from __future__ import annotations

import pytest

from cache_vault.core import storage as S, search


def test_build_query_with_text_uses_search_all(vault):
    """When search text is present, filter_name must be FILTER_SEARCH_ALL."""
    raw = "important note"
    q = search.parse(raw, S.FILTER_SEARCH_ALL)
    # The query's filter_name must be FILTER_SEARCH_ALL
    assert q.filter_name == S.FILTER_SEARCH_ALL
    assert q.text == raw


def test_build_query_without_text_uses_active_filter(vault):
    """When search box is empty, filter_name respects the active sidebar filter."""
    q = search.parse("", S.FILTER_ALL)
    assert q.filter_name == S.FILTER_ALL
    assert q.text == ""


def test_search_finds_live_clip(vault):
    """Free text search must find live clips."""
    clip = vault.capture("find-me-live-text", source_app="TestApp")
    clips = vault.list_clips(search.parse("find-me-live-text", S.FILTER_SEARCH_ALL))
    ids = [c.id for c in clips]
    assert clip.id in ids


def test_search_finds_clip_in_recently_removed(vault):
    """Free text search must find clips that have been moved to Recently Removed."""
    clip = vault.capture("ghost-in-recently-removed", source_app="TestApp")
    vault.remove_from_history(clip.id)

    # Verify it is deleted (Recently Removed, not Expired)
    db_clip = vault.storage.get_clip(clip.id)
    assert db_clip is not None
    assert db_clip.deleted_at is not None
    assert db_clip.expires_at is None  # soft-deleted, not auto-expired

    clips = vault.list_clips(search.parse("ghost-in-recently-removed", S.FILTER_SEARCH_ALL))
    ids = [c.id for c in clips]
    assert clip.id in ids, (
        "Cross-view search must find clips in Recently Removed when search text is active"
    )


def test_search_finds_live_and_deleted_combined(vault):
    """Cross-view search must return both live and Recently Removed clips in one result set."""
    live_clip = vault.capture("combined-search-live-xyz", source_app="Alpha")
    removed_clip = vault.capture("combined-search-removed-xyz", source_app="Beta")
    vault.remove_from_history(removed_clip.id)

    clips = vault.list_clips(search.parse("combined-search", S.FILTER_SEARCH_ALL))
    ids = [c.id for c in clips]
    assert live_clip.id in ids
    assert removed_clip.id in ids


def test_search_without_text_does_not_include_recently_removed(vault):
    """When search is empty, the active filter must NOT include Recently Removed clips
    unless the user has explicitly navigated to the Recently Removed filter."""
    clip = vault.capture("should-not-show-in-all-filter", source_app="TestApp")
    vault.remove_from_history(clip.id)

    # Empty search on FILTER_ALL — recently removed must not appear
    clips = vault.list_clips(search.parse("", S.FILTER_ALL))
    ids = [c.id for c in clips]
    assert clip.id not in ids, (
        "Empty search on FILTER_ALL must not include Recently Removed clips"
    )


def test_search_does_not_find_expired_sensitive_clips(vault):
    """Cross-view search must NOT surface Expired sensitive clip stubs."""
    from cache_vault.core.models import now_iso
    clip = vault.capture("SECRET-expired-content-xyz", source_app="TestApp")

    # Simulate expiry: set expires_at and deleted_at (like scrubbed sensitive clip)
    ts = now_iso()
    vault.storage.conn.execute(
        "UPDATE clips SET deleted_at=?, expires_at=?, content='[Expired]' WHERE id=?",
        (ts, ts, clip.id),
    )
    vault.storage.conn.commit()

    clips = vault.list_clips(search.parse("SECRET-expired-content-xyz", S.FILTER_SEARCH_ALL))
    ids = [c.id for c in clips]
    assert clip.id not in ids, (
        "Cross-view search must not surface Expired sensitive clip stubs"
    )


def test_search_all_filter_name_is_importable():
    """FILTER_SEARCH_ALL must be accessible from the storage module."""
    assert hasattr(S, "FILTER_SEARCH_ALL")
    assert isinstance(S.FILTER_SEARCH_ALL, str)
    assert S.FILTER_SEARCH_ALL  # non-empty
