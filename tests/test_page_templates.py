"""Tests for unified page templates, structural scaffolds, and state UI components."""

from __future__ import annotations

import ast
import inspect

import customtkinter as ctk
import pytest

from cache_vault import brand
from cache_vault.core import storage as S
from cache_vault.ui.page_scaffold import PageScaffold, LoadingState, EmptyState, ErrorState, UnavailableState
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
