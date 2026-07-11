import pytest
import customtkinter as ctk
from unittest.mock import patch
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.ui.page_header import PageHeader
from cache_vault.core.models import Clip, CONTENT_TEXT
import tkinter as tk

@pytest.fixture
def app(tk_root, vault):
    app = CacheVaultApp(vault=vault)
    yield app
    app.destroy()

def test_breakpoint_resolution(app):
    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
        assert getattr(app, "_current_layout_mode", None) == "wide"

    with patch.object(app, 'winfo_width', return_value=1200):
        app._handle_resize_debounced()
        assert getattr(app, "_current_layout_mode", None) == "standard"

    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
        assert getattr(app, "_current_layout_mode", None) == "compact"

def test_page_header_renders(app):
    header = app._page_header
    assert isinstance(header, PageHeader)
    assert header.winfo_exists()
    
    app._page_header.set_content("Test Title", "Test Subtitle")
    app.update_idletasks()
    assert header._title_label.cget("text") == "Test Title"

def test_navigation_clears_stale_selection(app):
    clip = Clip(id="test_1", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)
    app.refresh()
    
    app._on_clip_select(clip)
    assert app._selected_clip_id == clip.id
    assert app._preview._clip.id == clip.id
    
    # Navigate away
    app._on_filter_select("Screenshots", record_history=True)
    assert app._selected_clip_id is None
    assert app._preview._clip is None

def test_inspector_docked_in_wide_standard(app):
    with patch.object(app, 'winfo_width', return_value=1200):
        app._handle_resize_debounced()
        info = app._preview.grid_info()
        assert info, "Preview should be gridded in standard mode"
        assert info["row"] == 1
        assert info["column"] == 2
    
    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
        info = app._preview.grid_info()
        assert info, "Preview should be gridded in wide mode"
        assert info["row"] == 1
        assert info["column"] == 2

def test_inspector_slideover_in_compact(app):
    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
        grid_info = app._preview.grid_info()
        assert not grid_info, "Preview should not be gridded in compact mode"
        
        clip = Clip(id="test_2", content="hello", content_type=CONTENT_TEXT)
        app.vault.storage.add_clip(clip)
    app.refresh()
    
    app._on_clip_select(clip)
    place_info = app._preview.place_info()
    assert place_info, "Preview should be placed (slide-over) when selected in compact mode"

def test_compact_inspector_close_button(app):
    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
        clip = Clip(id="test_3", content="hello", content_type=CONTENT_TEXT)
        app.vault.storage.add_clip(clip)
    app.refresh()
    
    app._on_clip_select(clip)
    assert app._selected_clip_id == clip.id
    
    # Simulate close button click
    app._close_inspector()
    assert app._selected_clip_id is None
    assert app._preview._clip is None
    assert not app._preview.place_info(), "Preview should be hidden after closing"

def test_repeated_resize_does_not_duplicate(app):
    # Just ensure no errors and children count doesn't explode
    initial_children = len(app.winfo_children())
    for _ in range(5):
        with patch.object(app, 'winfo_width', return_value=950):
            app._handle_resize_debounced()
        with patch.object(app, 'winfo_width', return_value=1600):
            app._handle_resize_debounced()
    
    assert len(app.winfo_children()) <= initial_children + 5
