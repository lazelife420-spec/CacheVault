"""Sidebar context-menu command execution.

``sidebar_context.py`` builds the sidebar's right-click menus; this module
executes the commands those menus dispatch (open/refresh/select/export/
restore/permanently-delete/etc.) plus the small set of helpers only those
commands need. Menu *construction* stays in ``sidebar_context.py`` --
this module never builds a ``tk.Menu``.
"""

from __future__ import annotations

from typing import Any

from ..core import models
from ..core import sidebar_menu_context as smc
from . import sidebar_context
from .filters import NAV_CLEANUP_SUGGESTIONS


def dispatch_sidebar_command(window, key: str, ctx: Any) -> None:
    """Execute a sidebar context-menu command, re-validating live state first."""
    if not window._guard_unlocked():
        return
    # Rebuild context from current app state for every command so stale
    # captured contexts cannot silently act on the wrong view.
    current_ctx = sidebar_context.build_sidebar_invocation_context_for_window(
        window, ctx.target_key, getattr(ctx, "collection_name", None),
    )
    if not current_ctx.is_target_active and key not in (
        smc.CMD_OPEN,
        smc.CMD_SCAN_CLEANUP_SUGGESTIONS,
        smc.CMD_SCAN_AGAIN,
        smc.CMD_REVIEW_SUGGESTIONS,
        smc.CMD_SHOW_IGNORED,
        smc.CMD_RESTORE_ALL,
        smc.CMD_RENAME_COLLECTION,
        smc.CMD_EMPTY_COLLECTION,
        smc.CMD_PERMANENTLY_DELETE_ALL,
        smc.CMD_CLEAR_ALL_CLIPS,
    ):
        window._show_toast("Sidebar context changed; command aborted.")
        return
    # Dispatch through the bound _sidebar_{key} method on window, not the
    # module function directly -- callers (including tests) mock.patch.object
    # individual handlers (e.g. _sidebar_empty_collection) to verify a
    # given menu path never reaches a destructive command, and that only
    # works if dispatch actually goes through the attribute being patched.
    handler = getattr(window, f"_sidebar_{key}", None)
    if handler is None:
        return
    handler(current_ctx)


def sidebar_open(window, ctx: Any) -> None:
    from ..core import storage as S
    target = ctx.target_key
    if target == NAV_CLEANUP_SUGGESTIONS:
        window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)
    elif getattr(ctx, "collection_name", None) is not None:
        window._navigate_filter(f"{S.COLLECTION_PREFIX}{ctx.collection_name}")
    elif target.startswith("nav_"):
        window._navigate_screen(target)
    else:
        window._navigate_filter(target)


def sidebar_refresh(window, ctx: Any) -> None:
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    window.refresh()


def sidebar_scan_cleanup_suggestions(window, ctx: Any) -> None:
    window._scan_cleanup_suggestions()


def sidebar_select_all_visible(window, ctx: Any) -> None:
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    if not window._visible_clip_ids:
        return
    view = window._grid if window._view_mode == "grid" else window._list
    try:
        if not view.winfo_ismapped():
            return
    except Exception:  # noqa: BLE001
        return
    window._selection_scope.clear()
    view.select_all()


def sidebar_select_all_matching(window, ctx: Any) -> None:
    if not ctx.is_target_active or ctx.target_query is None:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    query = ctx.target_query
    view = window._grid if window._view_mode == "grid" else window._list
    try:
        if not view.winfo_ismapped():
            return
    except Exception:  # noqa: BLE001
        return
    matching = window._selection_scope.activate_matching(ctx.target_key, query)
    window._paint_matching_selection_visuals(view)
    window._set_selection_notice(f"All {matching.resolved_count} matching items selected")


def sidebar_deselect_all(window, ctx: Any) -> None:
    window._clear_selection()


def sidebar_export_current_view(window, ctx: Any) -> None:
    if not ctx.is_target_active or ctx.target_query is None:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    collection = window._collection_name_for(ctx.target_key)
    _export_for_query(window, ctx.target_query, collection_name=collection)


def sidebar_export_selected(window, ctx: Any) -> None:
    if not ctx.is_target_active or not ctx.visible_selected_ids:
        window._show_toast("No selection to export.")
        return
    _export_clip_ids(window, list(ctx.visible_selected_ids))


def sidebar_scan_image_duplicates(window, ctx: Any) -> None:
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    window._scan_cleanup_suggestions()
    window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)


def sidebar_review_tiny_images(window, ctx: Any) -> None:
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    window._scan_cleanup_suggestions()
    window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)


def sidebar_review_largest_images(window, ctx: Any) -> None:
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    window._scan_cleanup_suggestions()
    window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)


