"""Context menu handlers and construction helper functions."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from ..core import models, copy_clean, storage as S
from ..core.contextmenu import clip_menu_items
from ..core.menu_context import MenuInvocationContext, classify_view_kind, command_matrix
from ..core.selection import analyze_selection
from . import tooltip

# Selection-wide commands with a real matching-wide (snapshot + revalidate)
# implementation in this commit -- see shell.py's _dispatch_selection_command
# and its matching_dispatch table. Anything else stays visible-only;
# command_matrix() disables (never silently narrows) it while matching
# mode is active. select_all_visible/select_all_matching/deselect_all/
# invert_visible are handled directly by the dispatcher, not through this
# matching-wide/visible-only split, so they're intentionally absent here.
_MATCHING_WIDE_SUPPORTED = frozenset({
    "export_selected",
    "favorite_selected",
    "unfavorite_selected",
    "remove_favorite_marks",
    "move_to_recently_removed",
    "restore",
})


def build_invocation_context(window, clip) -> MenuInvocationContext:
    """The single authoritative snapshot of "what's selected, in which
    mode, in which view" that every context-menu command reads from --
    no command re-derives this for itself. Built fresh at right-click
    time; a command that actually mutates must still re-resolve through
    SelectionScope.resolve() immediately before doing so (this context is
    for menu *construction* -- labels, enabled state, dispatch routing --
    not a cached authorization to mutate).
    """
    active = window._filters.active
    query = window._build_query() if hasattr(window, "_build_query") else None
    view_kind = classify_view_kind(active, query)
    scope = window._selection_scope
    visible_ids = tuple(window._selected_clip_ids)
    mode = scope.mode
    matching = scope.matching
    return MenuInvocationContext(
        clicked_clip_id=clip.id,
        nav_key=active,
        view_kind=view_kind,
        was_selected_before_click=clip.id in visible_ids,
        selection_mode=mode if mode in ("matching",) else ("visible" if visible_ids else "none"),
        visible_selected_ids=visible_ids,
        matching_signature=matching.signature if matching else None,
        matching_count=matching.resolved_count if matching else None,
    )


def _append_selection_menu_section(window, menu, ctx: MenuInvocationContext) -> None:
    """Appends the universal selection-wide command section (Select All
    Visible/Matching, Deselect All, Invert Visible, then the view-kind-
    appropriate commands from command_matrix) to any clip context menu --
    single-item, visible-bulk, or matching-wide alike. The single place
    this section is built, so every menu surface stays consistent.
    """
    commands = command_matrix(ctx, matching_wide_supported=_MATCHING_WIDE_SUPPORTED)
    menu.add_separator()
    for command in commands:
        label = command.label if command.enabled else f"{command.label} ({command.reason})"
        menu.add_command(
            label=label,
            state=("normal" if command.enabled else "disabled"),
            command=(lambda k=command.key: window._dispatch_selection_command(k, ctx)) if command.enabled else None,
        )


def open_clip_menu(window, clip, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    ctx = build_invocation_context(window, clip)

    if ctx.is_matching and ctx.was_selected_before_click:
        # Right-click landed on one of the visibly-highlighted matching
        # rows: preserve matching mode, open the matching-aware menu --
        # never silently reinterpret this as "just the rendered ids".
        try:
            open_matching_clip_menu(window, ctx, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    if len(window._selected_clip_ids) > 1 and clip.id in window._selected_clip_ids:
        try:
            open_bulk_clip_menu(window, list(window._selected_clip_ids), x_root, y_root, ctx=ctx)
        finally:
            tooltip.after_menu_close()
        return

    menu = tk.Menu(
        window,
        tearoff=0,
        bg="#1c1c1e" if ctk.get_appearance_mode() == "Dark" else "#f2f2f7",
        fg="#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000",
        activebackground="#008080",
        activeforeground="#ffffff",
        font=("Segoe UI", 10),
    )

    dispatch = {
        "copy_again": lambda: window._copy_again(clip.id),
        "view_larger": lambda: window._open_photo_viewer(clip.id),
        "open_link": lambda: window._open_clip_link(clip.id),
        "open_asset_folder": lambda: window._open_asset_folder(clip.id),
        "drag_out": lambda: window._drag_out_clip(clip.id),
        "toggle_favorite": lambda: window._toggle_favorite(clip.id),
        "mark_keep": lambda: window._mark_keep(clip.id),
        "move_safe": lambda: window._move_to_safe(clip.id),
        "send_to_macro_safe": lambda: window._send_to_macro_safe(clip.id),
        "create_paste_macro": lambda: window._create_macro_from_clip(clip.id),
        "create_editable_copy": lambda: window._create_editable_copy(clip.id),
        "edit_clip_text": lambda: window._edit_clip_text(clip.id),
        "duplicate_editable_clip": lambda: window._duplicate_as_editable_clip(clip.id),
        "export_proof_zip": lambda: window._export_clip_proof(clip.id),
        "view_receipts": window._open_events,
        "view_mobile_receipt": window._open_events,
        "copy_metadata": lambda: window._copy_metadata(clip.id),
        "copy_item_id": lambda: window._copy_text(clip.id, "Copied item ID."),
        "copy_source_summary": lambda: window._copy_clean(clip.id, copy_clean.COPY_SOURCE_SUMMARY),
        "open": lambda: window._open_clip_path(clip.id),
        "reveal": lambda: window._reveal_clip_path(clip.id),
        "remove": lambda: window._remove_from_history(clip.id),
        "restore": lambda: window._restore(clip.id),
        "permanently_remove": lambda: window._permanently_remove(clip.id),
        "combine": window._open_clip_composer,
        "add_to_link_batch": lambda: window._add_to_link_batch(clip.id),
        "save_asset_as": lambda: window._save_asset_as(clip.id),
    }

    if clip.deleted_at is not None:
        original_items = clip_menu_items(clip)
        for item in original_items:
            if item.separator_before:
                menu.add_separator()
            _add_single_item(window, menu, item, dispatch, [clip])
    else:
        # Detect type
        is_image = False
        cls = getattr(clip, "classification", None)
        ct = getattr(clip, "content_type", None)
        if (isinstance(ct, str) and ct.startswith("image")) or (isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower())) or cls == models.CLASS_IMAGE:
            is_image = True
        is_link = (cls == models.CLASS_LINK)

        if is_image:
            primary_keys = ["view_larger", "copy_again", "save_asset_as", "move_safe"]
        elif is_link:
            primary_keys = ["open_link", "copy_clean:copy_link_only", "edit_clip_text", "duplicate_editable_clip", "move_safe"]
        else:
            primary_keys = ["edit_clip_text", "duplicate_editable_clip", "copy_again", "combine", "move_safe"]

        # Gather all leaf items from the original menu items
        all_leaves = []
        def collect_leaves(menu_item):
            if menu_item.children:
                if menu_item.key in ("primary", "copy_clean", "organize", "proof", "advanced", "danger"):
                    for child in menu_item.children:
                        collect_leaves(child)
                else:
                    all_leaves.append(menu_item)
            else:
                all_leaves.append(menu_item)

        original_items = clip_menu_items(clip)
        for item in original_items:
            collect_leaves(item)

        leaves_by_key = {item.key: item for item in all_leaves}

        # Populate primary menu items
        primary_menu_items = []
        for key in primary_keys:
            if key in leaves_by_key:
                primary_menu_items.append(leaves_by_key[key])
            elif ":" in key:
                suffix = key.split(":")[-1]
                for leaf in all_leaves:
                    if leaf.key.endswith(suffix):
                        primary_menu_items.append(leaf)
                        break

        # Everything else goes into More (including remove/receipts)
        used_keys = set(primary_keys)
        used_suffixes = {k.split(":")[-1] for k in used_keys if ":" in k}
        more_menu_items = []
        for item in all_leaves:
            if item.key not in used_keys:
                suffix = item.key.split(":")[-1] if ":" in item.key else item.key
                if suffix not in used_suffixes:
                    more_menu_items.append(item)

        # Build final menu:
        # 1. Primary items
        for item in primary_menu_items:
            if item.separator_before:
                menu.add_separator()
            _add_single_item(window, menu, item, dispatch, [clip])

        # 2. More...
        if more_menu_items:
            menu.add_separator()
            sub = tk.Menu(
                menu,
                tearoff=0,
                bg=menu.cget("bg"),
                fg=menu.cget("fg"),
                activebackground=menu.cget("activebackground"),
                activeforeground=menu.cget("activeforeground"),
                font=menu.cget("font"),
            )
            add_menu_items(window, sub, more_menu_items, dispatch, clip.id)
            menu.add_cascade(label="More…", menu=sub)

    window.vault.events.record(
        copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
        clip.id,
        {"surface": "clip", "classification": clip.classification},
    )

    _append_selection_menu_section(window, menu, ctx)
    popup_menu(window, menu, x_root, y_root)


def open_bulk_clip_menu(window, ids: list[str], x_root: int, y_root: int, *, ctx: MenuInvocationContext | None = None) -> None:
    # Compatibility: self._bulk_copy self._bulk_export_proof self._bulk_move_to_safe self._bulk_remove {n}
    clips = []
    for cid in ids:
        c = window.vault.storage.get_clip(cid)
        if c is not None:
            clips.append(c)

    menu = tk.Menu(
        window,
        tearoff=0,
        bg="#1c1c1e" if ctk.get_appearance_mode() == "Dark" else "#f2f2f7",
        fg="#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000",
        activebackground="#008080",
        activeforeground="#ffffff",
        font=("Segoe UI", 10),
    )

    summary = analyze_selection(clips)

    header_text = f"{len(clips)} clips selected"

    menu.add_command(label=header_text, state="disabled", font=("Segoe UI", 10, "bold"))
    menu.add_separator()

    items = clip_menu_items(clips)

    dispatch = {
        "copy_plain": lambda: window._bulk_copy_format("plain"),
        "copy_markdown": lambda: window._bulk_copy_format("markdown"),
        "combine": window._open_clip_composer,
        "copy_numbered": lambda: window._bulk_copy_format("numbered"),
        "move_safe": window._bulk_move_to_safe,
        "receipt": lambda: window._bulk_create_receipt(summary),
        "export": window._bulk_export_proof,
        "copy_pngs": window._bulk_copy_images,
        "save_pngs": window._bulk_save_images,
        "export_zip": window._bulk_export_zip,
        "copy_paths": window._bulk_copy_paths,
        "view_proof": window._bulk_view_proof,
        "export_bundle": window._bulk_export_bundle,
        "copy_text_links": window._bulk_copy_text_links,
        "save_screenshots": window._bulk_save_images,
        "remove": window._bulk_remove,
    }

    primary_keys = []
    if summary.text_count or summary.link_count:
        primary_keys.append(
            "combine" if summary.selection_class in ("text_only", "link_only") else "copy_text_links"
        )
    export_key = {
        "image_only": "export_zip",
        "mixed": "export_bundle",
    }.get(summary.selection_class, "export")
    primary_keys.extend(["receipt", export_key])
    if summary.image_count > 0:
        primary_keys.append("save_pngs" if summary.selection_class == "image_only" else "save_screenshots")

    all_leaves = []
    def collect_leaves(menu_item):
        if menu_item.children:
            for child in menu_item.children:
                collect_leaves(child)
        else:
            all_leaves.append(menu_item)

    for item in items:
        collect_leaves(item)

    leaves_by_key = {item.key: item for item in all_leaves}

    primary_menu_items = []
    for key in primary_keys:
        if key in leaves_by_key:
            primary_menu_items.append(leaves_by_key[key])

    used_keys = set(primary_keys)
    more_menu_items = []
    for item in all_leaves:
        if item.key not in used_keys:
            more_menu_items.append(item)

    # 1. Primary items
    for item in primary_menu_items:
        _add_single_item(window, menu, item, dispatch, clips)

    # 2. More...
    if more_menu_items:
        menu.add_separator()
        sub = tk.Menu(
            menu, tearoff=0, bg=menu.cget("bg"), fg=menu.cget("fg"),
            activebackground=menu.cget("activebackground"),
            activeforeground=menu.cget("activeforeground"),
            font=menu.cget("font"),
        )
        for item in more_menu_items:
            _add_single_item(window, sub, item, dispatch, clips)
        menu.add_cascade(label="More…", menu=sub)

    window.vault.events.record(
        copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
        None,
        {"surface": "clip_bulk", "count": len(clips)},
    )

    # ctx is None for callers outside the main clip list/grid (e.g. the
    # Home dashboard's own bulk menu, which uses a separate selection
    # mechanism -- see home_dashboard.py's _selected_ids, not
    # window._selected_clip_ids/_selection_scope at all). Only append the
    # shared selection-command section when there's a real invocation
    # context to drive it.
    if ctx is not None:
        _append_selection_menu_section(window, menu, ctx)
    popup_menu(window, menu, x_root, y_root)


def _add_single_item(window, menu, item, dispatch: dict, clips: list[Clip]) -> None:
    if item.key.startswith("copy_clean:"):
        action = item.key.split(":", 1)[1]
        command = lambda a=action: window._copy_clean(clips[0].id, a) if clips else None
    else:
        command = dispatch.get(item.key)

    label = item.label
    if item.key == "edit_clip_text":
        label = "Edit"
    elif item.key == "duplicate_editable_clip":
        label = "Duplicate"
    elif item.key == "copy_again":
        label = "Copy Image" if any(getattr(c, "classification", None) == "image" for c in clips) else "Copy"
    elif item.key == "combine":
        label = "Copy Combined Text"
    elif item.key == "copy_text_links":
        label = "Copy Combined Text"
    elif item.key == "move_safe":
        label = "Move to Safe"
    elif item.key == "view_larger":
        label = "View Larger"
    elif item.key == "save_asset_as":
        label = "Save PNG"
    elif item.key == "open_link":
        label = "Open Link"
    elif item.key.endswith("copy_link_only"):
        label = "Copy Link"
    elif item.key == "receipt":
        label = "Create Proof Receipt"
    elif item.key == "export":
        label = "Export Selection"
    elif item.key in ("export_zip", "export_bundle"):
        label = "Export Selection"
    elif item.key == "save_pngs":
        label = "Save Images"
    elif item.key == "save_screenshots":
        label = "Save Images"
    elif item.key == "remove":
        label = "Delete Selected"

    menu.add_command(
        label=label,
        state=("normal" if item.enabled else "disabled"),
        command=command,
    )


def add_menu_items(window, menu, items, dispatch: dict, clip_id: str) -> None:
    for item in items:
        if item.separator_before:
            menu.add_separator()
        if item.children:
            sub = tk.Menu(menu, tearoff=0)
            add_menu_items(window, sub, item.children, dispatch, clip_id)
            menu.add_cascade(label=item.label, menu=sub, state="normal")
            continue
        if item.key.startswith("copy_clean:"):
            action = item.key.split(":", 1)[1]
            command = lambda a=action, cid=clip_id: window._copy_clean(cid, a)
        else:
            command = dispatch[item.key]
        menu.add_command(
            label=item.label,
            state=("normal" if item.enabled else "disabled"),
            command=command,
        )


def _append_item_target_commands(window, menu, clip) -> None:
    """Open + Preview/Details -- always the CLICKED clip, never the
    active selection (see this commit's item-target-vs-selection-target
    split). Exactly one command per distinct action: this app has no
    dedicated properties/evidence dialog yet, so "Preview" is not
    duplicated under a second "Properties / Show Evidence" label that
    would invoke the identical callback -- a menu must never expose two
    commands for one underlying action. Extracted so it's directly
    testable without invoking tk_popup (see
    tests/test_clip_context_menu.py's no-duplicate-command test).
    """
    if clip is None:
        return
    menu.add_command(label="Open (clicked item)", command=lambda: window._open_item(clip.id))
    menu.add_command(label="Preview / Details (clicked item)", command=lambda: window._preview_item(clip.id))


def open_matching_clip_menu(window, ctx: MenuInvocationContext, x_root: int, y_root: int) -> None:
    """Menu for a right-click landing on one of the visibly-highlighted
    rows of an active "select all matching" selection.

    Item-target commands (Open/Preview) act on the CLICKED clip only --
    never the whole matching set (see this module's docstring / this
    commit's core invariant). Everything else is the shared selection
    section from _append_selection_menu_section, which routes through
    core/menu_context.py's command_matrix + shell.py's
    _dispatch_selection_command: every selection-wide command here
    either resolves the full matching selection through the Commit 1
    resolver at execution time, or is shown disabled with an honest
    reason -- never operates on window._selected_clip_ids alone.
    """
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    clip = window.vault.storage.get_clip(ctx.clicked_clip_id)
    menu = tk.Menu(
        window,
        tearoff=0,
        bg="#1c1c1e" if ctk.get_appearance_mode() == "Dark" else "#f2f2f7",
        fg="#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000",
        activebackground="#008080",
        activeforeground="#ffffff",
        font=("Segoe UI", 10),
    )

    count = ctx.matching_count or 0
    menu.add_command(
        label=f"{count} matching item(s) selected",
        state="disabled",
        font=("Segoe UI", 10, "bold"),
    )
    menu.add_separator()

    _append_item_target_commands(window, menu, clip)

    window.vault.events.record(
        copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
        None,
        {"surface": "clip_matching", "count": count},
    )

    _append_selection_menu_section(window, menu, ctx)
    popup_menu(window, menu, x_root, y_root)


def open_locked_menu(window, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label="Unlock Vault", command=window._lock_screen.focus_unlock)
    menu.add_command(label="Quit", command=window._quit)
    popup_menu(window, menu, x_root, y_root)


def destroy_menu(menu) -> None:
    try:
        menu.destroy()
    except Exception:  # noqa: BLE001
        pass


def popup_menu(window, menu, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    try:
        menu.tk_popup(x_root, y_root)
    finally:
        menu.grab_release()
        tooltip.after_menu_close()
        destroy_menu(menu)


def open_home_clip_menu(window, clip, x_root: int, y_root: int) -> None:
    window._on_clip_select(clip)
    open_clip_menu(window, clip, x_root, y_root)


def open_home_card_menu(window, label: str, filter_key: str | None, x_root: int, y_root: int) -> None:
    from .filters import (
        NAV_EDITABLE_COPIES, NAV_EXPORTS, NAV_MOBILE_ACCESS,
        NAV_MOBILE_INBOX, NAV_STAMPED_RECEIPTS,
    )

    if window._locked():
        open_locked_menu(window, x_root, y_root)
        return
    menu = tk.Menu(window, tearoff=0)
    nav_items = [
        ("All Clips", lambda: window._navigate_filter(S.FILTER_ALL)),
        ("Favorites", lambda: window._navigate_filter(S.FILTER_FAVORITES)),
        ("Screenshots", lambda: window._navigate_filter(S.FILTER_SCREENSHOTS)),
        ("Links", lambda: window._navigate_filter(S.FILTER_LINKS)),
        ("Code", lambda: window._navigate_filter(S.FILTER_CODE)),
        ("Mobile Inbox", lambda: window._navigate_screen(NAV_MOBILE_INBOX)),
        ("Stamped Receipts", lambda: window._navigate_screen(NAV_STAMPED_RECEIPTS)),
        ("Exports", lambda: window._navigate_screen(NAV_EXPORTS)),
    ]
    if filter_key:
        menu.add_command(label=f"Open {label}", command=lambda: window._navigate_filter(filter_key))
        menu.add_separator()
    elif label == "Receipts":
        menu.add_command(label="Open Stamped Receipts", command=lambda: window._navigate_screen(NAV_STAMPED_RECEIPTS))
        menu.add_separator()
    for item_label, command in nav_items:
        menu.add_command(label=item_label, command=command)
    popup_menu(window, menu, x_root, y_root)


def open_home_app_menu(window, x_root: int, y_root: int) -> None:
    if window._locked():
        open_locked_menu(window, x_root, y_root)
        return
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label="Quick Paste", command=window._schedule_quick_paste)
    menu.add_command(label="Save Current Clipboard", command=window._manual_save_clipboard)
    menu.add_separator()
    menu.add_command(label="Open All Clips", command=lambda: window._navigate_filter(S.FILTER_ALL))
    menu.add_command(label="Mobile Inbox", command=lambda: window._navigate_screen(NAV_MOBILE_INBOX))
    menu.add_command(label="Stamped Receipts", command=lambda: window._navigate_screen(NAV_STAMPED_RECEIPTS))
    menu.add_command(label="Settings", command=window._open_settings)
    popup_menu(window, menu, x_root, y_root)


def _find_receipt_file(row) -> Path | None:
    import os
    import json
    from pathlib import Path
    if not row or not getattr(row, "timestamp", None):
        return None
    date_part = row.timestamp[:10]
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    receipts_root = Path(base) / "CacheVault" / "Receipts"
    if not receipts_root.is_dir():
        return None
    dir_path = receipts_root / date_part
    if not dir_path.is_dir():
        return None

    action_raw = getattr(row, "action_raw", "")
    clip_id = getattr(row, "clip_id", None)
    receipt_id = getattr(row, "receipt_id", "")

    if not action_raw:
        return None

    pattern = f"{action_raw}-*.json"
    try:
        for f in dir_path.glob(pattern):
            name = f.name
            if clip_id and f"-{clip_id}-" in name:
                return f
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("id") == receipt_id or (clip_id and data.get("clip_id") == clip_id):
                    return f
            except Exception:
                pass
    except Exception:
        pass
    return None


def open_home_status_menu(window, surface: str, x_root: int, y_root: int) -> None:
    from .filters import NAV_MOBILE_ACCESS, NAV_MOBILE_INBOX, NAV_STAMPED_RECEIPTS

    if window._locked():
        open_locked_menu(window, x_root, y_root)
        return
    summary = window.vault.dashboard_summary()
    menu = tk.Menu(window, tearoff=0)
    if surface == "vault_status":
        menu.add_command(label="Open Safe", command=lambda: window._navigate_filter(f"{S.SAFE_PREFIX}{summary.get('default_safe', 'default')}"))
        menu.add_command(label="Copy Safe Summary", command=window._copy_default_safe_summary)
        menu.add_separator()
    menu.add_command(label="Open Receipts", command=lambda: window._navigate_screen(NAV_STAMPED_RECEIPTS))
    menu.add_command(label="Open Mobile Inbox", command=lambda: window._navigate_screen(NAV_MOBILE_INBOX))
    menu.add_command(label="Mobile Access", command=lambda: window._navigate_screen(NAV_MOBILE_ACCESS))
    popup_menu(window, menu, x_root, y_root)


def open_receipt_menu(window, row, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    import subprocess
    receipt_file = _find_receipt_file(row)
    clip_id = getattr(row, "clip_id", None)
    proof_hash = getattr(row, "proof_hash", "") or ""
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(
        label="Copy Receipt Summary",
        command=lambda: window._copy_receipt_summary(row),
    )
    if receipt_file is not None:
        menu.add_command(
            label="Copy Receipt Path",
            command=lambda: window._copy_text(str(receipt_file), "Copied receipt path."),
        )
    else:
        menu.add_command(
            label="Copy Receipt Path (no local file)",
            state="disabled",
        )
    menu.add_command(
        label="Copy Item ID",
        state=("normal" if clip_id else "disabled"),
        command=lambda: window._copy_text(str(clip_id), "Copied item ID."),
    )
    menu.add_command(
        label="Copy Hash",
        state=("normal" if proof_hash else "disabled"),
        command=lambda: window._copy_text(proof_hash, "Copied hash."),
    )
    menu.add_separator()
    if receipt_file is not None:
        menu.add_command(
            label="Open Receipt File / Folder",
            command=lambda: subprocess.run(["explorer", "/select,", str(receipt_file)], check=False),
        )
    else:
        menu.add_command(
            label="Open Receipt File / Folder (no local file)",
            state="disabled",
        )
    menu.add_command(
        label="Export Proof Zip",
        state=("normal" if clip_id else "disabled"),
        command=lambda: window._export_clip_proof(str(clip_id)),
    )
    popup_menu(window, menu, x_root, y_root)


def rename_collection(window, old_name: str) -> None:
    """Ask user for a new collection name and rename all clips in it."""
    import tkinter.simpledialog as sd
    new_name = sd.askstring(
        "Rename Collection",
        f"Rename '{old_name}' to:",
        initialvalue=old_name,
        parent=window,
    )
    if not new_name or not new_name.strip() or new_name.strip() == old_name:
        return
    new_name = new_name.strip()
    clips = window.vault.list_clips(f"col:{old_name}")
    for clip in clips:
        window.vault.storage.set_collection(clip.id, new_name)
    window.refresh()
    window._show_toast(f"Collection renamed to '{new_name}' ({len(clips)} clips updated).")


def clear_collection(window, name: str) -> None:
    """Remove all clips in a collection from that collection (keeps the clips)."""
    clips = window.vault.list_clips(f"col:{name}")
    for clip in clips:
        window.vault.storage.set_collection(clip.id, None)
    window.refresh()
    window._show_toast(f"Removed {len(clips)} clip(s) from collection '{name}'.")


def open_collection_sidebar_menu(window, name: str, x_root: int, y_root: int) -> None:
    """Right-click context menu on a COLLECTIONS sidebar row.

    Delegated to the unified sidebar context menu (Commit 3) so collection
    row menus share the same inactive-row safety and command matrix.
    """
    from . import sidebar_context
    sidebar_context.open_collection_sidebar_menu(window, name, x_root, y_root)


def open_safe_menu(window, safe: dict, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    safe_id = str(safe.get("id") or "")
    builtin = bool(safe.get("builtin"))
    menu = tk.Menu(
        window,
        tearoff=0,
        bg="#1c1c1e" if ctk.get_appearance_mode() == "Dark" else "#f2f2f7",
        fg="#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000",
        activebackground="#008080",
        activeforeground="#ffffff",
        font=("Segoe UI", 10),
    )
    menu.add_command(
        label="Open Safe",
        command=lambda: window._navigate_filter(f"{S.SAFE_PREFIX}{safe_id}"),
    )
    menu.add_command(
        label="Set as Default Safe",
        command=lambda: window._set_default_safe(safe_id),
    )
    menu.add_command(
        label="Copy Safe Summary",
        command=lambda: window._copy_safe_summary(safe),
    )
    menu.add_command(
        label="New Safe",
        command=window._open_new_safe,
    )
    menu.add_command(
        label="Collapse/Expand Safes",
        command=lambda: window._filters._toggle_section("SAFES"),  # noqa: SLF001
    )
    menu.add_separator()
    menu.add_command(
        label="Rename Safe",
        state=("disabled" if builtin else "normal"),
        command=lambda: window._rename_safe(safe),
    )
    menu.add_command(
        label="Change Icon",
        state=("disabled" if builtin else "normal"),
        command=lambda: window._customize_safe_text(safe, "icon", "Safe icon"),
    )
    menu.add_command(
        label="Change Color",
        state=("disabled" if builtin else "normal"),
        command=lambda: window._customize_safe_text(safe, "accent", "Safe accent color"),
    )
    popup_menu(window, menu, x_root, y_root)
