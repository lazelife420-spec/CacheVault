"""Context menu handlers and construction helper functions."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from ..core import models, copy_clean, storage as S
from ..core.contextmenu import clip_menu_items
from ..core.selection import analyze_selection
from . import tooltip


def open_clip_menu(window, clip, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    if len(window._selected_clip_ids) > 1 and clip.id in window._selected_clip_ids:
        try:
            open_bulk_clip_menu(window, list(window._selected_clip_ids), x_root, y_root)
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
        "open_link": lambda: window._open_clip_link(clip.id),
        "open_asset_folder": lambda: window._open_asset_folder(clip.id),
        "drag_out": lambda: window._drag_out_clip(clip.id),
        "toggle_favorite": lambda: window._toggle_favorite(clip.id),
        "mark_keep": lambda: window._mark_keep(clip.id),
        "move_safe": lambda: window._move_to_safe(clip.id),
        "send_to_macro_safe": lambda: window._send_to_macro_safe(clip.id),
        "create_paste_macro": lambda: window._create_macro_from_clip(clip.id),
        "create_editable_copy": lambda: window._create_editable_copy(clip.id),
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
    }

    items = clip_menu_items(clip)
    for item in items:
        if item.separator_before:
            menu.add_separator()
        if item.children:
            menu.add_separator()
            for child in item.children:
                if child.separator_before:
                    menu.add_separator()
                _add_single_item(window, menu, child, dispatch, [clip])
            continue
        _add_single_item(window, menu, item, dispatch, [clip])

    window.vault.events.record(
        copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
        clip.id,
        {"surface": "clip", "classification": clip.classification},
    )

    popup_menu(window, menu, x_root, y_root)


def open_bulk_clip_menu(window, ids: list[str], x_root: int, y_root: int) -> None:
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

    header_text = f"{len(clips)} selected items"
    if summary.selection_class == "link_only":
        header_text = f"{summary.link_count} links selected"
    elif summary.selection_class == "image_only":
        header_text = f"{summary.image_count} screenshots selected"
    elif summary.selection_class == "text_only":
        header_text = f"{summary.text_count} text clips selected"

    menu.add_command(label=header_text, state="disabled", font=("Segoe UI", 10, "bold"))

    if summary.selection_class == "mixed":
        sub_text = f"{summary.link_count} links · {summary.image_count} screenshots · {summary.text_count} text clips"
        menu.add_command(label=sub_text, state="disabled", font=("Segoe UI", 9, "italic"))

    menu.add_separator()

    items = clip_menu_items(clips)

    dispatch = {
        "copy_plain": lambda: window._bulk_copy_format("plain"),
        "copy_markdown": lambda: window._bulk_copy_format("markdown"),
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

    for item in items:
        if item.separator_before:
            menu.add_separator()
        _add_single_item(window, menu, item, dispatch, clips)

    window.vault.events.record(
        copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
        None,
        {"surface": "clip_bulk", "count": len(clips)},
    )

    popup_menu(window, menu, x_root, y_root)


def _add_single_item(window, menu, item, dispatch: dict, clips: list[Clip]) -> None:
    if item.key.startswith("copy_clean:"):
        action = item.key.split(":", 1)[1]
        command = lambda a=action: window._copy_clean(clips[0].id, a) if clips else None
    else:
        command = dispatch.get(item.key)

    menu.add_command(
        label=item.label,
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
        menu.add_command(label="Export Safe Proof Zip (planned)", state="disabled")
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
    """Right-click context menu on a COLLECTIONS sidebar row."""
    tooltip.before_menu_open()
    if window._locked():
        try:
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    menu = tk.Menu(window, tearoff=0)
    menu.add_command(
        label=f"View '{name}' Clips",
        command=lambda: window._navigate_filter(f"col:{name}"),
    )
    menu.add_separator()
    menu.add_command(
        label="Rename Collection…",
        command=lambda: rename_collection(window, name),
    )
    menu.add_command(
        label="Remove All from Collection",
        command=lambda: clear_collection(window, name),
    )
    popup_menu(window, menu, x_root, y_root)


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
    menu.add_separator()
    menu.add_command(label="Export Safe Proof Zip (planned)", state="disabled")
    menu.add_command(
        label="Delete Safe (planned)",
        state="disabled",
    )
    popup_menu(window, menu, x_root, y_root)