def sidebar_remove_favorite_marks(window, ctx: Any) -> None:
    if not ctx.is_target_active or ctx.target_query is None:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    ids = _resolve_sidebar_target_ids(window, ctx, prefer_selection=True)
    if not ids:
        window._show_toast("No favorite marks to remove.")
        return
    from tkinter import messagebox
    ok = messagebox.askyesno(
        "Remove Favorite Marks",
        f"Remove favorite marks from {len(ids)} clip{'s' if len(ids) != 1 else ''}?\n\n"
        "Clips and collections are not affected.",
        parent=window,
    )
    if not ok:
        return
    succeeded = 0
    skipped = 0
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is None:
            skipped += 1
            continue
        if clip.is_pinned:
            window.vault.set_favorite(cid, False)
            succeeded += 1
        else:
            skipped += 1
    if skipped:
        window._show_toast(f"Removed favorite marks from {succeeded} clips ({skipped} already removed).")
    else:
        window._show_toast(f"Removed favorite marks from {succeeded} clip{'s' if succeeded != 1 else ''}.")
    window.refresh()


def sidebar_rename_collection(window, ctx: Any) -> None:
    from tkinter import simpledialog
    name = getattr(ctx, "collection_name", None)
    if not name:
        return
    # Re-resolve the collection at execution time. If the target collection
    # no longer exists (renamed or deleted before invocation), abort
    # rather than silently updating zero rows on the wrong set.
    if ctx.target_query is None or window.vault.count_clips(ctx.target_query) == 0:
        window._show_toast("Collection no longer exists or is empty; rename aborted.")
        return
    new_name = simpledialog.askstring("Rename Collection", "New name:", initialvalue=name, parent=window)
    if not new_name or new_name.strip() == name:
        return
    new_name = new_name.strip()
    try:
        window.vault.storage.conn.execute(
            "UPDATE clips SET collection = ? WHERE collection = ?",
            (new_name, name),
        )
        window.vault.storage.conn.commit()
    except Exception as exc:  # noqa: BLE001
        window.vault.storage.conn.rollback()
        raise exc
    window.refresh()
    window._show_toast(f"Renamed collection to '{new_name}'.")


def sidebar_empty_collection(window, ctx: Any) -> None:
    from tkinter import messagebox
    from ..core import storage as S

    name = getattr(ctx, "collection_name", None)
    if not name:
        return

    # Re-resolve current membership at execution time, not the count
    # frozen in the menu label. The command is collection-wide and must
    # not depend on any visible/matching selection.
    ids = _resolve_sidebar_target_ids(window, ctx, prefer_selection=False)
    if not ids:
        window._show_toast(f"Collection '{name}' is already empty. No clips were changed.")
        return

    count = len(ids)
    plural = "s" if count != 1 else ""
    msg = (
        f"Empty collection '{name}'?\n\n"
        f"This will remove the collection label from {count} clip{plural}.\n\n"
        "Clips will remain in your vault.\n"
        "Only the collection label will be removed.\n\n"
        "No clips, files, or favorites will be deleted."
    )
    ok = messagebox.askyesno(
        "Empty collection",
        msg,
        parent=window,
    )
    if not ok:
        return

    result = window.vault.empty_collection(name, ids)
    removed = result.succeeded_count
    skipped = result.skipped_count

    if removed == 0:
        window._show_toast(f"Collection '{name}' is already empty. No clips were changed.")
    elif skipped:
        window._show_toast(
            f"Emptied collection '{name}': removed labels from {removed} clip"
            f"{'s' if removed != 1 else ''} ({skipped} already removed). "
            "Clips remain in your vault."
        )
    else:
        window._show_toast(
            f"Emptied collection '{name}': removed labels from {removed} clip"
            f"{'s' if removed != 1 else ''}. Clips remain in your vault."
        )

    if ctx.is_target_active:
        window._selection_scope.clear()
        window._navigate_filter(S.FILTER_ALL)
    else:
        window.refresh()


def sidebar_export_collection(window, ctx: Any) -> None:
    if not ctx.is_target_active or ctx.target_query is None:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    collection = ctx.collection_name
    _export_for_query(window, ctx.target_query, collection_name=collection)


def sidebar_restore_selected(window, ctx: Any) -> None:
    if not ctx.is_target_active or not ctx.visible_selected_ids:
        window._show_toast("No selection to restore.")
        return
    ids = list(dict.fromkeys(ctx.visible_selected_ids))
    result = window.vault.storage.restore_many(ids)
    for cid in result.succeeded:
        window.vault.events.record(models.EVENT_RESTORED, cid)
    total = len(result.succeeded)
    skipped = len(result.skipped)
    if skipped:
        window._show_toast(f"Restored {total} clip{'s' if total != 1 else ''} ({skipped} already active or missing).")
    else:
        window._show_toast(f"Restored {total} clip{'s' if total != 1 else ''}.")
    window._selection_scope.clear()
    window.refresh()


