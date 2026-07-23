"""Commit 2: pure-logic tests for core/menu_context.py -- view
classification and the selection-wide command matrix. Headless, no Tk
dependency (mirrors core/contextmenu.py's own test split). Tk-level
right-click/menu-routing behavior is covered in
tests/test_clip_context_menu.py.
"""

from __future__ import annotations

from cache_vault.core import storage as S
from cache_vault.core.menu_context import (
    MenuInvocationContext,
    VIEW_ACTIVE,
    VIEW_COLLECTION,
    VIEW_FAVORITES,
    VIEW_IMAGES,
    VIEW_OTHER,
    VIEW_RECENTLY_REMOVED,
    VIEW_SEARCH,
    classify_view_kind,
    command_matrix,
)
from cache_vault.core.search import SearchQuery

_MATCHING_WIDE = frozenset({
    "export_selected", "favorite_selected", "unfavorite_selected",
    "remove_favorite_marks", "move_to_recently_removed", "restore",
})


def _ctx(**kwargs) -> MenuInvocationContext:
    defaults = dict(
        clicked_clip_id="c1",
        nav_key=S.FILTER_ALL,
        view_kind=VIEW_ACTIVE,
        was_selected_before_click=False,
        selection_mode="none",
        visible_selected_ids=(),
        matching_signature=None,
        matching_count=None,
    )
    defaults.update(kwargs)
    return MenuInvocationContext(**defaults)


# --- classify_view_kind ------------------------------------------------


def test_classify_active_clips():
    assert classify_view_kind(S.FILTER_ALL, SearchQuery(filter_name=S.FILTER_ALL)) == VIEW_ACTIVE


def test_classify_recently_removed():
    q = SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)
    assert classify_view_kind(S.FILTER_RECENTLY_REMOVED, q) == VIEW_RECENTLY_REMOVED


def test_classify_favorites():
    q = SearchQuery(filter_name=S.FILTER_FAVORITES)
    assert classify_view_kind(S.FILTER_FAVORITES, q) == VIEW_FAVORITES


def test_classify_images():
    q = SearchQuery(filter_name=S.FILTER_SCREENSHOTS)
    assert classify_view_kind(S.FILTER_SCREENSHOTS, q) == VIEW_IMAGES


def test_classify_collection():
    q = SearchQuery(filter_name=f"{S.COLLECTION_PREFIX}Work")
    assert classify_view_kind(f"{S.COLLECTION_PREFIX}Work", q) == VIEW_COLLECTION


def test_classify_search_takes_priority_over_underlying_filter():
    """A search typed while on e.g. Favorites still counts as the search
    matrix, not the favorites matrix -- search text on the query wins."""
    q = SearchQuery(filter_name=S.FILTER_SEARCH_ALL, text="hello")
    assert classify_view_kind(S.FILTER_FAVORITES, q) == VIEW_SEARCH


def test_classify_none_query_falls_back_to_nav_key():
    assert classify_view_kind(S.FILTER_RECENTLY_REMOVED, None) == VIEW_RECENTLY_REMOVED


def test_classify_other_filters_behave_like_active():
    q = SearchQuery(filter_name=S.FILTER_LINKS)
    assert classify_view_kind(S.FILTER_LINKS, q) == VIEW_ACTIVE


# --- MenuInvocationContext properties -----------------------------------


def test_context_is_matching_property():
    ctx = _ctx(selection_mode="matching", matching_count=50)
    assert ctx.is_matching is True
    assert ctx.selection_count == 50


def test_context_is_bulk_visible_property():
    ctx = _ctx(selection_mode="visible", visible_selected_ids=("a", "b", "c"))
    assert ctx.is_bulk_visible is True
    assert ctx.selection_count == 3


def test_context_single_visible_is_not_bulk():
    ctx = _ctx(selection_mode="visible", visible_selected_ids=("a",))
    assert ctx.is_bulk_visible is False
    assert ctx.selection_count == 1


# --- command_matrix: universal commands always present -------------------


