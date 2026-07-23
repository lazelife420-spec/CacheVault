"""Tests for unified page templates, structural scaffolds, and state UI components."""

from __future__ import annotations

import ast
import inspect

import customtkinter as ctk
import pytest

from cache_vault import brand
from cache_vault.core import storage as S
from cache_vault.ui.page_scaffold import (
    PageScaffold, LoadingState, EmptyState, ErrorState, UnavailableState,
    build_clip_empty_state,
)
from cache_vault.ui.page_header import PageHeader
from cache_vault.ui import home_dashboard


@pytest.fixture(scope="module")
def tk_root():
    """Headless Tkinter root fixture."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_page_scaffold_structural_grid(tk_root):
    """Test PageScaffold grid layout rows configuration."""
    # Ensure all child components are instantiated with scaffold as master
    scaffold = PageScaffold(tk_root)
    header = ctk.CTkFrame(scaffold)
    toolbar = ctk.CTkFrame(scaffold)
    content = ctk.CTkFrame(scaffold)
    footer = ctk.CTkFrame(scaffold)

    scaffold.header = header
    scaffold.toolbar = toolbar
    scaffold.content = content
    scaffold.footer = footer

    header.grid(row=0, column=0, sticky="ew")
    toolbar.grid(row=1, column=0, sticky="ew")
    content.grid(row=2, column=0, sticky="nsew")
    footer.grid(row=3, column=0, sticky="ew")
    scaffold.grid_rowconfigure(2, weight=1)

    scaffold.grid(row=0, column=0)
    scaffold.update_idletasks()

    assert scaffold.header == header
    assert scaffold.toolbar == toolbar
    assert scaffold.content == content
    assert scaffold.footer == footer

    assert scaffold.grid_rowconfigure(2)["weight"] == 1


def test_loading_state_renders_skeletons(tk_root):
    """Test LoadingState renders cards skeleton blocks."""
    # Create parent frame first
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    ls = LoadingState(parent)
    ls.grid(row=0, column=0)
    ls.update_idletasks()

    children = ls.winfo_children()
    assert len(children) == 4
    for child in children:
        assert isinstance(child, ctk.CTkFrame)


def test_empty_state_renders_actions(tk_root):
    """Test EmptyState icon, description, and action callbacks."""
    called = []
    actions = [
        ("Action One", lambda: called.append(1), True),
        ("Action Two", lambda: called.append(2), False),
    ]

    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    es = EmptyState(
        parent,
        title="Testing Empty",
        description="Detailed testing description text.",
        icon="⚡",
        actions=actions,
    )
    es.grid(row=0, column=0)
    es.update_idletasks()

    assert es._title_lbl.cget("text") == "Testing Empty"
    assert es._desc_lbl.cget("text") == "Detailed testing description text."
    assert es._icon_lbl.cget("text") == "⚡"

    action_buttons = es._actions_frame.winfo_children()
    assert len(action_buttons) == 2
    assert isinstance(action_buttons[0], ctk.CTkButton)
    assert action_buttons[0].cget("text") == "Action One"

    action_buttons[0].invoke()
    assert called == [1]


def test_error_state_and_unavailable_state(tk_root):
    """Test ErrorState and UnavailableState initialization."""
    called = []
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    err = ErrorState(parent, title="Fatal Error", retry_cmd=lambda: called.append(99))
    err.grid(row=0, column=0)
    err.update_idletasks()
    assert err._title_lbl.cget("text") == "Fatal Error"
    assert isinstance(err._retry_btn, ctk.CTkButton)
    err._retry_btn.invoke()
    assert called == [99]

    unavail = UnavailableState(parent, title="Feature Offline", description="LAN bridge not paired.")
    unavail.grid(row=0, column=0)
    unavail.update_idletasks()
    assert unavail._title_lbl.cget("text") == "Feature Offline"
    assert unavail._desc_lbl.cget("text") == "LAN bridge not paired."


def test_build_clip_empty_state_favorites(tk_root):
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(parent, active_filter=S.FILTER_FAVORITES)
    est.grid(row=0, column=0)
    est.update_idletasks()
    assert est._title_lbl.cget("text") == "No Favorites"
    assert est._icon_lbl.cget("text") == "★"
    assert est._desc_lbl.cget("text") == "Star clips to save them here."
    assert not hasattr(est, "_actions_frame")


def test_build_clip_empty_state_recently_removed(tk_root):
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(parent, active_filter=S.FILTER_RECENTLY_REMOVED)
    est.grid(row=0, column=0)
    est.update_idletasks()
    assert est._title_lbl.cget("text") == "No Recently Removed"
    assert est._icon_lbl.cget("text") == "↩"
    assert est._desc_lbl.cget("text") == "Clean trash bin."


def test_build_clip_empty_state_duplicates_screenshots_sensitive(tk_root):
    cases = [
        (S.FILTER_DUPLICATES, "No Duplicates", "≡", "Everything looks clean."),
        (S.FILTER_SCREENSHOTS, "No Screenshots", "▦", "Screenshots will appear here."),
        (S.FILTER_SENSITIVE, "No Sensitive Items", "⚠", "Sensitive clips will appear here."),
    ]
    for active_filter, title, icon, desc in cases:
        parent = ctk.CTkFrame(tk_root)
        parent.grid(row=0, column=0)
        est = build_clip_empty_state(parent, active_filter=active_filter)
        est.grid(row=0, column=0)
        est.update_idletasks()
        assert est._title_lbl.cget("text") == title
        assert est._icon_lbl.cget("text") == icon
        assert est._desc_lbl.cget("text") == desc
        est.destroy()
        parent.destroy()


def test_build_clip_empty_state_collection_has_bespoke_state_no_actions(tk_root):
    """A Collection screen must get its own real empty state, not the
    generic 'no clips match filters' fallback, and must not offer
    Clear Filters / Save Clipboard actions that don't apply to it."""
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(
        parent,
        active_filter=S.COLLECTION_PREFIX + "My Collection",
        clear_filters=lambda: None,
        save_clipboard=lambda: None,
    )
    est.grid(row=0, column=0)
    est.update_idletasks()
    assert est._title_lbl.cget("text") == "This collection is empty"
    assert est._desc_lbl.cget("text") == "Add clips to this collection from a clip's context menu."
    assert not hasattr(est, "_actions_frame")


