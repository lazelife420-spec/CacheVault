import pytest
import customtkinter as ctk
from unittest.mock import patch
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.ui.page_header import PageHeader
from cache_vault.ui.filters import (
    NAV_EDITABLE_COPIES,
    NAV_HOTKEY_ACTIONS,
    NAV_MOBILE_ACCESS,
    NAV_SCREEN_KEYS,
)
from cache_vault.core.storage import FILTER_ALL, FILTER_HOME, FILTER_OLDER, FILTER_TODAY, FILTER_WEEK
from cache_vault.core.models import Clip, CONTENT_TEXT
import tkinter as tk

# The eight pages covered by the A3 corrective pass.
EIGHT_PAGES = [
    FILTER_HOME,
    FILTER_ALL,
    NAV_HOTKEY_ACTIONS,
    NAV_EDITABLE_COPIES,
    FILTER_TODAY,
    FILTER_WEEK,
    FILTER_OLDER,
    NAV_MOBILE_ACCESS,
]


def _label_texts(widget) -> list[str]:
    """Recursively collect text from CTkLabel descendants of *widget*."""
    texts = []
    if isinstance(widget, ctk.CTkLabel):
        try:
            texts.append(widget.cget("text"))
        except Exception:  # noqa: BLE001
            pass
    for child in widget.winfo_children():
        texts.extend(_label_texts(child))
    return texts


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

def test_header_subtitle_wraps_independent_of_title_width(app):
    """The subtitle must sit on its own row below the title, not share a
    row with it — otherwise a long title leaves the subtitle too little
    room and it clips past the window edge instead of wrapping."""
    header = app._page_header
    header.set_content(
        "Editable Copies / Revisions",
        "Original protected · Editable copy · Local-first",
    )
    app.update_idletasks()
    title_info = header._title_label.grid_info()
    subtitle_info = header._subtitle_label.grid_info()
    assert title_info["row"] != subtitle_info["row"], (
        "Title and subtitle must not share a grid row"
    )
    assert int(header._subtitle_label.cget("wraplength")) <= 560

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

def test_inspector_hidden_with_no_selection(app):
    """A clip page with nothing selected shows no docked inspector at all —
    not even the old always-on Vault Control fallback on Command Center."""
    with patch.object(app, 'winfo_width', return_value=1200):
        app._handle_resize_debounced()
    assert not app._preview.grid_info()
    assert app.grid_columnconfigure(2)["minsize"] == 0


def test_inspector_docked_in_wide_standard(app):
    clip = Clip(id="test_docked", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)

    with patch.object(app, 'winfo_width', return_value=1200):
        app._handle_resize_debounced()
        app._on_clip_select(clip)
        info = app._preview.grid_info()
        assert info, "Preview should be gridded in standard mode once a clip is selected"
        assert info["row"] == 1
        assert info["column"] == 2
        assert app.grid_columnconfigure(2)["minsize"] == 320

    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
        app._on_clip_select(clip)
        info = app._preview.grid_info()
        assert info, "Preview should be gridded in wide mode once a clip is selected"
        assert info["row"] == 1
        assert info["column"] == 2
        assert app.grid_columnconfigure(2)["minsize"] == 400

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


# --- A3 corrective-pass regression coverage --------------------------------

def test_identical_header_y_position_across_all_eight_pages(app):
    """All eight pages share a single PageHeader instance gridded at the same
    row of _center — its position cannot drift per page."""
    for key in EIGHT_PAGES:
        app._navigate_screen(key)
        info = app._page_header.grid_info()
        assert info, f"Header should be gridded while on {key!r}"
        assert info["row"] == 0
        assert info["column"] == 0


def test_only_content_row_has_expansion_weight(app):
    """Header/toolbar rows are fixed height; only the content row expands."""
    assert app._center.grid_rowconfigure(0)["weight"] == 0  # header
    assert app._center.grid_rowconfigure(1)["weight"] == 0  # toolbar
    assert app._center.grid_rowconfigure(2)["weight"] == 1  # content


def test_no_repeated_in_body_page_title(app):
    """The page content area must not re-render the same title text already
    shown in the shared PageHeader."""
    for key in (FILTER_HOME, NAV_HOTKEY_ACTIONS, NAV_EDITABLE_COPIES, NAV_MOBILE_ACCESS):
        app._navigate_screen(key)
        app._do_refresh_sync()  # header title / page routing is debounced via refresh()
        title = app._page_header._title_label.cget("text")
        if key == FILTER_HOME:
            content_widget = app._home
        else:
            content_widget = app._vault_screens._screens[key]
        body_texts = _label_texts(content_widget)
        assert title not in body_texts, (
            f"Page {key!r} repeats header title {title!r} in its own body"
        )


def test_hotkey_actions_hides_inspector(app):
    clip = Clip(id="test_hotkey_inspector", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)
    app._on_clip_select(clip)  # select while on a clip page first

    app._navigate_screen(NAV_HOTKEY_ACTIONS)
    assert app._selected_clip_id is None
    assert not app._preview.grid_info()
    assert not app._preview.place_info()
    assert app.grid_columnconfigure(2)["minsize"] == 0


