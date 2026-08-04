"""Commit 1: shell-level keyboard wiring for visible vs. matching
selection (Ctrl+A, Ctrl+Shift+A, Escape, text-entry guard) and
matching-selection invalidation on context change.

Headless (Tk-independent) coverage of the underlying scope/resolver
logic lives in tests/test_selection_scope.py. This file exercises the
same behavior through the real CacheVaultApp/Tk wiring, matching the
existing pattern in tests/test_clip_render_cap.py.
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest
from unittest import mock

from cache_vault.core import models
from cache_vault.core import search
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.core import storage as S
from cache_vault.ui.shell import CacheVaultApp, MAX_VISIBLE_CLIPS
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

OK, REASON = probe_tk_ui()


def _isolated_settings() -> Settings:
    """capture_paused=True pauses ClipboardMonitor entirely at
    construction (see shell.py: ``if settings.capture_paused:
    self._monitor.pause()``), so CacheVaultApp never reads or captures
    whatever happens to be on the real OS clipboard in this environment
    -- confirmed necessary: without this, app construction was observed
    auto-capturing exactly one live-clipboard item, which made count-
    based assertions non-deterministic. This does not affect this file's
    own explicit ``vault.capture(..., force=True)`` seed calls --
    ``force=True`` bypasses the capture_paused check (see vault.py).
    """
    return Settings(capture_paused=True)


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n, prefix="clip"):
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=_isolated_settings())
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app):
    app._do_refresh_sync()
    wait_for_refresh(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_a_still_selects_only_visible_rendered_rows(tmp_path):
    """Existing Ctrl+A behavior (select rendered rows only) must be
    unchanged by adding Ctrl+Shift+A alongside it."""
    total = MAX_VISIBLE_CLIPS + 30
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        app._keyboard_select_all(SimpleNamespace(widget=app))

        assert len(app._selected_clip_ids) == MAX_VISIBLE_CLIPS
        assert app._selection_scope.mode == "none"  # Ctrl+A never activates matching
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_shift_a_selects_beyond_render_cap_without_extra_widgets(tmp_path):
    total = MAX_VISIBLE_CLIPS + 30
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        # Deterministic: capture_paused=True (see _isolated_settings)
        # means the app never captures from the real clipboard, so
        # `total` (the exact number of clips this fixture seeded) is the
        # exact expected count -- no environmental fudge needed.
        assert vault.count_clips(app._build_query()) == total

        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        assert app._selection_scope.mode == "matching"
        assert app._selection_scope.matching.resolved_count == total
        # Rendered rows stay capped -- a matching selection over 150+
        # clips must not materialize a widget per match.
        assert len(app._list._row_by_id) == MAX_VISIBLE_CLIPS
        # Visible rows are still given the existing visual "selected"
        # treatment (a subset of the matching set), not left unpainted.
        assert len(app._selected_clip_ids) == MAX_VISIBLE_CLIPS
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_shift_a_shows_matching_count_notice(tmp_path):
    total = 12
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        label = app._page_header._selection_notice_label
        assert label.cget("text") == f"All {total} matching items selected"
        # winfo_ismapped() requires the whole window to be viewable, which
        # a withdraw()n test window never is -- place_info() reflects
        # whether place() was actually called regardless of that.
        assert label.place_info() != {}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_invalidated_by_search_change(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._search_var.set("clip 1")
        _settle(app)

        assert app._selection_scope.mode == "none"
        # set_selection_notice(None) hides the label via place_forget(),
        # which does not clear its last-configured text -- assert on
        # placement (place_info() is empty once forgotten), not the
        # (unmap-only, and unreliable under a withdraw()n window)
        # winfo_ismapped()/label content.
        assert app._page_header._selection_notice_label.place_info() == {}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_invalidated_by_type_filter_change(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._type_filter = models.CLASS_LINK
        _settle(app)

        assert app._selection_scope.mode == "none"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_invalidated_by_sort_change(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._sort_key = models.SORT_OLDEST_ADDED
        _settle(app)

        assert app._selection_scope.mode == "none"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_invalidated_by_navigation_change(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._navigate_screen(S.FILTER_SCREENSHOTS)
        _settle(app)

        assert app._selection_scope.mode == "none"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_invalidated_by_active_vs_recently_removed(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._navigate_screen(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        assert app._selection_scope.mode == "none"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_escape_clears_matching_selection(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"
        assert app._search_var.get() == ""  # so Escape reaches the selection-clear branch

        app._on_escape_pressed()

        assert app._selection_scope.mode == "none"
        assert app._selected_clip_ids == []
        assert app._page_header._selection_notice_label.place_info() == {}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_a_in_text_entry_preserves_normal_text_selection(tmp_path):
    """Plain Ctrl+A while focus is in a text-entry widget must not be
    hijacked into "select all visible clips" -- _keyboard_select_all
    must return None (letting Tk's/the widget's own default Ctrl+A
    text-select-all binding run normally), not "break" (which would
    swallow the event), and must not touch clip selection state at all."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        assert app._selected_clip_ids == []

        entry = tk.Entry(app)
        entry.insert(0, "some typed text")
        result = app._keyboard_select_all(SimpleNamespace(widget=entry))

        assert result is None  # not "break" -- event must propagate to the widget
        assert app._selected_clip_ids == []  # clip selection untouched
        assert app._selection_scope.mode == "none"
        entry.destroy()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_shift_a_ignored_while_focus_in_text_entry(tmp_path):
    """Delete/Ctrl+A/Ctrl+Shift+A must not fire while the user is typing
    in a text field -- normal text-editing behavior (e.g. native text
    select-all) must be preserved there, not hijacked into clip
    selection."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        entry = tk.Entry(app)
        result = app._keyboard_select_all_matching(SimpleNamespace(widget=entry))

        assert result is None
        assert app._selection_scope.mode == "none"
        entry.destroy()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_delete_key_never_reaches_permanent_removal(tmp_path):
    """Delete must route only to the existing safe soft-remove path
    (bulk_remove -> Recently Removed), never to hard_delete/
    permanently_remove -- this behavior is unchanged by this commit, but
    is asserted here because Commit 1 adds new selection modes that a
    future regression could accidentally wire into Delete."""
    import inspect

    from cache_vault.ui import shell as shell_module

    source = inspect.getsource(shell_module.CacheVaultApp._keyboard_remove_selected)
    assert "permanently_remove" not in source
    assert "hard_delete" not in source
    assert "_bulk_remove" in source or "remove_from_history" in source


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_resolve_refreshes_count_through_shell_query_builder(tmp_path):
    """End-to-end tie-in: resolving through app._selection_scope using
    app._build_query()/app._filters.active (what a future bulk-action
    commit will call) reflects clips added after activation, and detects
    staleness when the shell's own query state changes."""
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        assert vault.count_clips(app._build_query()) == 10  # deterministic: isolated clipboard
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        for i in range(5):
            vault.capture(f"late clip {i} https://late{i}.example.com", force=True)

        active = app._filters.active
        query = app._build_query()
        resolution = app._selection_scope.resolve(active, query)
        assert resolution.stale is False
        assert resolution.count == 15

        # Now change context without going through refresh() -- resolve()
        # must independently detect staleness against the caller's
        # current context, not rely on invalidate_if_stale having run.
        app._type_filter = models.CLASS_LINK
        stale_query = app._build_query()
        stale_resolution = app._selection_scope.resolve(active, stale_query)
        assert stale_resolution.stale is True
        assert stale_resolution.count == 0
    finally:
        app.destroy()


