"""Regression coverage for the bounded Tk context-menu lifecycle.

The copied-profile packaged A/B test exposed that repeated clip context-menu
invocations could exhaust the Tcl menu pool:

    TclError: No more menus can be allocated.

These tests prove that the active-menu lifecycle helper keeps the live menu
count bounded regardless of how many times a menu is opened and dismissed.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest import mock

import customtkinter as ctk
import pytest
import tkinter as tk

from cache_vault.ui import clip_context


def _count_menus(tk, widget: str = ".") -> int:
    """Recursively count all Tcl Menu widgets."""
    count = 0
    try:
        children = tk.call("winfo", "children", widget)
    except tk.TclError:
        return 0
    if not children:
        return 0
    # winfo children can return a Tcl list string or a tuple depending on the
    # tkinter wrapper and the number of children.
    if isinstance(children, tuple):
        child_list = list(children)
    else:
        child_list = children.split()
    for child in child_list:
        try:
            if tk.call("winfo", "class", child) == "Menu":
                count += 1
        except tk.TclError:
            pass
        count += _count_menus(tk, child)
    return count


def _wait_for_deferred_destroy(tk_root, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        tk_root.update()
        time.sleep(0.01)


@pytest.fixture
def menu_window():
    """A fresh window object that supports the active-menu lifecycle attributes.

    Isolated from the shared Tk root so replay-guard state does not leak
    between tests.
    """
    return SimpleNamespace()


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_repeated_popup_menus_keep_menu_count_bounded(menu_window, tk_root):
    """Opening and dismissing many context menus in sequence must not leak
    Tcl menu widgets."""
    peak = 0
    for i in range(30):
        menu = tk.Menu(tk_root, tearoff=0)
        menu.add_command(label=f"Item {i}", command=lambda: None)
        with mock.patch.object(menu, "tk_popup"):
            clip_context.popup_menu(menu_window, menu, 0, 0)
        tk_root.update()
        peak = max(peak, _count_menus(tk_root))

    _wait_for_deferred_destroy(tk_root)
    final = _count_menus(tk_root)
    assert final <= 2, f"too many live menus after cleanup: {final}"
    assert peak <= 3, f"peak live menus too high: {peak}"


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_new_menu_replaces_prior_active_menu(menu_window, tk_root):
    """Opening a new menu while another is still in its deferred cleanup
    window must destroy the previous one."""
    first = tk.Menu(tk_root, tearoff=0)
    first.add_command(label="First", command=lambda: None)
    with mock.patch.object(first, "tk_popup"):
        clip_context.popup_menu(menu_window, first, 0, 0)
    tk_root.update()
    assert menu_window._active_popup_menu is first

    second = tk.Menu(tk_root, tearoff=0)
    second.add_command(label="Second", command=lambda: None)
    with mock.patch.object(second, "tk_popup"):
        clip_context.popup_menu(menu_window, second, 10, 10)
    tk_root.update()
    assert menu_window._active_popup_menu is second

    # The first menu should have been destroyed immediately when the second
    # was opened, even though its own 150ms deferred cleanup has not run yet.
    assert not first.winfo_exists(), "prior active menu was not destroyed"

    _wait_for_deferred_destroy(tk_root)
    assert not second.winfo_exists(), "second menu was not destroyed"
    assert _count_menus(tk_root) <= 1


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_popup_menu_replay_guard_does_not_register_duplicate(menu_window, tk_root):
    """A right-click at the same position within the replay window must
    destroy the duplicate menu and leave the active slot unchanged."""
    menu = tk.Menu(tk_root, tearoff=0)
    menu.add_command(label="Item", command=lambda: None)
    with mock.patch.object(menu, "tk_popup"):
        clip_context.popup_menu(menu_window, menu, 0, 0)
    tk_root.update()
    assert menu_window._active_popup_menu is menu

    duplicate = tk.Menu(tk_root, tearoff=0)
    duplicate.add_command(label="Duplicate", command=lambda: None)
    with mock.patch.object(duplicate, "tk_popup"):
        clip_context.popup_menu(menu_window, duplicate, 0, 0)
    tk_root.update()
    assert menu_window._active_popup_menu is menu, "duplicate replaced active menu"
    assert not duplicate.winfo_exists(), "duplicate menu was not destroyed"

    _wait_for_deferred_destroy(tk_root)


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_destroy_menu_is_still_deferred_for_command_dispatch(menu_window, tk_root):
    """The 150ms deferred destroy must remain so native Windows command
    callbacks are not raced and dropped."""
    menu = tk.Menu(tk_root, tearoff=0)
    menu.add_command(label="Item", command=lambda: None)
    with mock.patch.object(menu, "tk_popup"), \
         mock.patch.object(clip_context, "destroy_menu", wraps=clip_context.destroy_menu) as destroy_mock:
        clip_context.popup_menu(menu_window, menu, 0, 0)
        assert destroy_mock.call_count == 0, "destroy_menu ran synchronously"
        _wait_for_deferred_destroy(tk_root, timeout=0.5)
        destroy_mock.assert_called_once_with(menu)


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_prior_menu_destroyed_does_not_break_later_deferred_cleanup(menu_window, tk_root):
    """If the active-menu replacement destroys a menu before its own deferred
    cleanup fires, the stale deferred cleanup must be a no-op."""
    first = tk.Menu(tk_root, tearoff=0)
    first.add_command(label="First", command=lambda: None)
    with mock.patch.object(first, "tk_popup"):
        clip_context.popup_menu(menu_window, first, 0, 0)
    tk_root.update()

    second = tk.Menu(tk_root, tearoff=0)
    second.add_command(label="Second", command=lambda: None)
    with mock.patch.object(second, "tk_popup"):
        clip_context.popup_menu(menu_window, second, 0, 0)
    tk_root.update()

    # Wait long enough for both deferred cleanup callbacks to fire.
    _wait_for_deferred_destroy(tk_root, timeout=1.0)
    assert not second.winfo_exists()
    assert _count_menus(tk_root) <= 1


@pytest.mark.skipif(not ctk.CTk, reason="CustomTkinter unavailable")
def test_exception_during_tk_popup_still_schedules_cleanup(menu_window, tk_root):
    """If tk_popup raises, the menu must still be destroyed and the active
    reference cleared."""
    menu = tk.Menu(tk_root, tearoff=0)
    menu.add_command(label="Item", command=lambda: None)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    with mock.patch.object(menu, "tk_popup", side_effect=_boom), \
         mock.patch.object(clip_context, "destroy_menu", wraps=clip_context.destroy_menu) as destroy_mock:
        with pytest.raises(RuntimeError):
            clip_context.popup_menu(menu_window, menu, 0, 0)
        assert destroy_mock.call_count == 0, "destroy_menu ran synchronously on exception"
        _wait_for_deferred_destroy(tk_root)
        assert menu_window._active_popup_menu is None, "active reference not cleared on exception"
        destroy_mock.assert_called_once_with(menu)