def test_mobile_access_hides_inspector(app):
    clip = Clip(id="test_mobile_inspector", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)
    app._on_clip_select(clip)

    app._navigate_screen(NAV_MOBILE_ACCESS)
    assert app._selected_clip_id is None
    assert not app._preview.grid_info()
    assert not app._preview.place_info()
    assert app.grid_columnconfigure(2)["minsize"] == 0


def test_editable_copies_hides_inspector_until_revision_selected(app):
    clip = Clip(id="test_revision_clip", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)

    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
        app._navigate_screen(NAV_EDITABLE_COPIES)
        assert not app._preview.grid_info(), "Inspector must stay hidden with no revision selected"
        assert app.grid_columnconfigure(2)["minsize"] == 0

        # Explicitly selecting a revision's original clip shows the inspector
        # in place, without leaving the Editable Copies page.
        app._select_visible_clip_by_id(clip.id)
        assert app._filters.active == NAV_EDITABLE_COPIES, "selection must not navigate away"
        info = app._preview.grid_info()
        assert info, "Inspector should dock once a revision is explicitly selected"
        assert app.grid_columnconfigure(2)["minsize"] == 400


def test_navigation_to_non_clip_page_closes_docked_inspector(app):
    clip = Clip(id="test_close_docked", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)

    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
        app._on_clip_select(clip)
        assert app._preview.grid_info()

        app._navigate_screen(NAV_HOTKEY_ACTIONS)
        assert app._selected_clip_id is None
        assert not app._preview.grid_info()
        assert app.grid_columnconfigure(2)["minsize"] == 0


def test_compact_non_clip_page_closes_slideover(app):
    clip = Clip(id="test_close_slideover", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)

    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
        app._on_clip_select(clip)
        assert app._preview.place_info(), "Slide-over should be open before navigating away"

        app._navigate_screen(NAV_MOBILE_ACCESS)
        assert not app._preview.place_info(), "Slide-over must close on non-clip pages"
        assert not app._preview.grid_info()


def test_returning_to_all_clips_allows_slideover_again(app):
    clip = Clip(id="test_reopen_slideover", content="hello", content_type=CONTENT_TEXT)
    app.vault.storage.add_clip(clip)

    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
        app._navigate_screen(NAV_HOTKEY_ACTIONS)
        assert not app._preview.place_info()

        app._navigate_screen(FILTER_ALL)
        app._on_clip_select(clip)
        assert app._preview.place_info(), "Slide-over should be able to reopen on All Clips"


def test_today_week_older_share_clip_page_template(app):
    """Today/This Week/Older route through the exact same clip list/grid and
    toolbar widgets as All Clips — only the query filter differs."""
    for key in (FILTER_ALL, FILTER_TODAY, FILTER_WEEK, FILTER_OLDER):
        app._navigate_screen(key)
        app._do_refresh_sync()  # page widget swap (_show_clips) is debounced via refresh()
        assert app._filters.active == key
        assert app._vault_screens.grid_info() == {}
        assert app._home.grid_info() == {}
        assert app._toolbar.grid_info(), f"Shared toolbar should be visible for {key!r}"
        view = app._grid if app._view_mode == "grid" else app._list
        assert view.grid_info(), f"Shared clip view should be visible for {key!r}"


def test_toolbar_overflow_at_compact_width(app):
    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
    app.update_idletasks()
    assert not app._view_label.winfo_ismapped(), "View: label should collapse at compact width"
    assert not app._selection_hint_label.winfo_ismapped(), "Selection hint should collapse at compact width"
    assert not app._top_receipts_btn.winfo_ismapped(), "Top Stamped Receipts button should collapse at compact width"
    assert not app._top_capture_rules_btn.winfo_ismapped(), "Top Capture Rules button should collapse at compact width"
    assert not app._control_strip._safe.winfo_ismapped(), "Default Safe label should collapse at compact width"

    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
    app.update_idletasks()
    assert app._view_label.winfo_ismapped(), "View: label should return at wide width"
    assert app._selection_hint_label.winfo_ismapped(), "Selection hint should return at wide width"
    assert app._top_receipts_btn.winfo_ismapped(), "Top Stamped Receipts button should return at wide width"
    assert app._top_capture_rules_btn.winfo_ismapped(), "Top Capture Rules button should return at wide width"
    assert app._control_strip._safe.winfo_ismapped(), "Default Safe label should return at wide width"


def test_repeated_navigation_does_not_duplicate_widgets(app):
    initial_screen_count = len(app._vault_screens._screens)
    initial_center_children = len(app._center.winfo_children())

    for _ in range(3):
        for key in EIGHT_PAGES:
            app._navigate_screen(key)

    assert len(app._vault_screens._screens) == initial_screen_count
    assert len(app._center.winfo_children()) == initial_center_children