# --- Exactly one active selection mode --------------------------------------
#
# Visible and matching selection must never both be authoritative. A real
# manual selection action (click/Ctrl-click/Shift-click/right-click
# collapse/Ctrl+A) while matching mode is active must exit matching mode
# and make the manual action's result authoritative -- not leave the "All
# N matching" banner showing while _selected_clip_ids has silently
# diverged from it.


@pytest.mark.skipif(not OK, reason=REASON)
def test_click_after_matching_selection_exits_matching_and_selects_one(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"
        assert len(app._selected_clip_ids) == 20

        target_id = app._visible_clip_ids[3]
        target_clip = vault.storage.get_clip(target_id)
        app._list._click(SimpleNamespace(state=0, widget=app), target_clip)

        assert app._selection_scope.mode == "none"
        assert app._selected_clip_ids == [target_id]
        assert app._page_header._selection_notice_label.place_info() == {}

        # A subsequent action resolves exactly the one visible item, not
        # the original 20-item matching set -- this is the exact call
        # shape a future bulk action would make.
        active = app._filters.active
        resolution = app._selection_scope.resolve(
            active, app._build_query(), visible_ids=app._selected_clip_ids,
        )
        assert resolution.mode == "visible"
        assert resolution.count == 1
        assert resolution.resolve_all_ids() == [target_id]
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_click_after_matching_selection_exits_matching_mode(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        # Ctrl-click on an already-all-selected row toggles it *off* --
        # the point here isn't the resulting set, it's that matching mode
        # is gone the instant a manual Ctrl-click happens.
        target_id = app._visible_clip_ids[0]
        target_clip = vault.storage.get_clip(target_id)
        app._list._click(
            SimpleNamespace(state=app._list._CTRL_MASK, widget=app), target_clip,
        )

        assert app._selection_scope.mode == "none"
        assert app._page_header._selection_notice_label.place_info() == {}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_shift_click_after_matching_selection_exits_matching_mode(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        target_id = app._visible_clip_ids[5]
        target_clip = vault.storage.get_clip(target_id)
        app._list._click(
            SimpleNamespace(state=app._list._SHIFT_MASK, widget=app), target_clip,
        )

        assert app._selection_scope.mode == "none"
        assert app._page_header._selection_notice_label.place_info() == {}
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_collapsing_to_one_item_exits_matching_mode(tmp_path):
    """Right-click's existing collapse-to-single-item behavior (when the
    clicked row isn't part of the current multi-selection) must exit
    matching mode via the same _select() -> _on_clip_select path a plain
    click uses. Directly puts the view's concrete selection into a state
    where the clicked row is not part of it (len(selected_ids) <= 1),
    matching ClipList._context's own collapse condition, rather than
    depending on select_all()'s painted set never containing a single
    row (which would defeat the point of the test)."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        other_id, target_id = app._visible_clip_ids[0], app._visible_clip_ids[1]
        app._selected_clip_ids = [other_id]
        app._list._selected_ids = {other_id}  # simulates "clicked row not in current selection"
        target_clip = vault.storage.get_clip(target_id)
        event = SimpleNamespace(x_root=10, y_root=20, widget=app)

        with mock.patch.object(app._list, "_on_context") as on_context:
            app._list._context(event, target_clip)

        # Mode must have transitioned: matching → none.
        assert app._selection_scope.mode == "none"
        # Collapsed to exactly the right-clicked clip.
        assert app._selected_clip_ids == [target_id]
        # Selection notice banner must be hidden.
        assert app._page_header._selection_notice_label.place_info() == {}
        # Popup boundary: callback called exactly once with (clip, x_root, y_root).
        on_context.assert_called_once_with(target_clip, 10, 20)
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_preserving_existing_multiselect_keeps_matching_mode(tmp_path):
    """The complementary case: right-clicking a row that IS part of the
    current (matching-painted) multi-selection preserves it -- this is
    "open a menu for the current selection", not a scope-changing manual
    selection action, so matching mode must survive."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        target_id = app._visible_clip_ids[0]
        target_clip = vault.storage.get_clip(target_id)
        event = SimpleNamespace(x_root=10, y_root=20, widget=app)

        with mock.patch.object(app._list, "_on_context") as on_context:
            app._list._context(event, target_clip)

        # Mode must be preserved: matching stays matching.
        assert app._selection_scope.mode == "matching"
        # Matching descriptor must still be set (not cleared by the right-click).
        assert app._selection_scope._matching is not None
        # Popup boundary: callback called exactly once with (clip, x_root, y_root).
        on_context.assert_called_once_with(target_clip, 10, 20)
    finally:
        app.destroy()


# --- Legacy actions must not silently use only visible ids while matching --


@pytest.mark.skipif(not OK, reason=REASON)
def test_ctrl_shift_a_then_delete_is_blocked_not_silent(tmp_path):
    """Delete after Ctrl+Shift+A must neither permanently delete nor
    silently soft-remove only the up-to-120 rendered ids while the "All
    N matching" banner claims a larger set -- it must refuse to run."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"
        before = vault.count_clips(None)

        result = app._keyboard_remove_selected(SimpleNamespace(widget=app))

        assert result == "break"
        # Nothing moved, nothing deleted -- the matching selection is
        # still intact (blocked, not silently consumed).
        assert vault.count_clips(None) == before
        removed_query = search.SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)
        assert vault.count_clips(removed_query) == 0
        assert app._selection_scope.mode == "matching"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_bulk_actions_blocked_while_matching_active(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        assert app._block_if_matching_active("Copy") is True
        assert app._block_if_matching_active("Export") is True
        assert app._block_if_matching_active("Move to Safe") is True
        assert app._block_if_matching_active("Remove") is True

        app._selection_scope.clear()
        assert app._block_if_matching_active("Copy") is False
    finally:
        app.destroy()


# --- Same-context refresh preserves matching visuals ------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_same_context_refresh_preserves_matching_selection_and_repaints(tmp_path):
    """A refresh that doesn't change the matching context (e.g. a new
    capture arriving) must keep matching mode active, keep the banner
    showing, and keep every re-rendered row painted as selected -- not
    silently collapse to a single highlighted row the way a plain
    refresh does for ordinary visible selection."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"
        matching_before = app._selection_scope.matching

        # A same-context refresh: nothing about nav/search/filter/sort
        # changed, just new data (a fresh capture).
        vault.capture("unrelated new capture https://new.example.com", force=True)
        _settle(app)

        assert app._selection_scope.mode == "matching"
        assert app._selection_scope.matching is matching_before  # not invalidated
        assert app._page_header._selection_notice_label.place_info() != {}
        # Every rendered row is still painted selected -- not collapsed
        # to one row the way plain visible selection would be.
        assert len(app._list._selected_ids) == len(app._list._render_order)
        assert len(app._list._row_by_id) <= MAX_VISIBLE_CLIPS  # still no extra widgets
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_context_changing_refresh_still_clears_matching_selection(tmp_path):
    """The complementary case to the above: a refresh that DOES change
    context (here, a search) must still invalidate matching mode, exactly
    as designed before this hardening pass."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        app._search_var.set("clip 1")
        _settle(app)

        assert app._selection_scope.mode == "none"
    finally:
        app.destroy()


# --- Clipboard isolation -----------------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_app_construction_creates_zero_unexpected_records(tmp_path):
    """CacheVaultApp construction must never read or capture the real OS
    clipboard -- with capture_paused=True (see _isolated_settings), an
    app built over a freshly-seeded vault must show exactly the clips
    this test put there, nothing more."""
    vault = _vault_with_clips(tmp_path, 7)
    before = vault.count_clips(None)
    assert before == 7

    app = _make_app(vault)
    try:
        app.withdraw()
        # Construction alone (no navigation, no refresh) must not have
        # added anything.
        assert vault.count_clips(None) == 7

        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        # A settled refresh cycle must not have added anything either --
        # confirms the monitor genuinely never captured, not just that
        # construction alone didn't.
        assert vault.count_clips(None) == 7
        assert vault.count_clips(app._build_query()) == 7
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_clipboard_monitor_is_paused_not_just_uncaptured_by_luck(tmp_path):
    """Directly confirms the mechanism (monitor.paused), not just its
    absence of side effects -- distinguishes "isolated by design" from
    "happened not to capture anything this run."""
    vault = _vault_with_clips(tmp_path, 1)
    app = _make_app(vault)
    try:
        app.withdraw()
        assert app._monitor.paused is True
    finally:
        app.destroy()


def test_production_vault_path_never_used_by_this_suite(tmp_path):
    """Sanity check with no Tk dependency: every fixture in this file
    builds VaultStorage against an explicit tmp_path, never
    default_db_path() (the real %LOCALAPPDATA%\\CacheVault location) --
    confirms these tests structurally cannot touch a real user's vault
    regardless of environment."""
    import inspect

    source = inspect.getsource(_vault_with_clips)
    assert "default_db_path" not in source
    assert "tmp_path" in source
