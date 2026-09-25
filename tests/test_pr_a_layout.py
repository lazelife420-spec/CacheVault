import pytest
import customtkinter as ctk
from unittest.mock import call, patch
from cache_vault import brand
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
from tests.tk_support import wait_for_refresh
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


# Matches the header title's own font size (page_header.py sets 24pt bold).
# Body content routinely reuses a page's name as a small-font status-table
# field label (e.g. Mobile Access's device-status row "Mobile Access: On") —
# that's legitimate data, not a duplicated heading, so only a heading-sized
# label re-stating the title counts as a violation.
_HEADING_FONT_SIZE_THRESHOLD = 18


def _heading_sized_label_texts(widget) -> list[str]:
    """Recursively collect text from CTkLabel descendants whose font size is
    heading-sized, so small-font status/table labels that happen to reuse a
    page's name aren't mistaken for a duplicated page title."""
    texts = []
    if isinstance(widget, ctk.CTkLabel):
        try:
            font = widget.cget("font")
            size = abs(font.cget("size")) if hasattr(font, "cget") else 0
            if size >= _HEADING_FONT_SIZE_THRESHOLD:
                texts.append(widget.cget("text"))
        except Exception:  # noqa: BLE001
            pass
    for child in widget.winfo_children():
        texts.extend(_heading_sized_label_texts(child))
    return texts


def _bounds(widget):
    x = widget.winfo_rootx()
    return x, x + widget.winfo_width()


def _assert_fully_visible(child, parent, label, size_label):
    """winfo_ismapped() alone doesn't prove a control is usable -- Tk keeps
    "managing" a child even after it's been positioned past its own
    parent's boundary, and the OS then clips it there silently. This
    checks actual bounds: the child must sit entirely within its parent's
    rendered rectangle, not just be nominally mapped."""
    child_left, child_right = _bounds(child)
    parent_left, parent_right = _bounds(parent)
    visible_width = max(0, min(child_right, parent_right) - max(child_left, parent_left))
    assert child_left >= parent_left, (
        f"{label} left edge ({child_left}) is left of its parent's left edge "
        f"({parent_left}) at {size_label}"
    )
    assert child_right <= parent_right, (
        f"{label} right edge ({child_right}) extends past its parent's right edge "
        f"({parent_right}) at {size_label} -- clipped by {child_right - parent_right}px"
    )
    assert visible_width == child.winfo_width(), (
        f"{label} is only partially visible at {size_label}: "
        f"{visible_width}px visible of {child.winfo_width()}px"
    )


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


def test_home_uses_its_header_and_reclaims_hidden_toolbar_row(app):
    app._navigate_filter(FILTER_HOME)
    app._do_refresh_sync()
    wait_for_refresh(app)

    header_info = app._page_header.grid_info()
    home_info = app._home.grid_info()
    assert app._page_header._title_label.cget("text") == "Home"
    assert header_info["row"] == 0
    assert home_info["row"] == 1
    assert home_info["rowspan"] == 2
    assert not app._toolbar.grid_info()

    app._navigate_filter(FILTER_ALL)
    app._do_refresh_sync()
    wait_for_refresh(app)
    assert app._page_header.grid_info()["row"] == 0
    assert app._toolbar.grid_info()["row"] == 1

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


