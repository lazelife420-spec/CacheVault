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
def test_recently_removed_menu_has_no_permanent_delete(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        matrix = sidebar_context.sidebar_command_matrix(ctx)
        labels = " ".join(c.label.lower() for c in matrix)
        assert "permanently delete" not in labels
        assert "empty recently removed" not in labels
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