def test_build_clip_empty_state_generic_fallback_attaches_actions_when_available(tk_root):
    called = []
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(
        parent,
        active_filter=S.FILTER_ALL,
        clear_filters=lambda: called.append("clear"),
        save_clipboard=lambda: called.append("save"),
    )
    est.grid(row=0, column=0)
    est.update_idletasks()
    assert est._title_lbl.cget("text") == "No clips match filters"
    buttons = est._actions_frame.winfo_children()
    assert [b.cget("text") for b in buttons] == ["Clear Filters", "Save Clipboard"]
    buttons[0].invoke()
    buttons[1].invoke()
    assert called == ["clear", "save"]


def test_build_clip_empty_state_generic_fallback_no_actions_when_callbacks_missing(tk_root):
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(parent, active_filter=S.FILTER_ALL)
    est.grid(row=0, column=0)
    est.update_idletasks()
    assert est._title_lbl.cget("text") == "No clips match filters"
    assert not hasattr(est, "_actions_frame")


def test_build_clip_empty_state_uses_empty_message_when_no_filter_matches(tk_root):
    parent = ctk.CTkFrame(tk_root)
    parent.grid(row=0, column=0)
    est = build_clip_empty_state(
        parent, active_filter="", empty_message="Nothing captured yet in this vault.",
    )
    est.grid(row=0, column=0)
    est.update_idletasks()
    # No structured filter/collection key matched, so this falls to the
    # generic branch, which always overwrites desc -- matching the
    # pre-existing behavior this refactor preserves rather than changes.
    assert est._title_lbl.cget("text") == "No clips match filters"


def test_home_dashboard_no_duplicate_method_definitions():
    """Regression guard: a prior bad merge left a second, broken `render`/
    `set_selected` pair ahead of the live ones in HomeDashboard — Python
    silently keeps only the last definition, which built an orphaned,
    unpacked frame and left the page's content effectively blank. A
    duplicate method name in this class means the same defect crept back."""
    source = inspect.getsource(home_dashboard)
    tree = ast.parse(source)
    class_node = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "HomeDashboard"
    )
    method_names = [
        node.name for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    duplicates = {name for name in method_names if method_names.count(name) > 1}
    assert not duplicates, f"Duplicate method definitions in HomeDashboard: {duplicates}"
