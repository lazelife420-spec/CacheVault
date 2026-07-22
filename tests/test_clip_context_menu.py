"""Commit 2: item context-menu invocation state, right-click routing, and
matching-wide command execution, through the real CacheVaultApp/Tk
wiring.

Deliberately does NOT call open_clip_menu/open_bulk_clip_menu/
open_matching_clip_menu/popup_menu directly -- those end in
tk.Menu.tk_popup(), which is unsafe to invoke in a headless test run.
Instead this tests the building blocks those functions are made of
(build_invocation_context, _append_selection_menu_section against a real
but never-popped-up tk.Menu) and the actual action methods menu commands
dispatch to (_matching_export, _matching_move_to_recently_removed, etc.)
directly -- which is the real business logic under test; the menu is
just a thin dispatch layer on top of it.

Right-click *routing* tests (selection state after a right-click event)
call _context() on the list/grid widget.  _context() normally routes to
_on_context, which is the bound method captured at widget construction
time; following that path reaches tk_popup() which blocks in a modal
grab loop.  Those tests therefore patch _on_context *on the widget
instance* -- the object that actually holds the captured callback -- so
the test stops at the routing boundary, asserts selection state, and
verifies the callback was invoked with the correct arguments, without
ever executing native popup code.

Pure-logic view-classification/command-matrix coverage lives in
tests/test_menu_context.py.
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace
from unittest import mock

import pytest

from cache_vault.core import models
from cache_vault.core import search
from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui import clip_context
from cache_vault.ui.shell import CacheVaultApp, MAX_VISIBLE_CLIPS
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

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
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=_isolated_settings())
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app):
    app._do_refresh_sync()
    wait_for_refresh(app)


def _teardown(app):
    """Destroy the app.  Named _teardown so call sites are explicit about
    the intent; the actual teardown strategy may be refined here without
    touching every finally block across the file."""
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        pass


# --- build_invocation_context ------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_invocation_context_none_mode_when_nothing_selected(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        clip = vault.storage.get_clip(app._visible_clip_ids[0])

        ctx = clip_context.build_invocation_context(app, clip)

        assert ctx.selection_mode == "none"
        assert ctx.was_selected_before_click is False
        assert ctx.clicked_clip_id == clip.id
        assert ctx.view_kind == "active"
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_invocation_context_matching_mode_carries_true_count(tmp_path):
    total = MAX_VISIBLE_CLIPS + 25
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        clip = vault.storage.get_clip(app._visible_clip_ids[0])

        ctx = clip_context.build_invocation_context(app, clip)

        assert ctx.selection_mode == "matching"
        assert ctx.was_selected_before_click is True  # painted as part of the matching set
        assert ctx.matching_count == total
        assert ctx.matching_count != len(ctx.visible_selected_ids)  # true count, not the visible cap
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_invocation_context_view_kind_recently_removed(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    for c in vault.storage.list_clips(None):
        vault.remove_from_history(c.id)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        clip = vault.storage.get_clip(app._visible_clip_ids[0])

        ctx = clip_context.build_invocation_context(app, clip)

        assert ctx.view_kind == "recently_removed"
    finally:
        _teardown(app)


# --- Right-click routing (list) -----------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_unselected_item_selects_only_it_list(tmp_path):
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        target_id = app._visible_clip_ids[2]
        target_clip = vault.storage.get_clip(target_id)

        event = SimpleNamespace(x_root=10, y_root=20, widget=app)
        # Patch _on_context on the widget instance to stop at the callback
        # boundary -- the widget captured the bound method at construction
        # time, so patching the app attribute alone would not intercept it.
        with mock.patch.object(app._list, "_on_context") as on_ctx:
            app._list._context(event, target_clip)

        assert app._selected_clip_ids == [target_id]
        assert app._selection_scope.mode == "none"
        on_ctx.assert_called_once_with(target_clip, event.x_root, event.y_root)
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_selected_item_preserves_visible_multiselect_list(tmp_path):
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        # A settled refresh leaves _visible_clip_ids[0] single-selected by
        # default (see _apply_refresh_snapshot) -- clear first so the
        # Ctrl-clicks below are a clean 3-item accumulation, not an
        # accidental toggle-off of the pre-selected row.
        app._clear_selection()
        ids = app._visible_clip_ids[:3]
        for cid in ids:
            app._list._toggle_select(vault.storage.get_clip(cid))
        assert set(app._selected_clip_ids) == set(ids)

        clicked_clip = vault.storage.get_clip(ids[0])
        event = SimpleNamespace(x_root=10, y_root=20, widget=app)
        with mock.patch.object(app._list, "_on_context") as on_ctx:
            app._list._context(event, clicked_clip)

        assert set(app._selected_clip_ids) == set(ids)  # preserved, not collapsed
        on_ctx.assert_called_once_with(clicked_clip, event.x_root, event.y_root)
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_matching_highlighted_row_preserves_matching_mode_list(tmp_path):
    vault = _vault_with_clips(tmp_path, 15)
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
        with mock.patch.object(app._list, "_on_context") as on_ctx:
            app._list._context(event, target_clip)

        assert app._selection_scope.mode == "matching"  # not silently collapsed
        on_ctx.assert_called_once_with(target_clip, event.x_root, event.y_root)
    finally:
        _teardown(app)


# --- Right-click routing (grid) ------------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_unselected_item_selects_only_it_grid(tmp_path):
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._set_view_mode("grid")
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        target_id = app._visible_clip_ids[2]
        target_clip = vault.storage.get_clip(target_id)

        event = SimpleNamespace(x_root=10, y_root=20, widget=app)
        with mock.patch.object(app._grid, "_on_context") as on_ctx:
            app._grid._context(event, target_clip)

        assert app._selected_clip_ids == [target_id]
        assert app._selection_scope.mode == "none"
        on_ctx.assert_called_once_with(target_clip, event.x_root, event.y_root)
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_matching_highlighted_row_preserves_matching_mode_grid(tmp_path):
    from dataclasses import replace

    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._set_view_mode("grid")
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.mode == "matching"

        # Represent a matching selection whose descriptor count exceeds the
        # rendered set without constructing unnecessary physical widgets.
        orig_matching = app._selection_scope.matching
        matching_count = 130
        app._selection_scope._matching = replace(orig_matching, resolved_count=matching_count)

        assert app._selection_scope.matching.resolved_count == 130
        assert app._selection_scope.matching.resolved_count > len(app._visible_clip_ids)

        target_id = app._visible_clip_ids[0]
        target_clip = vault.storage.get_clip(target_id)

        event = SimpleNamespace(x_root=10, y_root=20, widget=app)
        with mock.patch.object(app._grid, "_on_context") as on_ctx:
            app._grid._context(event, target_clip)

        assert app._selection_scope.mode == "matching"
        assert app._selection_scope.matching.resolved_count == 130
        assert app._selection_scope.matching.signature == orig_matching.signature
        on_ctx.assert_called_once_with(target_clip, event.x_root, event.y_root)
    finally:
        _teardown(app)


# --- Empty-space right-click: no binding exists, selection untouched -----


@pytest.mark.skipif(not OK, reason=REASON)
def test_empty_space_right_click_does_not_clear_selection(tmp_path):
    """No <Button-3> binding exists on the container frame itself (only
    per-row), so right-clicking empty space is structurally a no-op --
    this documents and locks in that existing behavior rather than
    inventing a new empty-space menu (optional, deferred)."""
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        target_id = app._visible_clip_ids[0]
        app._list._select(vault.storage.get_clip(target_id))
        assert app._selected_clip_ids == [target_id]

        # No handler is bound to empty background space -- nothing to call.
        assert "<Button-3>" not in app._list.bind()  # only rows are bound, not the frame

        assert app._selected_clip_ids == [target_id]  # unchanged
    finally:
        _teardown(app)


# --- Popup-boundary regression: selection tests cannot reach tk_popup ----


@pytest.mark.skipif(not OK, reason=REASON)
def test_right_click_selection_tests_never_reach_tk_popup(tmp_path):
    """Prove that the five right-click selection-routing tests stop at the
    _on_context callback boundary and cannot invoke tk.Menu.tk_popup,
    clip_context.popup_menu, or any native modal/grab behavior.

    Strategy: patch clip_context.popup_menu to raise RuntimeError immediately.
    Then exercise all five _context() call paths using the same _on_context
    mock pattern used by those tests.  The test passes only if none of the
    five calls propagates past _on_context -- i.e. popup_menu is never
    reached and the RuntimeError is never raised.
    """
    from cache_vault.ui import clip_context as _clip_ctx

    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        def _must_not_be_called(*args, **kwargs):
            raise RuntimeError(
                "popup_menu was reached: _on_context patch did not intercept the call"
            )

        with mock.patch.object(_clip_ctx, "popup_menu", side_effect=_must_not_be_called):
            # Path 1: unselected item, list
            target = vault.storage.get_clip(app._visible_clip_ids[2])
            ev = SimpleNamespace(x_root=1, y_root=2, widget=app)
            with mock.patch.object(app._list, "_on_context"):
                app._list._context(ev, target)

            # Path 2: selected item preserves multi-select, list
            app._clear_selection()
            for cid in app._visible_clip_ids[:3]:
                app._list._toggle_select(vault.storage.get_clip(cid))
            clicked = vault.storage.get_clip(app._visible_clip_ids[0])
            with mock.patch.object(app._list, "_on_context"):
                app._list._context(ev, clicked)

            # Path 3: matching mode preserved, list
            app._keyboard_select_all_matching(SimpleNamespace(widget=app))
            target3 = vault.storage.get_clip(app._visible_clip_ids[0])
            with mock.patch.object(app._list, "_on_context"):
                app._list._context(ev, target3)

            # Path 4: unselected item, grid
            app._set_view_mode("grid")
            _settle(app)
            target4 = vault.storage.get_clip(app._visible_clip_ids[2])
            with mock.patch.object(app._grid, "_on_context"):
                app._grid._context(ev, target4)

            # Path 5: matching mode preserved, grid
            app._keyboard_select_all_matching(SimpleNamespace(widget=app))
            target5 = vault.storage.get_clip(app._visible_clip_ids[0])
            with mock.patch.object(app._grid, "_on_context"):
                app._grid._context(ev, target5)

        # If we reach here, popup_menu was never called -- the boundary holds.
    finally:
        _teardown(app)


# --- Item-target actions act on the clicked item only ---------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_preview_item_targets_clicked_clip_not_selection(tmp_path):
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        target_id = app._visible_clip_ids[3]

        app._preview_item(target_id)

        assert app._preview._clip is not None
        assert app._preview._clip.id == target_id
        # Previewing must not itself change selection state.
        assert app._selection_scope.mode == "matching"
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_open_item_targets_clicked_clip_not_whole_matching_selection(tmp_path):
    """Regression for "Open must never launch every item in a matching
    selection" -- calls _open_item once for one clip id and asserts only
    that clip's type-specific action fired, not len(matching selection)
    invocations."""
    vault = _vault_with_clips(tmp_path, 15)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        target_id = app._visible_clip_ids[0]
        # The fixture's seeded content ("clip N https://exampleN.com/...")
        # classifies as a link, so _open_item routes to _open_clip_link --
        # patch all three possible type-dispatch targets and assert
        # exactly one fired, exactly once, for the one clicked clip,
        # rather than assuming which classification applies.
        with mock.patch.object(app, "_open_clip_link") as link_spy, \
             mock.patch.object(app, "_edit_clip_text") as text_spy, \
             mock.patch.object(app, "_copy_again") as image_spy:
            app._open_item(target_id)

        calls = [link_spy.call_count, text_spy.call_count, image_spy.call_count]
        assert sum(calls) == 1  # exactly one type-dispatch action fired
        fired = link_spy if link_spy.call_count else (text_spy if text_spy.call_count else image_spy)
        fired.assert_called_once_with(target_id)
    finally:
        _teardown(app)


# --- Menu construction causes no mutation ---------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_building_invocation_context_and_menu_section_causes_no_mutation(tmp_path):
    """Constructing the invocation context and populating a real tk.Menu
    from it (without ever popping it up) must not change selection state,
    vault contents, or the matching selection."""
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        before_count = vault.count_clips(None)
        before_mode = app._selection_scope.mode
        before_selected = list(app._selected_clip_ids)

        clip = vault.storage.get_clip(app._visible_clip_ids[0])
        ctx = clip_context.build_invocation_context(app, clip)
        menu = tk.Menu(app, tearoff=0)
        clip_context._append_selection_menu_section(app, menu, ctx)

        assert vault.count_clips(None) == before_count
        assert app._selection_scope.mode == before_mode
        assert app._selected_clip_ids == before_selected
        menu.destroy()
    finally:
        _teardown(app)


# --- Matching-wide command execution: resolver, not visible ids ----------


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_export_uses_resolver_beyond_visible_cap(tmp_path):
    total = MAX_VISIBLE_CLIPS + 40
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        captured_ids = []

        def fake_export(ids, dest, mode="auto"):
            captured_ids.extend(ids)

        with mock.patch.object(app.vault, "export_proof_zip", side_effect=fake_export), \
             mock.patch("tkinter.filedialog.asksaveasfilename", return_value=str(tmp_path / "out.zip")), \
             mock.patch.object(app, "_require_founder", return_value=True):
            app._matching_export()

        assert len(captured_ids) == total
        assert len(set(captured_ids)) == total  # deduplicated
        assert len(captured_ids) > MAX_VISIBLE_CLIPS
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_move_to_recently_removed_beyond_visible_cap(tmp_path):
    total = MAX_VISIBLE_CLIPS + 30
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._matching_move_to_recently_removed()

        removed_query = search.SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)
        assert vault.count_clips(removed_query) == total
        assert vault.count_clips(search.SearchQuery(filter_name=S.FILTER_ALL)) == 0
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_restore_beyond_visible_cap(tmp_path):
    total = MAX_VISIBLE_CLIPS + 20
    vault = _vault_with_clips(tmp_path, total)
    for c in vault.storage.list_clips(None):
        vault.remove_from_history(c.id)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        assert app._selection_scope.matching.resolved_count == total

        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._matching_restore()

        assert vault.count_clips(search.SearchQuery(filter_name=S.FILTER_ALL)) == total
        assert vault.count_clips(search.SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 0
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_favorite_beyond_visible_cap(tmp_path):
    total = MAX_VISIBLE_CLIPS + 10
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        app._matching_toggle_favorite(True)

        favorited = sum(1 for c in vault.storage.list_clips(None) if c.is_pinned)
        assert favorited == total
        # Un-favoriting must never delete clips.
        assert vault.count_clips(None) == total
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_stale_matching_export_aborts_without_mutating(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        # Change context WITHOUT going through refresh()/invalidate_if_stale
        # -- the action itself must independently detect staleness.
        app._type_filter = models.CLASS_LINK

        called = []
        with mock.patch.object(app.vault, "export_proof_zip", side_effect=lambda *a, **k: called.append(a)), \
             mock.patch.object(app, "_require_founder", return_value=True):
            app._matching_export()

        assert called == []  # aborted -- never reached the export call
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_wide_move_declined_confirmation_does_not_mutate(tmp_path):
    vault = _vault_with_clips(tmp_path, 20)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))

        with mock.patch("tkinter.messagebox.askyesno", return_value=False):
            app._matching_move_to_recently_removed()

        assert vault.count_clips(search.SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 0
        assert vault.count_clips(None) == 20
    finally:
        _teardown(app)


# --- Favorites/collection semantics preserved -----------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_bulk_remove_favorite_marks_never_deletes_clips(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    for c in vault.storage.list_clips(None):
        vault.set_favorite(c.id, True)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_FAVORITES)
        _settle(app)
        app._list.select_all()

        app._bulk_toggle_favorite(False)

        assert vault.count_clips(None) == 5
        assert all(not c.is_pinned for c in vault.storage.list_clips(None))
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_bulk_remove_from_collection_clears_membership_only(tmp_path):
    vault = _vault_with_clips(tmp_path, 4)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.set_collection(c.id, "Work")
    vault.set_favorite(clips[0].id, True)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)
        app._list.select_all()

        app._bulk_remove_from_collection()

        reloaded = {c.id: c for c in vault.storage.list_clips(None)}
        assert len(reloaded) == 4  # no clips deleted
        assert all(c.collection is None for c in reloaded.values())
        assert reloaded[clips[0].id].is_pinned is True  # favorite state untouched
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_collection_removal_disabled_via_matrix_when_matching(tmp_path):
    """End-to-end tie-in to the pure-logic matrix test: in a real app,
    building the invocation context for a matching selection inside a
    collection view yields a disabled remove_from_collection command."""
    from cache_vault.core.menu_context import command_matrix

    vault = _vault_with_clips(tmp_path, 20)
    for c in vault.storage.list_clips(None):
        vault.set_collection(c.id, "Work")
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(f"{S.COLLECTION_PREFIX}Work")
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        clip = vault.storage.get_clip(app._visible_clip_ids[0])
        ctx = clip_context.build_invocation_context(app, clip)

        commands = {c.key: c for c in command_matrix(ctx, matching_wide_supported=clip_context._MATCHING_WIDE_SUPPORTED)}
        assert commands["remove_from_collection"].enabled is False
    finally:
        _teardown(app)


# --- No permanent delete anywhere in this commit's new code ---------------


def test_no_new_permanent_delete_dispatch_key_exists():
    """The new selection-wide dispatch table (shell.py's
    _dispatch_selection_command) must not route any key to a permanent-
    delete action -- checked at the dispatch-table level since that's
    the actual behavior surface, not a source-text scan of the whole
    file."""
    import inspect

    from cache_vault.ui import shell as shell_module

    source = inspect.getsource(shell_module.CacheVaultApp._dispatch_selection_command)
    assert "permanently_remove" not in source
    assert "hard_delete" not in source


# --- Preview/Properties: one honest command, not two labels for one action --


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_menu_item_target_section_has_no_duplicate_preview_command(tmp_path):
    """_append_item_target_commands must expose exactly one preview/
    details command, not a second "Properties" label bound to the
    identical _preview_item callback -- a menu must never show two
    commands for one underlying action."""
    vault = _vault_with_clips(tmp_path, 10)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        clip = vault.storage.get_clip(app._visible_clip_ids[0])

        menu = tk.Menu(app, tearoff=0)
        clip_context._append_item_target_commands(app, menu, clip)

        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
        preview_like = [l for l in labels if "preview" in l.lower() or "properties" in l.lower() or "evidence" in l.lower()]
        assert len(preview_like) == 1, f"expected exactly one preview/details command, got {preview_like}"
        menu.destroy()
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_item_target_section_handles_none_clip_without_error(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        menu = tk.Menu(app, tearoff=0)
        clip_context._append_item_target_commands(app, menu, None)
        assert menu.index("end") is None  # nothing added for a missing clip
        menu.destroy()
    finally:
        _teardown(app)


# --- Stale-after-menu-open: context captured at open time must not be trusted --


@pytest.mark.skipif(not OK, reason=REASON)
def test_dispatch_with_stale_captured_context_still_aborts(tmp_path):
    """Reproduces the exact narrative: (1) activate matching selection,
    (2) build/"open" the invocation context as a menu construction would,
    (3) change search context WITHOUT going through refresh() -- so the
    captured ctx object still shows the old matching_count/signature,
    (4) invoke the command through _dispatch_selection_command using that
    STALE ctx, (5) the operation must abort visibly, (6) no record must
    change. Proves the command validates the LIVE context via
    _resolve_matching_or_abort's independent resolve() call, never
    trusting ctx's cached snapshot."""
    total = 20
    vault = _vault_with_clips(tmp_path, total)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._keyboard_select_all_matching(SimpleNamespace(widget=app))
        clip = vault.storage.get_clip(app._visible_clip_ids[0])

        # (2) Build the context as menu construction would -- captures
        # the CURRENT (still valid) matching count/signature.
        stale_ctx = clip_context.build_invocation_context(app, clip)
        assert stale_ctx.matching_count == total

        # (3) Change context without refresh()/invalidate_if_stale.
        app._search_var.set("something that narrows the result set")

        # (4) Dispatch using the now-stale captured ctx.
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_selection_command("move_to_recently_removed", stale_ctx)

        # (5)/(6) Aborted visibly -- no record changed at all.
        assert vault.count_clips(search.SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 0
        assert vault.count_clips(None) == total
    finally:
        _teardown(app)


# --- Favorite command truth: explicit direction, no inference from mixed state --


@pytest.mark.skipif(not OK, reason=REASON)
def test_mixed_favorite_selection_favorite_selected_sets_all_favorited(tmp_path):
    """A selection with mixed favorite states (some already favorited,
    some not) must not receive an inferred "toggle" direction from the
    clicked item -- "Favorite Selected" always means "make the whole
    selection favorited", regardless of any individual clip's current
    state."""
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)
    vault.set_favorite(clips[1].id, True)
    # clips[2:5] remain unfavorited -- a genuinely mixed selection.
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._list.select_all()

        app._bulk_toggle_favorite(True)

        reloaded = vault.storage.list_clips(None)
        assert all(c.is_pinned for c in reloaded)  # every clip, including the already-favorited ones
    finally:
        _teardown(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_mixed_favorite_selection_remove_favorite_marks_clears_all(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    clips = vault.storage.list_clips(None)
    vault.set_favorite(clips[0].id, True)
    vault.set_favorite(clips[1].id, True)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        app._list.select_all()

        app._bulk_toggle_favorite(False)

        reloaded = vault.storage.list_clips(None)
        assert all(not c.is_pinned for c in reloaded)
        assert len(reloaded) == 5  # clips never deleted by a favorite-mark change
    finally:
        _teardown(app)


def test_favorite_and_unfavorite_are_separate_explicit_commands_not_a_toggle():
    """Pure-logic tie-in: command_matrix must expose two distinct,
    explicitly-directional keys (favorite_selected / unfavorite_selected)
    for a non-favorites view, never a single ambiguous "toggle_favorite"
    key whose direction would have to be inferred from somewhere."""
    from cache_vault.core.menu_context import MenuInvocationContext, VIEW_ACTIVE, command_matrix

    ctx = MenuInvocationContext(
        clicked_clip_id="c1", nav_key=S.FILTER_ALL, view_kind=VIEW_ACTIVE,
        was_selected_before_click=True, selection_mode="visible",
        visible_selected_ids=("a", "b", "c"), matching_signature=None, matching_count=None,
    )
    keys = {c.key for c in command_matrix(ctx, matching_wide_supported=clip_context._MATCHING_WIDE_SUPPORTED)}
    assert "favorite_selected" in keys
    assert "unfavorite_selected" in keys
    assert "toggle_favorite" not in keys