def test_empty_page_header_regions_do_not_create_vertical_canvas(app):
    app._page_header.set_content("Home")
    app._page_header.set_actions()
    app._page_header.set_status_chips([])
    app.update_idletasks()

    assert app._page_header.winfo_reqheight() < 100

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
    """The page content area must not re-render the same title as a second
    heading-sized label — small-font status/table fields that happen to
    reuse a page's name (e.g. Mobile Access's "Mobile Access: On" status
    row) are legitimate data, not a duplicated heading."""
    for key in (FILTER_HOME, NAV_HOTKEY_ACTIONS, NAV_EDITABLE_COPIES, NAV_MOBILE_ACCESS):
        app._navigate_screen(key)
        app._do_refresh_sync()  # header title / page routing is debounced via refresh()
        wait_for_refresh(app)
        title = app._page_header._title_label.cget("text")
        if key == FILTER_HOME:
            content_widget = app._home
        else:
            content_widget = app._vault_screens._screens[key]
        heading_texts = _heading_sized_label_texts(content_widget)
        assert title not in heading_texts, (
            f"Page {key!r} repeats header title {title!r} as a heading-sized label in its own body"
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
        wait_for_refresh(app)
        assert app._filters.active == key
        assert app._vault_screens.grid_info() == {}
        assert app._home.grid_info() == {}
        assert app._toolbar.grid_info(), f"Shared toolbar should be visible for {key!r}"
        view = app._grid if app._view_mode == "grid" else app._list
        assert view.grid_info(), f"Shared clip view should be visible for {key!r}"


def test_top_bar_hierarchy_stays_consistent_at_every_width(app):
    """The top bar's hierarchy is now steady-state: control strip (vault/
    capture state) -> Quick Paste (the one dominant action) -> "More"
    overflow -> Settings. Export, Stamped Receipts, and Capture Rules live
    in the overflow at every width, so narrowing the window never moves
    top-bar controls -- only the control strip's own density folds."""
    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
    app.update_idletasks()
    assert not app._view_label.winfo_ismapped(), "View: label should collapse at compact width"
    assert not app._selection_hint_label.winfo_ismapped(), "Selection hint should collapse at compact width"
    assert not app._control_strip._safe.winfo_ismapped(), "Default Safe label should collapse at compact width"
    assert not app._control_strip._quick.winfo_ismapped(), "Quick Actions dropdown should collapse at compact width"
    # The overflow and the dominant action are always reachable.
    assert app._top_more_btn.winfo_ismapped(), "More overflow must stay visible at compact width"
    assert app._top_quick_paste_btn.winfo_ismapped(), "Quick Paste must stay visible at compact width"
    assert app._control_strip._lock_btn.cget("text") == "Lock", (
        "Lock Now should shorten to 'Lock' at compact width, but stay a distinct, reachable button"
    )
    assert app._control_strip._lock_btn.winfo_ismapped(), "Lock button must stay reachable at compact width"

    with patch.object(app, 'winfo_width', return_value=1600):
        app._handle_resize_debounced()
    app.update_idletasks()
    assert app._view_label.winfo_ismapped(), "View: label should return at wide width"
    assert app._selection_hint_label.winfo_ismapped(), "Selection hint should return at wide width"
    assert app._control_strip._safe.winfo_ismapped(), "Default Safe label should return at wide width"
    assert app._control_strip._quick.winfo_ismapped(), "Quick Actions dropdown should return at wide width"
    assert app._top_more_btn.winfo_ismapped(), "More overflow is a permanent control, not a compact-only one"
    assert app._top_quick_paste_btn.winfo_ismapped(), "Quick Paste must stay visible at wide width"
    assert app._control_strip._lock_btn.cget("text") == "Lock Now", (
        "Lock label should revert to 'Lock Now' at wide width"
    )


def test_toolbar_overflow_menu_invokes_original_handlers(app):
    """The "More" menu must call the exact same handlers as the controls it
    replaced -- Export, Stamped Receipts, Capture Rules at every width,
    plus the Quick Actions dropdown's own choices while that dropdown is
    collapsed at non-wide widths. This is an access path, not a different
    feature."""
    with patch.object(app, 'winfo_width', return_value=950):
        app._handle_resize_debounced()
    app.update_idletasks()

    captured_menu = {}

    def _fake_popup(window, menu, x, y):
        captured_menu["menu"] = menu

    with patch("cache_vault.ui.shell.clip_context.popup_menu", side_effect=_fake_popup), \
         patch.object(app, "_export_view") as export_mock, \
         patch.object(app, "_navigate_screen") as nav_mock, \
         patch.object(app, "_open_regex_macros") as macros_mock, \
         patch.object(app._control_strip, "invoke_quick_action") as quick_mock:
        app._open_top_overflow_menu()
        menu = captured_menu["menu"]
        choices = app._control_strip.QUICK_ACTION_CHOICES
        assert menu.index("end") == 3 + len(choices), (
            "Overflow menu should offer Export, Stamped Receipts, Capture "
            "Rules, a separator, and every Quick Actions choice"
        )
        assert menu.type(3) == "separator", "A separator should divide the two action groups"

        menu.invoke(0)
        export_mock.assert_called_once()

        menu.invoke(1)
        nav_mock.assert_called_once()
        from cache_vault.ui.filters import NAV_STAMPED_RECEIPTS
        assert nav_mock.call_args[0][0] == NAV_STAMPED_RECEIPTS

        menu.invoke(2)
        macros_mock.assert_called_once()

        for offset, choice in enumerate(choices):
            menu.invoke(4 + offset)
        # assert_has_calls inspects mock_calls, which also records calls
        # made on a mock's *return value* (Tk's command dispatch stringifies
        # each callback's result); call_args_list only reflects direct
        # invocations of the mock itself, so it's the correct comparison.
        assert quick_mock.call_args_list == [call(c) for c in choices]
    menu.destroy()


def test_control_strip_lock_and_quick_actions_stay_reachable_at_every_width(app):
    """Regression test for a real defect found during the Slice 2 visual
    pass: winfo_ismapped() was insufficient to prove a control is usable --
    a widget Tk still "manages" can be positioned past its own parent
    frame's boundary and get silently clipped there, invisibly, since
    Tk doesn't shrink a frame's children to fit when the frame itself gets
    squeezed by its own parent's grid. At compact and standard widths,
    VaultControlStrip's full content (Capture/Mobile/Receipts dropdowns +
    Default Safe + Lock + Quick Actions) doesn't fit even after Default
    Safe is hidden -- Quick Actions (and, at these widths, Stamped
    Receipts / Capture Rules) move into the "More" overflow, and Lock
    must remain directly visible and fully within VaultControlStrip's
    bounds at every one of these widths, never reduced to a clipped
    sliver."""
    app._navigate_screen(FILTER_ALL)
    cs = app._control_strip

    for geometry, expected_mode in (
        ("900x600", "compact"),
        ("1000x650", "standard"),
        ("1100x700", "standard"),
        ("1600x900", "wide"),
    ):
        app.geometry(geometry)
        app.update()
        if app._resize_job:
            app.after_cancel(app._resize_job)
            app._resize_job = None
        app._handle_resize_debounced()
        app.update()
        assert app._current_layout_mode == expected_mode, (
            f"Expected {expected_mode!r} mode at {geometry}, got {app._current_layout_mode!r}"
        )

        # Always-direct controls: fully bounds-checked at every width, not
        # just "mapped" -- a mapped widget can still be clipped by its
        # parent's actual rendered boundary.
        for widget, label in (
            (cs._capture, "Capture dropdown"),
            (cs._mobile, "Mobile dropdown"),
            (cs._receipts, "Receipts dropdown"),
            (cs._lock_btn, "Lock button"),
        ):
            assert widget.winfo_ismapped(), f"{label} must be mapped at {geometry}"
            _assert_fully_visible(widget, cs, label, geometry)

        if expected_mode == "wide":
            for widget, label in (
                (cs._safe, "Default Safe label"),
                (cs._quick, "Quick Actions dropdown"),
                (app._top_quick_paste_btn, "Quick Paste button"),
                (app._top_more_btn, "More button"),
            ):
                assert widget.winfo_ismapped(), f"{label} must be mapped at {geometry}"
                _assert_fully_visible(widget, widget.master, label, geometry)
            continue

        # Overflowed at compact/standard: the control strip's own density
        # folds (Default Safe label, Quick Actions dropdown), but the top
        # bar's steady-state controls never move -- Quick Paste, More, and
        # Settings stay mapped and fully inside the top bar at every width.
        assert not cs._safe.winfo_ismapped(), f"Default Safe should be hidden at {geometry}"
        assert not cs._quick.winfo_ismapped(), (
            f"Quick Actions dropdown must be intentionally removed (not left "
            f"mapped-but-clipped) at {geometry}"
        )
        for widget, label in (
            (app._top_quick_paste_btn, "Quick Paste button"),
            (app._top_more_btn, "More button"),
        ):
            assert widget.winfo_ismapped(), f"{label} must be reachable at {geometry}"
            _assert_fully_visible(widget, widget.master, label, geometry)

        captured_menu = {}

        def _fake_popup(window, menu, x, y):
            captured_menu["menu"] = menu

        with patch("cache_vault.ui.shell.clip_context.popup_menu", side_effect=_fake_popup), \
             patch.object(app, "_export_view") as export_mock, \
             patch.object(app, "_navigate_screen") as nav_mock, \
             patch.object(app, "_open_regex_macros") as macros_mock, \
             patch.object(cs, "invoke_quick_action") as quick_mock:
            app._open_top_overflow_menu()
            menu = captured_menu["menu"]
            choices = cs.QUICK_ACTION_CHOICES

            assert menu.entrycget(0, "label") == brand.TERM_EXPORT
            assert menu.entrycget(1, "label") == brand.TERM_STAMPED_RECEIPTS
            assert menu.entrycget(2, "label") == "Capture Rules"
            assert menu.type(3) == "separator"
            for offset, choice in enumerate(choices):
                assert menu.entrycget(4 + offset, "label") == choice, (
                    f"More menu must offer the Quick Actions choice {choice!r} at {geometry}"
                )

            menu.invoke(0)
            export_mock.assert_called_once()

            menu.invoke(1)
            from cache_vault.ui.filters import NAV_STAMPED_RECEIPTS
            nav_mock.assert_called_once_with(NAV_STAMPED_RECEIPTS)

            menu.invoke(2)
            macros_mock.assert_called_once()

            for offset in range(len(choices)):
                menu.invoke(4 + offset)
            # call_args_list (not mock_calls / assert_has_calls) -- Tk's
            # command dispatch stringifies each callback's return value,
            # which otherwise shows up as spurious call().__str__() entries.
            assert quick_mock.call_args_list == [call(c) for c in choices]
        menu.destroy()


def test_default_safe_label_hidden_in_standard_mode_too_not_just_compact(app):
    """Regression test for a real steady-state defect found during the
    Slice 2 visual pass: VaultControlStrip's own content (Capture/Mobile/
    Receipts dropdowns + Default Safe label + Lock + Quick Actions),
    combined with the outer top bar's fixed-width buttons, doesn't
    actually fit in "standard" mode (1150-1499px) -- only "compact" mode
    previously dropped the Default Safe label, so at e.g. 1100px width
    the label rendered visually clipped mid-word ("Default Safe: default"
    -> "D..."). Verified via real window geometry (not a mocked
    winfo_width) that this no longer happens and nothing overlaps."""
    app._navigate_screen(FILTER_ALL)
    for geometry, expected_mode in (("1600x900", "wide"), ("1100x700", "standard"), ("900x600", "compact")):
        app.geometry(geometry)
        app.update()
        if app._resize_job:
            app.after_cancel(app._resize_job)
            app._resize_job = None
        app._handle_resize_debounced()
        app.update()
        assert app._current_layout_mode == expected_mode, (
            f"Expected {expected_mode!r} mode at {geometry}, got {app._current_layout_mode!r}"
        )
        safe = app._control_strip._safe
        if expected_mode == "wide":
            assert safe.winfo_ismapped(), "Default Safe label should be visible in wide mode"
        else:
            assert not safe.winfo_ismapped(), (
                f"Default Safe label must be hidden in {expected_mode!r} mode, not just 'compact'"
            )


def test_view_toggle_controls_keep_minimum_right_inset_at_every_supported_width(app):
    """Cards/Grid must never sit flush against (or past) the toolbar's
    right edge -- headroom, not a fix for observed clipping (none exists
    at any currently supported width; this asserts the margin explicitly
    so a future change can't silently erode it back to zero).

    Uses real window geometry (not a mocked winfo_width) -- mocking only
    drives the layout-mode branch, it doesn't move any actual widget, so
    a pixel-bounds assertion needs the real window genuinely resized.
    """
    app._navigate_screen(FILTER_ALL)
    MIN_INSET = 8  # logical px; deliberately looser than the ~21px measured
                   # after the fix, so this doesn't become pixel-brittle.
    for geometry in ("900x600", "1000x650", "1100x700", "1600x900"):
        app.geometry(geometry)
        app.update()
        if app._resize_job:
            app.after_cancel(app._resize_job)
            app._resize_job = None
        app._handle_resize_debounced()
        app.update()

        assert app._grid_btn.winfo_ismapped(), f"Grid must stay visible at {geometry}"
        assert app._cards_btn.winfo_ismapped(), f"Cards must stay visible at {geometry}"
        toolbar_right = app._toolbar.winfo_rootx() + app._toolbar.winfo_width()
        grid_right = app._grid_btn.winfo_rootx() + app._grid_btn.winfo_width()
        assert grid_right <= toolbar_right, (
            f"Grid button must not extend past the toolbar boundary at {geometry}"
        )
        margin = toolbar_right - grid_right
        assert margin >= MIN_INSET, (
            f"Grid button right edge too close to toolbar boundary at {geometry}: "
            f"margin={margin}px, required >= {MIN_INSET}px"
        )


def test_bulk_action_strip_stays_within_toolbar_bounds_at_minimum_width(app):
    """Verified via real measurement (not screenshots) that a genuine
    2-item selection's bulk-action strip stays fully inside the toolbar at
    the narrowest supported width (900x600) -- confirming no change is
    needed here, and guarding against future regression."""
    app.vault.storage.add_clip(Clip(id="bulk_strip_1", content="first", content_type=CONTENT_TEXT))
    app.vault.storage.add_clip(Clip(id="bulk_strip_2", content="second", content_type=CONTENT_TEXT))
    app._navigate_screen(FILTER_ALL)
    app._do_refresh_sync()
    wait_for_refresh(app)

    app.geometry("900x600")
    app.update()
    if app._resize_job:
        app.after_cancel(app._resize_job)
        app._resize_job = None
    app._handle_resize_debounced()
    app.update()

    app._clear_selection()
    ids = app._visible_clip_ids[:2]
    assert len(ids) == 2, "Test fixture needs at least 2 visible clips"
    for cid in ids:
        app._list._toggle_select(app.vault.storage.get_clip(cid))
    app.update()

    assert app._selected_action_frame.winfo_ismapped()
    toolbar_right = app._toolbar.winfo_rootx() + app._toolbar.winfo_width()
    for btn in app._selected_action_buttons:
        btn_right = btn.winfo_rootx() + btn.winfo_width()
        assert btn_right <= toolbar_right, (
            f"Bulk-strip button {btn.cget('text')!r} extends past the toolbar "
            f"boundary at 900x600 ({btn_right} > {toolbar_right})"
        )


def test_repeated_navigation_does_not_duplicate_widgets(app):
    initial_screen_count = len(app._vault_screens._screens)
    initial_center_children = len(app._center.winfo_children())

    for _ in range(3):
        for key in EIGHT_PAGES:
            app._navigate_screen(key)

    assert len(app._vault_screens._screens) == initial_screen_count
    assert len(app._center.winfo_children()) == initial_center_children
