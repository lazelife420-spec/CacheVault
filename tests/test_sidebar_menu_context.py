"""Commit 3: pure-logic tests for the sidebar context-menu matrix and
invocation context. Headless, no Tk dependency.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cache_vault.core import storage as S
from cache_vault.core.menu_context import MenuCommand
from cache_vault.core.search import SearchQuery
from cache_vault.core.sidebar_menu_context import (
    CMD_EMPTY_COLLECTION,
    CMD_EXPORT_COLLECTION,
    CMD_EXPORT_CURRENT_VIEW,
    CMD_EXPORT_SELECTED,
    CMD_OPEN,
    CMD_PROPERTIES,
    CMD_REFRESH,
    CMD_REMOVE_FAVORITE_MARKS,
    CMD_RENAME_COLLECTION,
    CMD_RESTORE_ALL,
    CMD_RESTORE_SELECTED,
    CMD_SCAN_AGAIN,
    CMD_SCAN_CLEANUP_SUGGESTIONS,
    CMD_SCAN_IMAGE_DUPLICATES,
    CMD_SELECT_ALL_MATCHING,
    CMD_SELECT_ALL_VISIBLE,
    CMD_REVIEW_LARGEST_IMAGES,
    CMD_REVIEW_SUGGESTIONS,
    CMD_REVIEW_TINY_IMAGES,
    CMD_SHOW_IGNORED,
    SIDEBAR_ALL_CLIPS,
    SIDEBAR_CLEANUP_SUGGESTIONS,
    SIDEBAR_COLLECTION,
    SIDEBAR_FAVORITES,
    SIDEBAR_HOME,
    SIDEBAR_IMAGES,
    SIDEBAR_RECENTLY_REMOVED,
    SidebarInvocationContext,
    build_sidebar_invocation_context,
    build_sidebar_query,
    classify_sidebar_row,
    sidebar_command_matrix,
)


def _matching(nav_key: str, query: SearchQuery, resolved_count: int = 0):
    from cache_vault.core.selection import MatchingSelection, query_signature
    return MatchingSelection(
        nav_key=nav_key,
        query=query,
        signature=query_signature(nav_key, query),
        resolved_count=resolved_count,
        resolved_at="2024-01-01T00:00:00Z",
    )


def _ctx(
    target_key: str,
    active_key: str = S.FILTER_ALL,
    collection_name: str | None = None,
    visible_selected_ids: tuple[str, ...] = (),
    matching=None,
    item_count: int = 0,
) -> SidebarInvocationContext:
    return build_sidebar_invocation_context(
        target_key=target_key,
        active_key=active_key,
        collection_name=collection_name,
        visible_selected_ids=visible_selected_ids,
        matching=matching,
        item_count=item_count,
    )


def _keys(matrix: list[MenuCommand]) -> set[str]:
    return {c.key for c in matrix if c.enabled}


def _labels(matrix: list[MenuCommand]) -> dict[str, str]:
    return {c.key: c.label for c in matrix}


# --- classification and context ------------------------------------------------


def test_classify_home():
    assert classify_sidebar_row(S.FILTER_HOME) == SIDEBAR_HOME


def test_classify_all_clips():
    assert classify_sidebar_row(S.FILTER_ALL) == SIDEBAR_ALL_CLIPS


def test_classify_images():
    assert classify_sidebar_row(S.FILTER_SCREENSHOTS) == SIDEBAR_IMAGES


def test_classify_favorites():
    assert classify_sidebar_row(S.FILTER_FAVORITES) == SIDEBAR_FAVORITES
    assert classify_sidebar_row(S.FILTER_PINNED) == SIDEBAR_FAVORITES


def test_classify_recently_removed():
    assert classify_sidebar_row(S.FILTER_RECENTLY_REMOVED) == SIDEBAR_RECENTLY_REMOVED


def test_classify_collection():
    assert classify_sidebar_row(f"{S.COLLECTION_PREFIX}Work") == SIDEBAR_COLLECTION


def test_classify_cleanup_suggestions():
    assert classify_sidebar_row("nav_cleanup_suggestions") == SIDEBAR_CLEANUP_SUGGESTIONS


def test_classify_unknown_is_other():
    assert classify_sidebar_row("nav_unknown") == "other"


def test_build_sidebar_query_for_filter():
    q = build_sidebar_query(S.FILTER_ALL)
    assert q is not None
    assert q.filter_name == S.FILTER_ALL
    assert q.text == ""


def test_build_sidebar_query_for_collection():
    q = build_sidebar_query(f"{S.COLLECTION_PREFIX}Work", collection_name="Work")
    assert q is not None
    assert q.filter_name == f"{S.COLLECTION_PREFIX}Work"
    assert q.collection == "Work"


def test_build_sidebar_query_for_home_and_cleanup():
    assert build_sidebar_query(S.FILTER_HOME) is None
    assert build_sidebar_query("nav_cleanup_suggestions") is None


def test_context_knows_target_active():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_SCREENSHOTS)
    assert ctx.is_target_active is True
    assert ctx.row_type == SIDEBAR_IMAGES


def test_context_knows_target_inactive():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_ALL)
    assert ctx.is_target_active is False


def test_matching_descriptor_only_when_belongs_to_target():
    q = SearchQuery(filter_name=S.FILTER_SCREENSHOTS)
    m = _matching(S.FILTER_SCREENSHOTS, q, resolved_count=42)
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_SCREENSHOTS, matching=m, item_count=42)
    assert ctx.matching_descriptor is not None
    assert ctx.selection_count == 42


def test_matching_descriptor_excluded_when_from_different_row():
    q = SearchQuery(filter_name=S.FILTER_ALL)
    m = _matching(S.FILTER_ALL, q, resolved_count=42)
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_ALL, matching=m, item_count=0)
    assert ctx.matching_descriptor is None


def test_matching_descriptor_excluded_when_search_text_present():
    q = SearchQuery(filter_name=S.FILTER_SCREENSHOTS, text="hello")
    m = _matching(S.FILTER_SCREENSHOTS, q, resolved_count=42)
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_SCREENSHOTS, matching=m, item_count=42)
    assert ctx.matching_descriptor is None


def test_visible_selection_counts_without_matching():
    ctx = _ctx(S.FILTER_ALL, visible_selected_ids=("a", "b", "a"), item_count=10)
    assert ctx.selection_count == 3
    assert ctx.has_selection is True


# --- Home menu -----------------------------------------------------------------


def test_home_menu_has_open_refresh_scan():
    ctx = _ctx(S.FILTER_HOME, active_key=S.FILTER_HOME, item_count=0)
    matrix = sidebar_command_matrix(ctx)
    keys = _keys(matrix)
    assert CMD_OPEN in keys
    assert CMD_REFRESH in keys
    assert CMD_SCAN_CLEANUP_SUGGESTIONS in keys
    assert CMD_PROPERTIES not in keys


# --- All Clips / History menu --------------------------------------------------


def test_all_clips_menu_active_with_items():
    ctx = _ctx(S.FILTER_ALL, active_key=S.FILTER_ALL, item_count=24)
    matrix = sidebar_command_matrix(ctx)
    keys = _keys(matrix)
    assert CMD_OPEN in keys
    assert CMD_REFRESH in keys
    assert CMD_SELECT_ALL_VISIBLE in keys
    assert CMD_SELECT_ALL_MATCHING in keys
    assert CMD_SCAN_CLEANUP_SUGGESTIONS in keys
    assert CMD_PROPERTIES in keys


def test_all_clips_menu_inactive_hides_view_dependent_commands():
    ctx = _ctx(S.FILTER_ALL, active_key=S.FILTER_SCREENSHOTS, item_count=24)
    matrix = sidebar_command_matrix(ctx)
    keys = _keys(matrix)
    assert CMD_OPEN in keys
    assert CMD_REFRESH not in keys
    assert CMD_SELECT_ALL_VISIBLE not in keys
    assert CMD_SELECT_ALL_MATCHING not in keys
    assert CMD_EXPORT_CURRENT_VIEW not in keys


def test_all_clips_menu_never_exposes_empty_or_delete():
    ctx = _ctx(S.FILTER_ALL, active_key=S.FILTER_ALL, item_count=10)
    labels = " ".join(_labels(sidebar_command_matrix(ctx)).values()).lower()
    assert "empty" not in labels
    assert "permanently delete" not in labels
    assert "delete" not in labels


def test_all_clips_export_label_shows_matching_count():
    ctx = _ctx(S.FILTER_ALL, active_key=S.FILTER_ALL, item_count=140)
    labels = _labels(sidebar_command_matrix(ctx))
    assert "140" in labels[CMD_EXPORT_CURRENT_VIEW]
    assert "matching clips" in labels[CMD_EXPORT_CURRENT_VIEW].lower()


# --- Images / Screenshots menu -------------------------------------------------


def test_images_menu_active_with_images():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_SCREENSHOTS, item_count=7)
    matrix = sidebar_command_matrix(ctx)
    keys = _keys(matrix)
    assert CMD_OPEN in keys
    assert CMD_REFRESH in keys
    assert CMD_SELECT_ALL_VISIBLE in keys
    assert CMD_SELECT_ALL_MATCHING in keys
    assert CMD_SCAN_IMAGE_DUPLICATES in keys


def test_images_menu_never_exposes_permanent_delete():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_SCREENSHOTS, item_count=5)
    labels = " ".join(_labels(sidebar_command_matrix(ctx)).values()).lower()
    assert "permanently delete" not in labels
    assert "empty" not in labels


def test_images_menu_inactive_blocks_view_commands():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_ALL, item_count=5)
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_OPEN in keys
    assert CMD_SCAN_IMAGE_DUPLICATES not in keys
    assert CMD_REVIEW_TINY_IMAGES not in keys
    assert CMD_REVIEW_LARGEST_IMAGES not in keys


# --- Favorites menu ------------------------------------------------------------


def test_favorites_menu_remove_favorite_marks_label_includes_count():
    ctx = _ctx(
        S.FILTER_FAVORITES,
        active_key=S.FILTER_FAVORITES,
        item_count=24,
        visible_selected_ids=("a", "b"),
    )
    labels = _labels(sidebar_command_matrix(ctx))
    assert "24" in labels[CMD_REMOVE_FAVORITE_MARKS] or "2" in labels[CMD_REMOVE_FAVORITE_MARKS]
    assert "Remove favorite marks" in labels[CMD_REMOVE_FAVORITE_MARKS]
    assert "Empty Favorites" not in labels.values()


def test_favorites_menu_no_empty_label():
    ctx = _ctx(S.FILTER_FAVORITES, active_key=S.FILTER_FAVORITES, item_count=5)
    labels = " ".join(_labels(sidebar_command_matrix(ctx)).values()).lower()
    assert "empty favorites" not in labels


def test_favorites_menu_inactive_blocks_selection_and_export():
    ctx = _ctx(S.FILTER_FAVORITES, active_key=S.FILTER_ALL, item_count=5)
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_OPEN in keys
    assert CMD_SELECT_ALL_VISIBLE not in keys
    assert CMD_EXPORT_SELECTED not in keys
    assert CMD_REMOVE_FAVORITE_MARKS not in keys


# --- Individual collection menu --------------------------------------------------


def test_collection_menu_has_only_allowed_commands():
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}Work",
        active_key=f"{S.COLLECTION_PREFIX}Work",
        collection_name="Work",
        item_count=8,
    )
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_OPEN in keys
    assert CMD_RENAME_COLLECTION in keys
    assert CMD_SELECT_ALL_VISIBLE in keys
    assert CMD_SELECT_ALL_MATCHING in keys
    assert CMD_EXPORT_COLLECTION in keys
    assert CMD_PROPERTIES in keys


def test_collection_menu_has_empty_and_forbids_delete():
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}Work",
        active_key=f"{S.COLLECTION_PREFIX}Work",
        collection_name="Work",
        item_count=8,
    )
    keys = _keys(sidebar_command_matrix(ctx))
    labels = " ".join(_labels(sidebar_command_matrix(ctx)).values()).lower()
    assert CMD_EMPTY_COLLECTION in keys
    assert "empty collection" in labels
    assert "delete collection" not in labels


def test_collection_menu_inactive_cannot_target_other_collection():
    # Right-clicking Work while Work2 is active.
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}Work",
        active_key=f"{S.COLLECTION_PREFIX}Work2",
        collection_name="Work",
        item_count=8,
    )
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_SELECT_ALL_VISIBLE not in keys
    assert CMD_EXPORT_COLLECTION not in keys


# --- Recently Removed menu -----------------------------------------------------


def test_recently_removed_menu_exposes_restore_not_delete():
    ctx = _ctx(
        S.FILTER_RECENTLY_REMOVED,
        active_key=S.FILTER_RECENTLY_REMOVED,
        item_count=18,
        visible_selected_ids=("c1", "c2"),
    )
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_RESTORE_SELECTED in keys
    assert CMD_RESTORE_ALL in keys
    labels = _labels(sidebar_command_matrix(ctx))
    assert "Restore 2 selected items" == labels[CMD_RESTORE_SELECTED]
    assert "Restore all 18 items" == labels[CMD_RESTORE_ALL]


def test_recently_removed_menu_no_permanent_delete():
    ctx = _ctx(S.FILTER_RECENTLY_REMOVED, active_key=S.FILTER_RECENTLY_REMOVED, item_count=5)
    labels = " ".join(_labels(sidebar_command_matrix(ctx)).values()).lower()
    assert "permanently delete" not in labels
    assert "empty recently removed" not in labels


# --- Cleanup Suggestions menu --------------------------------------------------


def test_cleanup_suggestions_menu_reuses_callbacks():
    ctx = _ctx("nav_cleanup_suggestions", active_key="nav_cleanup_suggestions", item_count=0)
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_OPEN in keys
    assert CMD_SCAN_AGAIN in keys
    assert CMD_REVIEW_SUGGESTIONS in keys
    assert CMD_SHOW_IGNORED in keys
    assert CMD_PROPERTIES in keys


def test_cleanup_suggestions_menu_no_forbidden_decision_commands():
    ctx = _ctx("nav_cleanup_suggestions", active_key="nav_cleanup_suggestions", item_count=0)
    keys = _keys(sidebar_command_matrix(ctx))
    assert "keep" not in keys
    assert "keep_forever" not in keys
    assert "ignore" not in keys


# --- counts use unique / stable ids --------------------------------------------


def test_counts_reflect_item_count_not_duplicate_visible_ids():
    ctx = _ctx(
        S.FILTER_FAVORITES,
        active_key=S.FILTER_FAVORITES,
        item_count=24,
        visible_selected_ids=("a", "a", "b"),
    )
    assert ctx.selection_count == 3


def test_sidebar_command_matrix_contains_menu_command_instances():
    ctx = _ctx(S.FILTER_ALL, active_key=S.FILTER_ALL, item_count=10)
    matrix = sidebar_command_matrix(ctx)
    assert all(isinstance(c, MenuCommand) for c in matrix)

# --- Matching-selection ownership ----------------------------------------------


def test_matching_all_clips_selection_does_not_belong_to_images():
    q_all = SearchQuery(filter_name=S.FILTER_ALL)
    m_all = _matching(S.FILTER_ALL, q_all, resolved_count=10)
    ctx = _ctx(
        S.FILTER_SCREENSHOTS,
        active_key=S.FILTER_SCREENSHOTS,
        matching=m_all,
        item_count=0,
    )
    assert ctx.matching_descriptor is None


def test_matching_images_selection_does_not_belong_to_all_clips():
    q_img = SearchQuery(filter_name=S.FILTER_SCREENSHOTS)
    m_img = _matching(S.FILTER_SCREENSHOTS, q_img, resolved_count=7)
    ctx = _ctx(
        S.FILTER_ALL,
        active_key=S.FILTER_ALL,
        matching=m_img,
        item_count=20,
    )
    assert ctx.matching_descriptor is None


def test_matching_collection_a_does_not_belong_to_collection_b():
    q_a = SearchQuery(
        filter_name=f"{S.COLLECTION_PREFIX}A", collection="A",
    )
    m_a = _matching(f"{S.COLLECTION_PREFIX}A", q_a, resolved_count=5)
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}B",
        active_key=f"{S.COLLECTION_PREFIX}B",
        collection_name="B",
        matching=m_a,
        item_count=5,
    )
    assert ctx.matching_descriptor is None


def test_matching_active_vault_does_not_belong_to_recently_removed():
    q_all = SearchQuery(filter_name=S.FILTER_ALL)
    m_all = _matching(S.FILTER_ALL, q_all, resolved_count=10)
    ctx = _ctx(
        S.FILTER_RECENTLY_REMOVED,
        active_key=S.FILTER_RECENTLY_REMOVED,
        matching=m_all,
        item_count=0,
    )
    assert ctx.matching_descriptor is None


def test_matching_recently_removed_does_not_belong_to_favorites():
    q_rr = SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)
    m_rr = _matching(S.FILTER_RECENTLY_REMOVED, q_rr, resolved_count=3)
    ctx = _ctx(
        S.FILTER_FAVORITES,
        active_key=S.FILTER_FAVORITES,
        matching=m_rr,
        item_count=0,
    )
    assert ctx.matching_descriptor is None


def test_search_text_in_matching_excludes_it_from_sidebar_target():
    q = SearchQuery(filter_name=S.FILTER_ALL, text="hello")
    m = _matching(S.FILTER_ALL, q, resolved_count=4)
    ctx = _ctx(
        S.FILTER_ALL,
        active_key=S.FILTER_ALL,
        matching=m,
        item_count=4,
    )
    assert ctx.matching_descriptor is None


def test_owning_matching_descriptor_is_retained_for_active_target():
    q_fav = SearchQuery(filter_name=S.FILTER_FAVORITES)
    m_fav = _matching(S.FILTER_FAVORITES, q_fav, resolved_count=5)
    ctx = _ctx(
        S.FILTER_FAVORITES,
        active_key=S.FILTER_FAVORITES,
        matching=m_fav,
        item_count=5,
    )
    assert ctx.matching_descriptor is not None
    assert ctx.selection_count == 5


def test_visible_only_commands_absent_for_inactive_rows():
    ctx = _ctx(S.FILTER_SCREENSHOTS, active_key=S.FILTER_ALL, item_count=10)
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_SELECT_ALL_VISIBLE not in keys
    assert CMD_SELECT_ALL_MATCHING not in keys
    assert CMD_EXPORT_CURRENT_VIEW not in keys


# --- Menu-opening purity (logical layer) ---------------------------------------


def test_command_matrix_construction_does_not_mutate_state():
    # The pure matrix should produce the same output twice and never modify
    # the provided context.
    ctx = _ctx(
        S.FILTER_FAVORITES,
        active_key=S.FILTER_FAVORITES,
        item_count=12,
        visible_selected_ids=("a", "b"),
    )
    m1 = sidebar_command_matrix(ctx)
    m2 = sidebar_command_matrix(ctx)
    assert m1 == m2
    assert ctx.item_count == 12
    assert ctx.visible_selected_ids == ("a", "b")


def test_empty_collection_command_appears_for_collection_rows():
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}Work",
        active_key=S.FILTER_ALL,
        collection_name="Work",
        item_count=5,
    )
    keys = _keys(sidebar_command_matrix(ctx))
    assert CMD_EMPTY_COLLECTION in keys


def test_empty_collection_command_is_absent_for_non_collection_rows():
    for key in (S.FILTER_ALL, S.FILTER_FAVORITES, S.FILTER_SCREENSHOTS, S.FILTER_HOME):
        ctx = _ctx(key, active_key=key, item_count=3)
        keys = _keys(sidebar_command_matrix(ctx))
        assert CMD_EMPTY_COLLECTION not in keys


def test_no_delete_collection_command_in_matrix():
    ctx = _ctx(
        f"{S.COLLECTION_PREFIX}Work",
        active_key=S.FILTER_ALL,
        collection_name="Work",
        item_count=5,
    )
    labels = " ".join(c.label.lower() for c in sidebar_command_matrix(ctx))
    assert "delete collection" not in labels

