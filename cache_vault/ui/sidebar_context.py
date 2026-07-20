"""Right-click context menus for the left sidebar / filter navigation."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ..core import storage as S
from ..core.sidebar_menu_context import (
    CMD_DESELECT_ALL,
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
    CMD_REVIEW_LARGEST_IMAGES,
    CMD_REVIEW_SUGGESTIONS,
    CMD_REVIEW_TINY_IMAGES,
    CMD_SCAN_AGAIN,
    CMD_SCAN_CLEANUP_SUGGESTIONS,
    CMD_SCAN_IMAGE_DUPLICATES,
    CMD_SELECT_ALL_MATCHING,
    CMD_SELECT_ALL_VISIBLE,
    CMD_SHOW_IGNORED,
    SidebarInvocationContext,
    build_sidebar_invocation_context,
    build_sidebar_query,
    sidebar_command_matrix,
)
from . import tooltip
from .clip_context import popup_menu
from .filters import NAV_FOUNDER, NAV_QUICK_PASTE, NAV_VAULT_MACROS


def _locked(window) -> bool:
    return bool(window._locked())


def _menu_theme() -> dict:
    """Theme colors shared by sidebar context menus."""
    return {
        "bg": "#1c1c1e" if ctk.get_appearance_mode() == "Dark" else "#f2f2f7",
        "fg": "#ffffff" if ctk.get_appearance_mode() == "Dark" else "#000000",
        "activebackground": "#008080",
        "activeforeground": "#ffffff",
        "font": ("Segoe UI", 10),
    }


def _make_menu(window) -> tk.Menu:
    theme = _menu_theme()
    return tk.Menu(
        window,
        tearoff=0,
        bg=theme["bg"],
        fg=theme["fg"],
        activebackground=theme["activebackground"],
        activeforeground=theme["activeforeground"],
        font=theme["font"],
    )


def build_sidebar_invocation_context_for_window(
    window, target_key: str, collection_name: str | None = None,
) -> SidebarInvocationContext:
    """Snapshot the right-clicked sidebar row and the current app state.

    Commands that mutate must still re-resolve live state at dispatch time;
    this context drives menu labels and enabled/disabled state only.
    """
    active_key = window._filters.active
    target_query = build_sidebar_query(target_key, collection_name)
    if target_query is not None:
        item_count = window.vault.count_clips(target_query)
    else:
        item_count = 0

    visible_ids = tuple(window._selected_clip_ids)
    matching = window._selection_scope.matching
    return build_sidebar_invocation_context(
        target_key=target_key,
        active_key=active_key,
        collection_name=collection_name,
        visible_selected_ids=visible_ids,
        matching=matching,
        item_count=item_count,
    )


def _section_actions(window, heading: str, menu: tk.Menu) -> None:
    filters = window._filters  # noqa: SLF001
    collapsed = heading in filters._collapsed  # noqa: SLF001
    menu.add_command(
        label="Expand Section",
        state=("disabled" if not collapsed else "normal"),
        command=lambda: filters.expand_section(heading),
    )
    menu.add_command(
        label="Collapse Section",
        state=("disabled" if collapsed else "normal"),
        command=lambda: filters.collapse_section(heading),
    )
    menu.add_separator()
    menu.add_command(label="Expand All", command=filters.expand_all)
    menu.add_command(label="Collapse All", command=filters.collapse_all)


def open_section_heading_menu(window, heading: str, x_root: int, y_root: int) -> None:
    """Right-click on a collapsible section heading (not SAFES)."""
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    menu = tk.Menu(window, tearoff=0)
    _section_actions(window, heading, menu)
    popup_menu(window, menu, x_root, y_root)


def open_safes_heading_menu(window, x_root: int, y_root: int) -> None:
    """Right-click on the SAFES section heading."""
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label="New Safe", command=window._open_new_safe)
    menu.add_separator()
    _section_actions(window, "SAFES", menu)
    popup_menu(window, menu, x_root, y_root)


def open_safe_menu(window, safe: dict, x_root: int, y_root: int) -> None:
    """Right-click on an individual Safe row in the sidebar."""
    from .clip_context import open_safe_menu as _open_safe_menu
    _open_safe_menu(window, safe, x_root, y_root)


def open_founder_nav_menu(window, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label="Open Founder Status", command=window._open_founder)
    popup_menu(window, menu, x_root, y_root)


def open_quick_paste_nav_menu(window, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label="Open", command=window._schedule_quick_paste)
    menu.add_command(label="Configure Hotkey", command=lambda: window._open_settings("shortcuts"))
    popup_menu(window, menu, x_root, y_root)


def open_macros_nav_menu(window, x_root: int, y_root: int) -> None:
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(
        label="Open",
        command=lambda: window._navigate_screen(NAV_VAULT_MACROS),
    )
    menu.add_command(label="Configure Hotkey", command=lambda: window._open_settings("macros"))
    popup_menu(window, menu, x_root, y_root)


def open_sidebar_menu(window, ctx: SidebarInvocationContext, x_root: int, y_root: int) -> None:
    """Build and show the authoritative context menu for a sidebar row.

    Commands dispatch through ``window._dispatch_sidebar_command`` so the
    shell can revalidate live state before any mutation.
    """
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return

    menu = _make_menu(window)
    for command in sidebar_command_matrix(ctx):
        label = command.label if command.enabled else f"{command.label} ({command.reason})"
        if command.enabled:
            cmd = lambda k=command.key: window._dispatch_sidebar_command(k, ctx)
        else:
            cmd = None
        menu.add_command(label=label, state=("normal" if command.enabled else "disabled"), command=cmd)

    popup_menu(window, menu, x_root, y_root)


def open_collection_sidebar_menu(window, name: str, x_root: int, y_root: int) -> None:
    """Right-click context menu on an individual COLLECTIONS sidebar row."""
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    ctx = build_sidebar_invocation_context_for_window(
        window, S.COLLECTION_PREFIX + name, collection_name=name,
    )
    open_sidebar_menu(window, ctx, x_root, y_root)


def open_nav_row_menu(window, nav_key: str, x_root: int, y_root: int) -> None:
    """Route nav-row right-clicks to the correct menu. Legacy dialog-only
    rows keep their existing small menus; everything else uses the shared
    sidebar command matrix.
    """
    if nav_key == NAV_FOUNDER:
        open_founder_nav_menu(window, x_root, y_root)
    elif nav_key == NAV_QUICK_PASTE:
        open_quick_paste_nav_menu(window, x_root, y_root)
    elif nav_key == NAV_VAULT_MACROS:
        open_macros_nav_menu(window, x_root, y_root)
    else:
        ctx = build_sidebar_invocation_context_for_window(window, nav_key)
        open_sidebar_menu(window, ctx, x_root, y_root)