def sidebar_restore_all(window, ctx: Any) -> None:
    if ctx.target_query is None:
        return
    ids = []
    with window.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
        for batch in batches:
            ids.extend(batch)
    if not ids:
        window._show_toast("No removed items to restore.")
        return
    from tkinter import messagebox
    ok = messagebox.askyesno(
        "Restore All",
        f"Restore all {len(ids)} removed item{'s' if len(ids) != 1 else ''}?",
        parent=window,
    )
    if not ok:
        return
    result = window.vault.storage.restore_many(ids)
    for cid in result.succeeded:
        window.vault.events.record(models.EVENT_RESTORED, cid)
    total = len(result.succeeded)
    skipped = len(result.skipped)
    if skipped:
        window._show_toast(f"Restored {total} clip{'s' if total != 1 else ''} ({skipped} skipped).")
    else:
        window._show_toast(f"Restored {total} clip{'s' if total != 1 else ''}.")
    window._selection_scope.clear()
    window.refresh()


def sidebar_permanently_delete_selected(window, ctx: Any) -> None:
    """Recently Removed only -- guarded by the dispatch allowlist not
    exempting this key, so a stale/inactive context aborts before we
    even get here (mirrors ``sidebar_restore_selected``).
    """
    if not ctx.is_target_active:
        window._show_toast("Sidebar context changed; command aborted.")
        return
    ids = _resolve_sidebar_target_ids(window, ctx, prefer_selection=True)
    if not ids:
        window._show_toast("No selection to permanently delete.")
        return
    window._confirm_and_permanently_delete(ids)


def sidebar_permanently_delete_all(window, ctx: Any) -> None:
    from ..core import permanent_delete as pd

    if ctx.target_query is None:
        return
    ids = []
    with window.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
        for batch in batches:
            ids.extend(batch)
    if not ids:
        window._show_toast("No removed items to permanently delete.")
        return

    plan = pd.build_deletion_plan(window.vault.storage, ids)

    def _run() -> None:
        result = window.vault.permanently_delete_many(ids, confirmation_mode="delete_all")
        window._report_permanent_delete_result(result)

    from .dialogs import PermanentDeleteAllDialog
    PermanentDeleteAllDialog(
        window,
        total_count=len(ids),
        eligible_count=len(plan.eligible_ids),
        skipped_count=len(plan.skipped),
        asset_count=plan.asset_count,
        bytes_scheduled=plan.planned_bytes,
        on_confirm=_run,
    )


def sidebar_review_suggestions(window, ctx: Any) -> None:
    window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)


def sidebar_show_ignored(window, ctx: Any) -> None:
    window._navigate_screen(NAV_CLEANUP_SUGGESTIONS)


def sidebar_scan_again(window, ctx: Any) -> None:
    window._scan_cleanup_suggestions()


def sidebar_properties(window, ctx: Any) -> None:
    label = window._filters.active_label if ctx.is_target_active else ctx.target_key
    window._show_toast(f"{label}: {ctx.item_count} items")


# --- Helpers for sidebar commands ------------------------------------
def _resolve_sidebar_target_ids(window, ctx: Any, *, prefer_selection: bool = False) -> list[str]:
    """Resolve the unique IDs a sidebar command should act on.

    If ``prefer_selection`` is True and a visible/matching selection
    exists, use it. Otherwise use all IDs matching the target query.
    """
    if prefer_selection and ctx.has_selection:
        if ctx.matching_descriptor is not None:
            resolution = window._selection_scope.resolve(
                ctx.target_key,
                ctx.target_query,
                visible_ids=list(ctx.visible_selected_ids),
            )
            if resolution.stale:
                return []
            ids = []
            for batch in resolution.iter_ids():
                ids.extend(batch)
            return list(dict.fromkeys(ids))
        return list(dict.fromkeys(ctx.visible_selected_ids))
    if ctx.target_query is None:
        return []
    ids = []
    with window.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
        for batch in batches:
            ids.extend(batch)
    return list(dict.fromkeys(ids))


def _export_for_query(window, query, *, collection_name: str | None = None) -> None:
    """Export every clip matching ``query`` via the same dialog used
    by the active-view export command.
    """
    if not window._require_founder("exports_advanced"):
        return
    clips = window.vault.list_clips(query)
    if not clips:
        return
    from .dialogs import ExportViewDialog
    ExportViewDialog(window, len(clips),
                     on_export=lambda kind, incl: window._do_export_view(
                         clips, collection_name, kind, incl))


def _export_clip_ids(window, clip_ids: list[str]) -> None:
    """Export the provided clip ids via the existing export dialog."""
    if not window._require_founder("exports_advanced"):
        return
    clips = [window.vault.storage.get_clip(cid) for cid in clip_ids]
    clips = [c for c in clips if c is not None]
    if not clips:
        return
    from .dialogs import ExportViewDialog
    collection = window._collection_name_for(window._filters.active)
    ExportViewDialog(window, len(clips),
                     on_export=lambda kind, incl: window._do_export_view(
                         clips, collection, kind, incl))