def test_universal_selection_commands_always_present():
    ctx = _ctx()
    keys = {c.key for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert {"select_all_visible", "select_all_matching", "deselect_all", "invert_visible"} <= keys


def test_deselect_all_disabled_when_nothing_selected():
    ctx = _ctx(selection_mode="none")
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["deselect_all"].enabled is False


def test_deselect_all_enabled_with_a_selection():
    ctx = _ctx(selection_mode="visible", visible_selected_ids=("a",))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["deselect_all"].enabled is True


# --- command_matrix: no permanent delete anywhere -------------------------


def test_no_permanent_delete_command_in_any_view_kind():
    for view_kind in (VIEW_ACTIVE, VIEW_RECENTLY_REMOVED, VIEW_SEARCH, VIEW_COLLECTION, VIEW_FAVORITES, VIEW_IMAGES, VIEW_OTHER):
        ctx = _ctx(view_kind=view_kind, selection_mode="visible", visible_selected_ids=("a",))
        keys = {c.key for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
        assert "permanently_remove" not in keys
        assert "permanently_delete_selected" not in keys
        assert "permanently_delete_all" not in keys


# --- command_matrix: Recently Removed shows Restore, no delete/collection/favorite --


def test_recently_removed_matrix_shows_restore_only():
    ctx = _ctx(view_kind=VIEW_RECENTLY_REMOVED, selection_mode="visible", visible_selected_ids=("a", "b"))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert "restore" in commands
    assert commands["restore"].enabled is True
    assert commands["restore"].label == "Restore 2 item(s)"
    # No move-to-recently-removed, favorite, collection, or copy/export
    # commands leak into the Recently Removed matrix in this commit.
    assert "move_to_recently_removed" not in commands
    assert "favorite_selected" not in commands
    assert "add_to_collection" not in commands


def test_recently_removed_matching_wide_restore_enabled():
    ctx = _ctx(view_kind=VIEW_RECENTLY_REMOVED, selection_mode="matching", matching_count=40)
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["restore"].enabled is True
    assert commands["restore"].label == "Restore 40 item(s)"


# --- command_matrix: Favorites view removes marks, never deletes clips ---


def test_favorites_matrix_shows_remove_marks_not_delete():
    ctx = _ctx(view_kind=VIEW_FAVORITES, selection_mode="visible", visible_selected_ids=("a",))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert "remove_favorite_marks" in commands
    assert commands["remove_favorite_marks"].enabled is True
    assert "favorite_selected" not in commands  # favorites view doesn't need "favorite" again
    assert "unfavorite_selected" not in commands


# --- command_matrix: Collection view removal is membership-only, visible-only --


def test_collection_matrix_remove_from_collection_present():
    ctx = _ctx(view_kind=VIEW_COLLECTION, selection_mode="visible", visible_selected_ids=("a", "b", "c"))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["remove_from_collection"].enabled is True
    assert commands["remove_from_collection"].label == "Remove 3 from This Collection"
    assert "add_to_collection" not in commands  # already in a collection view


def test_collection_removal_disabled_in_matching_mode():
    """remove_from_collection has matching_capable=False -- collections
    stay a single-assignment-label operation, visible-selection only, per
    the architectural correction (no join-table / container semantics
    invented here)."""
    ctx = _ctx(view_kind=VIEW_COLLECTION, selection_mode="matching", matching_count=25)
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["remove_from_collection"].enabled is False
    assert "matching" in commands["remove_from_collection"].reason.lower() or "visible" in commands["remove_from_collection"].reason.lower()


def test_add_to_collection_disabled_in_matching_mode():
    ctx = _ctx(view_kind=VIEW_ACTIVE, selection_mode="matching", matching_count=25)
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["add_to_collection"].enabled is False


# --- command_matrix: matching-wide support boundary -----------------------


def test_matching_wide_supported_commands_enabled_in_matching_mode():
    ctx = _ctx(view_kind=VIEW_ACTIVE, selection_mode="matching", matching_count=300)
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    for key in ("export_selected", "favorite_selected", "unfavorite_selected", "move_to_recently_removed"):
        assert commands[key].enabled is True, f"{key} should be matching-wide enabled"


def test_matching_wide_unsupported_command_is_disabled_with_reason():
    ctx = _ctx(view_kind=VIEW_ACTIVE, selection_mode="matching", matching_count=300)
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=frozenset())}
    assert commands["export_selected"].enabled is False
    assert "matching" in commands["export_selected"].reason.lower()
    assert "visible" in commands["export_selected"].reason.lower()


def test_visible_mode_commands_all_enabled_regardless_of_matching_support():
    """matching_wide_supported only constrains matching MODE -- visible
    selection is unaffected by which commands are matching-capable."""
    ctx = _ctx(view_kind=VIEW_ACTIVE, selection_mode="visible", visible_selected_ids=("a", "b"))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=frozenset())}
    assert commands["export_selected"].enabled is True
    assert commands["copy_selected"].enabled is True


# --- command_matrix: labels are dynamic and reflect unique counts --------


def test_dynamic_labels_use_selection_count():
    ctx = _ctx(view_kind=VIEW_ACTIVE, selection_mode="visible", visible_selected_ids=("a", "b", "c"))
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["copy_selected"].label == "Copy 3 Selected"
    assert commands["export_selected"].label == "Export 3 Selected"
    assert commands["move_to_recently_removed"].label == "Move 3 to Recently Removed"


def test_dynamic_labels_use_matching_count_not_visible_count():
    """The label must reflect the true matching count, not
    len(visible_selected_ids) -- this is the exact "menu never looks
    like it targets all matching records while acting on only the
    visible 120" invariant, expressed at the label layer."""
    ctx = _ctx(
        view_kind=VIEW_ACTIVE, selection_mode="matching",
        visible_selected_ids=tuple(f"c{i}" for i in range(120)),  # capped visible subset
        matching_count=4213,  # true matching total, far beyond the visible cap
    )
    commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE)}
    assert commands["export_selected"].label == "Export 4213 Selected"
    assert "120" not in commands["export_selected"].label
    assert commands["move_to_recently_removed"].label == "Move 4213 to Recently Removed"
