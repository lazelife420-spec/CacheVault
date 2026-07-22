"""Commit 3: focused integration tests for context-aware sidebar menus.

These tests cover the full pipeline from a sidebar row right-click through
menu construction to command dispatch, including inactive-row safety,
collection/favorites/recently-removed behavior, and stale-menu aborts.
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace
from unittest import mock

import pytest

from cache_vault.core import storage as S
from cache_vault.core.search import SearchQuery
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui import sidebar_context
from cache_vault.ui.filters import FilterNav, NAV_QUICK_PASTE
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import _tcl_unavailable, probe_tk_ui, wait_for_refresh

OK, REASON = probe_tk_ui()


def _isolated_settings() -> Settings:
    return Settings(capture_paused=True)


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n, prefix="clip"):
    vault = Vault(
        storage=VaultStorage(tmp_path / "vault.db"),
        settings=_isolated_settings(),
    )
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app):
    app._do_refresh_sync()
    wait_for_refresh(app)


# --- Right-click routing / inactive-row safety ---------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_filter_nav_right_click_targets_row_without_navigating(tk_root):
    """A right-click on a sidebar row must invoke the context handler with
    the clicked key but must not call the select/navigate handler."""
    settings = Settings()
    selected = []
    context_keys = []

    def on_select(key):
        selected.append(key)

    def on_context(key, x, y):
        context_keys.append(key)

    filters = FilterNav(
        tk_root,
        on_select=on_select,
        settings=settings,
        on_nav_context=on_context,
    )
    filters.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Right-click on the Quick Paste row (a dialog-only nav).
    row = filters._rows[NAV_QUICK_PASTE]
    row._on_right_click(SimpleNamespace(x_root=100, y_root=100))

    assert selected == []
    assert context_keys == [NAV_QUICK_PASTE]


@pytest.mark.skipif(not OK, reason=REASON)
def test_building_context_for_inactive_row_does_not_mutate_state(tmp_path):
    """Opening a context menu on an inactive row must not navigate,
    change selection, or mutate records."""
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        before_active = app._filters.active
        before_selected = list(app._selected_clip_ids)
        before_count = vault.count_clips(None)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_SCREENSHOTS,
        )

        assert ctx.is_target_active is False
        assert app._filters.active == before_active
        assert app._selected_clip_ids == before_selected
        assert vault.count_clips(None) == before_count
    finally:
        app.destroy()


# --- Open / navigation ----------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_open_command_navigates_to_inactive_target(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_SCREENSHOTS,
        )
        app._dispatch_sidebar_command("open", ctx)
        _settle(app)

        assert app._filters.active == S.FILTER_SCREENSHOTS
    finally:
        app.destroy()


# --- Active-row selection commands ---------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_select_all_visible_selects_current_view_only(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_ALL,
        )
        app._dispatch_sidebar_command("select_all_visible", ctx)

        assert set(app._selected_clip_ids) == set(app._visible_clip_ids)
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_inactive_row_select_all_visible_aborts(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        before_selected = list(app._selected_clip_ids)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_SCREENSHOTS,
        )
        app._dispatch_sidebar_command("select_all_visible", ctx)

        assert app._selected_clip_ids == before_selected
    finally:
        app.destroy()


# --- Favorites menu ------------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_remove_favorite_marks_clears_marks_and_preserves_clips(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)
    vault.set_favorite(clips[1].id, True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_FAVORITES)
        _settle(app)
        app._list.select_all()

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_FAVORITES,
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("remove_favorite_marks", ctx)

        reloaded = vault.storage.list_clips(None)
        assert len(reloaded) == 5
        assert all(not c.is_pinned for c in reloaded)
        # Collections and other fields untouched.
        assert all(c.collection is None or c.collection == "" for c in reloaded)
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_inactive_favorites_row_cannot_remove_marks(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_FAVORITES,
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("remove_favorite_marks", ctx)

        assert vault.storage.get_clip(clips[0].id).is_pinned is True
    finally:
        app.destroy()


# --- Collection menu -----------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_a_rename_does_not_touch_collection_b(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.simpledialog.askstring", return_value="Work2"):
            app._dispatch_sidebar_command("rename_collection", ctx)
        _settle(app)

        work2_ids = {
            c.id for c in vault.storage.list_clips(
                S.COLLECTION_PREFIX + "Work2",
            )
        }
        personal_ids = {
            c.id for c in vault.storage.list_clips(
                S.COLLECTION_PREFIX + "Personal",
            )
        }
        assert work2_ids == {clips[0].id, clips[1].id}
        assert personal_ids == {clips[2].id, clips[3].id}
        assert vault.storage.get_clip(clips[0].id).collection == "Work2"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_a_commands_target_collection_a_not_active_collection_b(tmp_path):
    """Right-clicking a collection row while a different collection is active
    must not accidentally operate on the active collection's items.
    """
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    vault.storage.set_collection(clips[0].id, "Work")
    vault.storage.set_collection(clips[1].id, "Work")
    vault.storage.set_collection(clips[2].id, "Personal")
    vault.storage.set_collection(clips[3].id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        # Build context for Work while Personal is active.
        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # View commands should abort because Work is not active.
        with mock.patch("tkinter.messagebox.showwarning"):
            app._dispatch_sidebar_command("select_all_visible", ctx)

        assert app._filters.active == f"{S.COLLECTION_PREFIX}Personal"
        assert app._selected_clip_ids == []
    finally:
        app.destroy()


# --- Recently Removed menu -----------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_restore_all_restores_exact_unique_count(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.remove_from_history(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("restore_all", ctx)
        _settle(app)

        assert vault.count_clips(None) == 5
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_restore_all_deduplicates_and_skips_already_active(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    vault.remove_from_history(clips[0].id)
    vault.remove_from_history(clips[1].id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        # Manually restore one clip before invoking restore_all.
        vault.storage.restore(clips[0].id)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("restore_all", ctx)
        _settle(app)

        # All clips are active now; no permanent deletion occurred.
        assert vault.count_clips(None) == 3
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_recently_removed_menu_permanent_delete_present_elsewhere_absent(tmp_path):
    """Commit 5 added Permanently delete selected/all to the Recently
    Removed sidebar menu specifically -- this replaces the earlier
    placeholder that asserted the commands didn't exist yet. The menu
    labels must use the exact required destructive phrasing, and no
    other row type may ever show either command.
    """
    vault = _vault_with_clips(tmp_path, 3)
    for c in vault.storage.list_clips(None):
        vault.storage.soft_delete(c.id)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        removed_ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        removed_matrix = sidebar_context.sidebar_command_matrix(removed_ctx)
        removed_labels = {c.key: c.label for c in removed_matrix}
        assert removed_labels["permanently_delete_all"] == "Permanently delete all items in Recently Removed"
        assert "permanently_delete_selected" in removed_labels
        assert "empty recently removed" not in " ".join(removed_labels.values()).lower()

        all_clips_ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_ALL,
        )
        all_clips_keys = {c.key for c in sidebar_context.sidebar_command_matrix(all_clips_ctx)}
        assert "permanently_delete_selected" not in all_clips_keys
        assert "permanently_delete_all" not in all_clips_keys
    finally:
        app.destroy()


# --- Cleanup Suggestions -------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_cleanup_suggestions_commands_reuse_existing_callbacks(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, "nav_cleanup_suggestions",
        )
        with mock.patch.object(app, "_scan_cleanup_suggestions") as scan, \
             mock.patch.object(app, "_navigate_screen") as nav:
            app._dispatch_sidebar_command("scan_again", ctx)
            app._dispatch_sidebar_command("review_suggestions", ctx)

        scan.assert_called()
        nav.assert_called_with("nav_cleanup_suggestions")
    finally:
        app.destroy()


# --- Stale-menu safety ---------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_stale_captured_context_aborts_visible_command(tmp_path):
    """A context captured on All Clips must not run a view command after
    the user switches to Images (no mutation, no navigation).
    """
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_ALL,
        )
        # Change active view without touching the captured context.
        app._navigate_filter(S.FILTER_SCREENSHOTS)
        _settle(app)
        before_count = vault.count_clips(None)

        app._dispatch_sidebar_command("select_all_visible", ctx)

        # Should have aborted and left the active view/images state alone.
        assert app._filters.active == S.FILTER_SCREENSHOTS
        assert vault.count_clips(None) == before_count
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_stale_captured_context_aborts_restore(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.remove_from_history(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        # Switch to All Clips: the captured Recently Removed context is now stale.
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("restore_all", ctx)

        # restore_all does not require the target row to be active, but it
        # should still target Recently Removed and work (it re-resolves by
        # target key, not active view). The clips should be restored.
        assert vault.count_clips(None) == 3
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()

# --- Home refresh semantics ----------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_home_refresh_when_inactive_does_not_refresh_active_view(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_HOME,
        )
        with mock.patch.object(app, "refresh") as refresh, \
             mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("refresh", ctx)

        refresh.assert_not_called()
        assert app._filters.active == S.FILTER_ALL
        toast.assert_called_once()
        assert "aborted" in toast.call_args[0][0].lower()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_home_refresh_when_active_refreshes_dashboard_without_navigation(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_HOME)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_HOME,
        )
        with mock.patch.object(app, "refresh") as refresh, \
             mock.patch.object(app, "_navigate_filter") as nav_filter, \
             mock.patch.object(app, "_navigate_screen") as nav_screen:
            app._dispatch_sidebar_command("refresh", ctx)

        refresh.assert_called_once()
        nav_filter.assert_not_called()
        nav_screen.assert_not_called()
        assert app._filters.active == S.FILTER_HOME
    finally:
        app.destroy()


# --- Execution-time counts / refreshed set safety ------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_remove_favorite_marks_uses_refreshed_matching_set(tmp_path):
    """The favorite set can change between menu open and command invoke.
    The confirmation and the mutation must use the execution-time set,
    not the count frozen in the menu label.
    """
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:3]:
        vault.set_favorite(c.id, True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_FAVORITES)
        _settle(app)

        query = SearchQuery(filter_name=S.FILTER_FAVORITES)
        app._selection_scope.activate_matching(S.FILTER_FAVORITES, query)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_FAVORITES,
        )
        assert ctx.selection_count == 3

        # One favorite is removed before the command runs.
        vault.set_favorite(clips[0].id, False)

        with mock.patch("tkinter.messagebox.askyesno") as ask:
            ask.return_value = True
            app._dispatch_sidebar_command("remove_favorite_marks", ctx)

        ask.assert_called_once()
        msg = ask.call_args[0][1]
        # Confirmation must show the refreshed matching count (2), not 3.
        assert "2" in msg
        assert "3" not in msg
        assert vault.count_clips(S.FILTER_FAVORITES) == 0
        assert vault.count_clips(None) == 4
        for c in vault.storage.list_clips(None):
            assert c.is_pinned is False
            assert c.deleted_at is None
            assert c.collection is None or c.collection == ""
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_remove_favorite_marks_reports_exact_affected_and_skipped(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.set_favorite(c.id, True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_FAVORITES)
        _settle(app)

        # Select three clips; only the first two are favorites.
        app._selected_clip_ids = [c.id for c in clips[:3]]

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_FAVORITES,
        )

        with mock.patch("tkinter.messagebox.askyesno", return_value=True), \
             mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("remove_favorite_marks", ctx)

        toast.assert_called_once()
        msg = toast.call_args[0][0]
        assert "2" in msg
        assert "1" in msg
        assert "already removed" in msg
        assert sum(c.is_pinned for c in vault.storage.list_clips(None)) == 0
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_restore_all_uses_refreshed_removed_set(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.remove_from_history(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        assert ctx.item_count == 2

        # Another clip is removed before the command runs.
        vault.remove_from_history(clips[2].id)

        with mock.patch("tkinter.messagebox.askyesno") as ask:
            ask.return_value = True
            app._dispatch_sidebar_command("restore_all", ctx)

        ask.assert_called_once()
        msg = ask.call_args[0][1]
        # Confirmation must reflect the execution-time count (3), not 2.
        assert "3" in msg
        assert vault.count_clips(None) == 4
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_restore_all_reports_exact_succeeded_and_skipped(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    vault.remove_from_history(clips[0].id)
    vault.remove_from_history(clips[1].id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        # Restore one before the command so the snapshot sees one already-active
        # clip and one removed clip.
        vault.storage.restore(clips[0].id)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )

        with mock.patch("tkinter.messagebox.askyesno", return_value=True), \
             mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("restore_all", ctx)

        toast.assert_called_once()
        msg = toast.call_args[0][0]
        assert vault.count_clips(None) == 3
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()


# --- Inactive-row targeting: favorites and recently removed ---------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_favorites_remove_marks_while_all_clips_active_aborts(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_FAVORITES,
        )

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("remove_favorite_marks", ctx)

        # No mutation of the unrelated All Clips selection/view.
        assert app._filters.active == S.FILTER_ALL
        assert vault.storage.get_clip(clips[0].id).is_pinned is True
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_recently_removed_restore_all_while_all_clips_active_targets_removed(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.remove_from_history(clips[0].id)
    vault.remove_from_history(clips[1].id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        # Arbitrary unrelated selection in All Clips.
        app._selected_clip_ids = [clips[2].id]
        before_selection = list(app._selected_clip_ids)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("restore_all", ctx)

        # Active view and selection untouched; removed clips restored.
        assert app._filters.active == S.FILTER_ALL
        assert app._selected_clip_ids == before_selection
        assert vault.count_clips(None) == 5
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
    finally:
        app.destroy()


# --- Collection targeting while another collection is active --------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_rename_while_b_active_targets_a_not_b(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        with mock.patch("tkinter.simpledialog.askstring", return_value="Work2"):
            app._dispatch_sidebar_command("rename_collection", ctx)

        assert app._filters.active == f"{S.COLLECTION_PREFIX}Personal"
        work2_ids = {
            c.id for c in vault.storage.list_clips(
                S.COLLECTION_PREFIX + "Work2",
            )
        }
        personal_ids = {
            c.id for c in vault.storage.list_clips(
                S.COLLECTION_PREFIX + "Personal",
            )
        }
        assert work2_ids == {clips[0].id, clips[1].id}
        assert personal_ids == {clips[2].id, clips[3].id}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_export_query_while_b_active_targets_a(tmp_path):
    vault = _vault_with_clips(tmp_path, 6)
    clips = vault.storage.list_clips(None)
    for c in clips[:3]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[3:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # The context/query count reflects Collection A, not the active B view.
        assert ctx.item_count == 3
        matrix = sidebar_context.sidebar_command_matrix(ctx)
        labels = {c.key: c.label for c in matrix}
        assert "3" in labels[sidebar_context.CMD_PROPERTIES]

        # Export is disabled for an inactive collection, and an explicit dispatch aborts.
        with mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("export_collection", ctx)
        toast.assert_called_once()
        assert "aborted" in toast.call_args[0][0].lower()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_stale_rename_aborts_if_collection_ceased(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # Rename/cease Work before the menu command is invoked.
        vault.storage.conn.execute(
            "UPDATE clips SET collection = ? WHERE collection = ?",
            ("Merged", "Work"),
        )
        vault.storage.conn.commit()

        with mock.patch("tkinter.simpledialog.askstring") as ask, \
             mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("rename_collection", ctx)

        ask.assert_not_called()
        toast.assert_called_once()
        assert "aborted" in toast.call_args[0][0].lower()
        # Personal must remain untouched.
        personal_ids = {
            c.id for c in vault.storage.list_clips(
                S.COLLECTION_PREFIX + "Personal",
            )
        }
        assert personal_ids == {clips[2].id, clips[3].id}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_rename_collision_with_existing_name_merges_explicitly(tmp_path):
    """Renaming a collection to a name that already exists merges the two
    collections and does not delete any clips. This is the explicit collision
    behavior: no data loss, no container-table operation."""
    vault = _vault_with_clips(tmp_path, 6)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:5]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.simpledialog.askstring", return_value="Personal"):
            app._dispatch_sidebar_command("rename_collection", ctx)
        _settle(app)

        # All five targeted clips now share the same collection name.
        personal_ids = {
            c.id for c in vault.storage.list_clips(S.COLLECTION_PREFIX + "Personal")
        }
        assert personal_ids == {clips[0].id, clips[1].id, clips[2].id, clips[3].id, clips[4].id}
        assert vault.storage.list_clips(S.COLLECTION_PREFIX + "Work") == []
        assert vault.count_clips(None) == 6  # No clips deleted.
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_rename_preserves_favorites_and_pinned_state(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")
        vault.storage.set_pinned(c.id, True)
        vault.set_favorite(c.id, True)
    content_before = {c.id: c.content for c in vault.storage.list_clips(None)}

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.simpledialog.askstring", return_value="Work2"):
            app._dispatch_sidebar_command("rename_collection", ctx)
        _settle(app)

        for c in vault.storage.list_clips(S.COLLECTION_PREFIX + "Work2"):
            assert c.collection == "Work2"
            assert c.is_pinned is True  # Favorites are stored in is_pinned.
            assert c.content == content_before[c.id]
            assert c.deleted_at is None
            assert app.vault.is_favorite(c.id) is True
    finally:
        app.destroy()


# --- Cleanup Suggestions callback reuse ----------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_cleanup_suggestions_images_commands_reuse_controllers(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_SCREENSHOTS)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_SCREENSHOTS,
        )

        with mock.patch.object(app, "_scan_cleanup_suggestions") as scan, \
             mock.patch.object(app, "_navigate_screen") as nav:
            app._dispatch_sidebar_command("scan_image_duplicates", ctx)
            app._dispatch_sidebar_command("review_tiny_images", ctx)
            app._dispatch_sidebar_command("review_largest_images", ctx)

            assert scan.call_count == 3
            assert all(call.args == ("nav_cleanup_suggestions",) for call in nav.call_args_list)

            # scan_again, review_suggestions and show_ignored route through the same
            # two existing controllers; no detector logic is duplicated in the sidebar.
            nav_cleanup_ctx = sidebar_context.build_sidebar_invocation_context_for_window(
                app, "nav_cleanup_suggestions",
            )
            scan.reset_mock()
            nav.reset_mock()
            app._dispatch_sidebar_command("scan_again", nav_cleanup_ctx)
            scan.assert_called_once()
            nav.assert_not_called()

            nav.reset_mock()
            app._dispatch_sidebar_command("review_suggestions", nav_cleanup_ctx)
            app._dispatch_sidebar_command("show_ignored", nav_cleanup_ctx)
            assert all(call.args == ("nav_cleanup_suggestions",) for call in nav.call_args_list)
    finally:
        app.destroy()


# --- Matching-selection ownership ----------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_ownership_across_rows(tmp_path):
    vault = _vault_with_clips(tmp_path, 8)
    clips = vault.storage.list_clips(None)
    for c in clips[:3]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[3:6]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()

        # Activate matching on All Clips.
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        app._selection_scope.activate_matching(
            S.FILTER_ALL, SearchQuery(filter_name=S.FILTER_ALL),
        )

        # A matching All Clips selection must not be reused by Images.
        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_SCREENSHOTS,
        )
        assert ctx.matching_descriptor is None

        # A matching Collection A selection must not be reused by Collection B.
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)
        app._selection_scope.activate_matching(
            f"{S.COLLECTION_PREFIX}Work",
            SearchQuery(
                filter_name=f"{S.COLLECTION_PREFIX}Work", collection="Work",
            ),
        )
        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Personal", collection_name="Personal",
        )
        assert ctx.matching_descriptor is None

        # A matching Active Vault selection must not be reused by Recently Removed.
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        app._selection_scope.activate_matching(
            S.FILTER_ALL, SearchQuery(filter_name=S.FILTER_ALL),
        )
        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        assert ctx.matching_descriptor is None
    finally:
        app.destroy()


# --- Menu-opening purity -------------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_menu_opening_for_all_row_types_causes_no_mutation(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)
    vault.remove_from_history(clips[1].id)
    vault.storage.set_collection(clips[2].id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        before_active = app._filters.active
        before_selected = list(app._selected_clip_ids)
        before_counts = {
            "all": vault.count_clips(S.FILTER_ALL),
            "images": vault.count_clips(S.FILTER_SCREENSHOTS),
            "favorites": vault.count_clips(S.FILTER_FAVORITES),
            "removed": vault.count_clips(S.FILTER_RECENTLY_REMOVED),
            "work": vault.count_clips(f"{S.COLLECTION_PREFIX}Work"),
        }

        with mock.patch("cache_vault.ui.sidebar_context.popup_menu"):
            for target_key in (
                S.FILTER_HOME,
                S.FILTER_ALL,
                S.FILTER_SCREENSHOTS,
                S.FILTER_FAVORITES,
                S.FILTER_RECENTLY_REMOVED,
                "nav_cleanup_suggestions",
            ):
                ctx = sidebar_context.build_sidebar_invocation_context_for_window(
                    app, target_key,
                )
                sidebar_context.open_sidebar_menu(app, ctx, 0, 0)

            sidebar_context.open_collection_sidebar_menu(app, "Work", 0, 0)
            sidebar_context.open_nav_row_menu(app, NAV_QUICK_PASTE, 0, 0)

        assert app._filters.active == before_active
        assert app._selected_clip_ids == before_selected
        assert vault.count_clips(S.FILTER_ALL) == before_counts["all"]
        assert vault.count_clips(S.FILTER_SCREENSHOTS) == before_counts["images"]
        assert vault.count_clips(S.FILTER_FAVORITES) == before_counts["favorites"]
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == before_counts["removed"]
        assert vault.count_clips(f"{S.COLLECTION_PREFIX}Work") == before_counts["work"]
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_menu_opening_does_not_scan_or_record(tmp_path):
    """Opening a sidebar menu must not perform scans, emit events, or write receipts."""
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        with mock.patch.object(app, "_scan_cleanup_suggestions") as scan, \
             mock.patch.object(app.vault.events, "record") as record:
            for target_key in (
                S.FILTER_HOME,
                S.FILTER_ALL,
                S.FILTER_SCREENSHOTS,
                S.FILTER_FAVORITES,
                S.FILTER_RECENTLY_REMOVED,
                "nav_cleanup_suggestions",
            ):
                ctx = sidebar_context.build_sidebar_invocation_context_for_window(
                    app, target_key,
                )
                sidebar_context.open_sidebar_menu(app, ctx, 0, 0)

            sidebar_context.open_collection_sidebar_menu(app, "Work", 0, 0)
            sidebar_context.open_nav_row_menu(app, NAV_QUICK_PASTE, 0, 0)

        scan.assert_not_called()
        record.assert_not_called()
    finally:
        app.destroy()


# --- Empty Collection command -------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_menu_opening_causes_no_mutation(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        before_counts = {
            "all": vault.count_clips(None),
            "work": vault.count_clips(f"{S.COLLECTION_PREFIX}Work"),
            "pinned": sum(c.is_pinned for c in vault.storage.list_clips(None)),
        }

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        sidebar_context.open_sidebar_menu(app, ctx, 0, 0)

        assert vault.count_clips(None) == before_counts["all"]
        assert vault.count_clips(f"{S.COLLECTION_PREFIX}Work") == before_counts["work"]
        assert sum(c.is_pinned for c in vault.storage.list_clips(None)) == before_counts["pinned"]
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_inactive_collection_a_does_not_target_active_collection_b(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("empty_collection", ctx)
        _settle(app)

        assert {c.id for c in vault.storage.list_clips("col:Personal")} == {clips[2].id, clips[3].id}
        assert {c.id for c in vault.storage.list_clips("col:Work")} == set()
        assert vault.count_clips(None) == 4
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_confirmation_uses_refreshed_membership_count(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # Remove one member before the command runs.
        vault.storage.set_collection(clips[0].id, None)

        with mock.patch("tkinter.messagebox.askyesno") as ask:
            ask.return_value = True
            app._dispatch_sidebar_command("empty_collection", ctx)

        ask.assert_called_once()
        msg = ask.call_args[0][1]
        # Confirmation must show the refreshed count (4), not the original 5.
        assert "4" in msg
        assert "5" not in msg
        assert vault.count_clips("col:Work") == 0
        assert vault.count_clips(None) == 5
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_added_membership_after_menu_creation_is_removed(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    for c in clips[:3]:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # Two more clips join Work before the command is invoked.
        for c in clips[3:]:
            vault.storage.set_collection(c.id, "Work")

        with mock.patch("tkinter.messagebox.askyesno") as ask:
            ask.return_value = True
            app._dispatch_sidebar_command("empty_collection", ctx)

        ask.assert_called_once()
        msg = ask.call_args[0][1]
        assert "5" in msg
        assert vault.count_clips("col:Work") == 0
        assert vault.count_clips(None) == 5
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_renamed_collection_aborts_safely(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )

        # Rename Work to Work2 before invoking the command.
        vault.storage.conn.execute(
            "UPDATE clips SET collection = ? WHERE collection = ?",
            ("Work2", "Work"),
        )
        vault.storage.conn.commit()

        with mock.patch.object(app, "_show_toast") as toast:
            app._dispatch_sidebar_command("empty_collection", ctx)

        toast.assert_called_once()
        msg = toast.call_args[0][0]
        assert "empty" in msg.lower() or "no clips" in msg.lower()
        # Personal collection must be untouched.
        assert {c.id for c in vault.storage.list_clips("col:Personal")} == {clips[2].id, clips[3].id}
        assert {c.id for c in vault.storage.list_clips("col:Work2")} == {clips[0].id, clips[1].id}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_preserves_favorite_pinned_and_other_metadata(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")
        vault.set_favorite(c.id, True)
    content_before = {c.id: c.content for c in vault.storage.list_clips(None)}

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("empty_collection", ctx)
        _settle(app)

        for c in vault.storage.list_clips(None):
            assert c.collection is None
            assert c.is_pinned is True
            assert c.content == content_before[c.id]
            assert c.deleted_at is None
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_does_not_depend_on_visible_selection(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    for c in clips[:2]:
        vault.storage.set_collection(c.id, "Work")
    for c in clips[2:]:
        vault.storage.set_collection(c.id, "Personal")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Personal")
        _settle(app)

        # An unrelated visible selection in the active Personal view.
        app._selected_clip_ids = [clips[2].id, clips[3].id]
        before_selection = list(app._selected_clip_ids)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("empty_collection", ctx)
        _settle(app)

        # Work is emptied, selection is untouched, Personal still active.
        assert app._filters.active == f"{S.COLLECTION_PREFIX}Personal"
        assert app._selected_clip_ids == before_selection
        assert vault.count_clips("col:Work") == 0
        assert vault.count_clips("col:Personal") == 3
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_active_collection_navigates_to_all_clips(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("empty_collection", ctx)
        _settle(app)

        assert app._filters.active == S.FILTER_ALL
        assert vault.count_clips("col:Work") == 0
        assert vault.count_clips(None) == 3
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_empty_membership_produces_no_receipt_and_no_event(tmp_path):
    vault = _vault_with_clips(tmp_path, 2)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        # Empty Work before the command runs.
        for c in clips:
            vault.storage.set_collection(c.id, None)

        before_events = len(app.vault.events.recent())
        with mock.patch("tkinter.messagebox.askyesno") as ask, \
             mock.patch.object(app.vault.events, "record") as record:
            app._dispatch_sidebar_command(
                "empty_collection",
                sidebar_context.build_sidebar_invocation_context_for_window(
                    app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
                ),
            )

        # No confirmation dialog because membership is zero.
        ask.assert_not_called()
        record.assert_not_called()
        assert len(app.vault.events.recent()) == before_events
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_collection_successful_receipt_reports_zero_deletions(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.set_collection(c.id, "Work")

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, f"{S.COLLECTION_PREFIX}Work", collection_name="Work",
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True), \
             mock.patch("cache_vault.core.collection_receipts.write_file_receipt") as receipt:
            app._dispatch_sidebar_command("empty_collection", ctx)

        receipt.assert_called_once()
        payload = receipt.call_args[0][1]
        assert payload["collection_name"] == "Work"
        assert payload["membership_removed"] == 3
        assert payload["clips_deleted"] == 0
        assert payload["assets_deleted"] == 0
        assert payload["disk_bytes_reclaimed"] == 0
    finally:
        app.destroy()


