"""Right-click context menus for the left sidebar / filter navigation."""

from __future__ import annotations

import tkinter as tk

from ..core import storage as S
from . import tooltip
from .clip_context import popup_menu
from .filters import NAV_FOUNDER, NAV_QUICK_PASTE, NAV_VAULT_MACROS


def _locked(window) -> bool:
    return bool(window._locked())


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
    tooltip.before_menu_open()
    if _locked(window):
        try:
            from .clip_context import open_locked_menu
            open_locked_menu(window, x_root, y_root)
        finally:
            tooltip.after_menu_close()
        return
    safe_id = str(safe.get("id") or "")
    builtin = bool(safe.get("builtin"))
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(
        label="Open Safe",
        command=lambda: window._navigate_filter(f"{S.SAFE_PREFIX}{safe_id}"),
    )
    menu.add_command(
        label="Set as Default",
        command=lambda: window._set_default_safe(safe_id),
    )
    menu.add_separator()
    menu.add_command(
        label="Rename",
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
    menu.add_command(
        label="Copy Safe Summary",
        command=lambda: window._copy_safe_summary(safe),
    )
    menu.add_command(label="New Safe", command=window._open_new_safe)
    menu.add_separator()
    menu.add_command(label="Export Safe Proof Zip", state="disabled")
    menu.add_command(label="Delete Safe", state="disabled")
    popup_menu(window, menu, x_root, y_root)


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
    menu.add_command(label="Configure Hotkey", command=window._open_settings)
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
    menu.add_command(label="Configure Hotkey", command=window._open_settings)
    popup_menu(window, menu, x_root, y_root)


def open_nav_row_menu(window, nav_key: str, x_root: int, y_root: int) -> None:
    if nav_key == NAV_FOUNDER:
        open_founder_nav_menu(window, x_root, y_root)
    elif nav_key == NAV_QUICK_PASTE:
        open_quick_paste_nav_menu(window, x_root, y_root)
    elif nav_key == NAV_VAULT_MACROS:
        open_macros_nav_menu(window, x_root, y_root)
