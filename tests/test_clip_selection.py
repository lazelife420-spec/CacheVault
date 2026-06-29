from __future__ import annotations

from types import SimpleNamespace
import inspect

from cache_vault import brand
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.clip_list import ClipList


class FakeWidget:
    def __init__(self):
        self.configured: list[dict] = []

    def configure(self, **kwargs) -> None:
        self.configured.append(kwargs)

    def winfo_rootx(self) -> int:
        return 10

    def winfo_rooty(self) -> int:
        return 20

    def winfo_height(self) -> int:
        return 32


def _clip(clip_id: str):
    return SimpleNamespace(id=clip_id)


def test_clip_list_select_repaints_previous_and_current_rows():
    selected = []
    view = object.__new__(ClipList)
    view._selected_id = "old"
    view._row_by_id = {"old": FakeWidget(), "new": FakeWidget()}
    view._on_select = selected.append

    view._select(_clip("new"))

    assert view._row_by_id["old"].configured[-1]["fg_color"] == brand.ROW_BG
    assert view._row_by_id["new"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG
    assert selected[-1].id == "new"


def test_clip_list_right_click_selects_before_opening_context_menu():
    calls = []
    view = object.__new__(ClipList)
    view._selected_id = None
    view._row_by_id = {"clip-1": FakeWidget()}
    view._on_select = lambda clip: calls.append(("select", clip.id))
    view._on_context = lambda clip, x, y: calls.append(("context", clip.id, x, y))
    event = SimpleNamespace(x_root=10, y_root=20)

    view._context(event, _clip("clip-1"))

    assert calls == [("select", "clip-1"), ("context", "clip-1", 10, 20)]
    assert view._row_by_id["clip-1"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG


def test_clip_grid_select_repaints_row_and_name_label():
    selected = []
    view = object.__new__(ClipGrid)
    view._selected_id = "old"
    view._row_by_id = {"old": FakeWidget(), "new": FakeWidget()}
    view._name_label_by_id = {"old": FakeWidget(), "new": FakeWidget()}
    view._on_select = selected.append

    view._select(_clip("new"))

    assert view._row_by_id["old"].configured[-1]["fg_color"] == brand.ROW_BG
    assert view._row_by_id["new"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG
    assert view._name_label_by_id["old"].configured[-1]["text_color"] == brand.MUTED_FG
    assert view._name_label_by_id["new"].configured[-1]["text_color"] == brand.PROOF_TEAL
    assert selected[-1].id == "new"


def test_clip_grid_right_click_selects_before_opening_context_menu():
    calls = []
    view = object.__new__(ClipGrid)
    view._selected_id = None
    view._row_by_id = {"clip-1": FakeWidget()}
    view._name_label_by_id = {"clip-1": FakeWidget()}
    view._on_select = lambda clip: calls.append(("select", clip.id))
    view._on_context = lambda clip, x, y: calls.append(("context", clip.id, x, y))
    event = SimpleNamespace(x_root=30, y_root=40)

    view._context(event, _clip("clip-1"))

    assert calls == [("select", "clip-1"), ("context", "clip-1", 30, 40)]
    assert view._row_by_id["clip-1"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG


def test_clip_list_ctrl_click_toggles_membership():
    changes = []
    view = object.__new__(ClipList)
    view._selected_id = "a"
    view._selected_ids = {"a"}
    view._anchor_id = "a"
    view._render_order = ["a", "b", "c"]
    view._row_by_id = {"a": FakeWidget(), "b": FakeWidget(), "c": FakeWidget()}
    view._on_selection_change = changes.append

    view._toggle_select(_clip("b"))
    assert view._selected_ids == {"a", "b"}
    assert changes[-1] == ["a", "b"]  # reported in render order

    view._toggle_select(_clip("a"))
    assert view._selected_ids == {"b"}
    assert changes[-1] == ["b"]


def test_clip_list_shift_click_selects_contiguous_range():
    changes = []
    view = object.__new__(ClipList)
    view._selected_id = "a"
    view._selected_ids = {"a"}
    view._anchor_id = "a"
    view._render_order = ["a", "b", "c", "d"]
    view._row_by_id = {k: FakeWidget() for k in "abcd"}
    view._on_selection_change = changes.append

    view._range_select(_clip("c"))
    assert view._selected_ids == {"a", "b", "c"}
    assert changes[-1] == ["a", "b", "c"]


def test_clip_list_click_dispatches_on_modifier_state():
    view = object.__new__(ClipList)
    calls = []
    view._select = lambda c: calls.append(("select", c.id))
    view._toggle_select = lambda c: calls.append(("toggle", c.id))
    view._range_select = lambda c: calls.append(("range", c.id))

    view._click(SimpleNamespace(state=0), _clip("x"))
    view._click(SimpleNamespace(state=ClipList._CTRL_MASK), _clip("y"))
    view._click(SimpleNamespace(state=ClipList._SHIFT_MASK), _clip("z"))

    assert calls == [("select", "x"), ("toggle", "y"), ("range", "z")]


def test_clip_grid_ctrl_click_toggles_membership():
    changes = []
    view = object.__new__(ClipGrid)
    view._selected_id = "a"
    view._selected_ids = {"a"}
    view._anchor_id = "a"
    view._render_order = ["a", "b", "c"]
    view._row_by_id = {k: FakeWidget() for k in "abc"}
    view._name_label_by_id = {k: FakeWidget() for k in "abc"}
    view._on_selection_change = changes.append

    view._toggle_select(_clip("b"))
    assert view._selected_ids == {"a", "b"}
    assert changes[-1] == ["a", "b"]


def test_clip_grid_shift_click_selects_contiguous_range():
    changes = []
    view = object.__new__(ClipGrid)
    view._selected_id = "b"
    view._selected_ids = {"b"}
    view._anchor_id = "b"
    view._render_order = ["a", "b", "c", "d"]
    view._row_by_id = {k: FakeWidget() for k in "abcd"}
    view._name_label_by_id = {k: FakeWidget() for k in "abcd"}
    view._on_selection_change = changes.append

    view._range_select(_clip("d"))
    assert view._selected_ids == {"b", "c", "d"}
    assert changes[-1] == ["b", "c", "d"]


def test_clip_list_select_all_and_clear():
    changes = []
    view = object.__new__(ClipList)
    view._selected_id = None
    view._selected_ids = set()
    view._anchor_id = None
    view._render_order = ["a", "b", "c"]
    view._row_by_id = {k: FakeWidget() for k in "abc"}
    view._on_selection_change = changes.append

    view.select_all()
    assert view._selected_ids == {"a", "b", "c"}
    assert changes[-1] == ["a", "b", "c"]
    assert view.has_selection()

    view.clear_selection()
    assert view._selected_ids == set()
    assert changes[-1] == []
    assert not view.has_selection()


def test_clip_grid_select_all_and_clear():
    changes = []
    view = object.__new__(ClipGrid)
    view._selected_id = None
    view._selected_ids = set()
    view._anchor_id = None
    view._render_order = ["a", "b", "c"]
    view._row_by_id = {k: FakeWidget() for k in "abc"}
    view._name_label_by_id = {k: FakeWidget() for k in "abc"}
    view._on_selection_change = changes.append

    view.select_all()
    assert view._selected_ids == {"a", "b", "c"}
    assert changes[-1] == ["a", "b", "c"]

    view.clear_selection()
    assert view._selected_ids == set()
    assert changes[-1] == []


def test_clip_list_select_all_empty_is_noop():
    view = object.__new__(ClipList)
    view._selected_ids = set()
    view._render_order = []
    view._row_by_id = {}
    view._on_selection_change = lambda ids: (_ for _ in ()).throw(AssertionError("should not fire"))
    view.select_all()  # no rows → must not notify or raise
    assert view._selected_ids == set()


def test_shell_select_all_and_clear_are_wired():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp)

    assert "<Control-a>" in source
    assert "_keyboard_select_all" in source
    assert "winfo_ismapped" in source
    assert "def _clear_selection" in source
    assert "clear_selection()" in source


def test_shell_multi_select_bulk_actions_are_wired():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp)

    assert "_on_clip_selection_change" in source
    assert "_update_bulk_action_strip" in source
    assert "def _bulk_copy" in source
    assert "def _bulk_remove" in source
    assert "def _bulk_export_proof" in source
    assert "def _bulk_move_to_safe" in source


def test_shell_selection_hint_is_wired():
    from cache_vault import brand
    from cache_vault.ui.shell import CacheVaultApp

    assert brand.SELECTION_HINT == "Ctrl/Shift-click to select multiple"

    single = inspect.getsource(CacheVaultApp._update_selected_action_strip)
    bulk = inspect.getsource(CacheVaultApp._update_bulk_action_strip)

    # Hint shows for none/single selection, hides for multi (count takes over).
    assert "_set_selection_hint(brand.SELECTION_HINT)" in single
    assert '_set_selection_hint("")' in bulk
    assert 'text=f"{len(ids)} selected"' in bulk


def test_shell_context_menu_is_bulk_aware():
    from cache_vault.ui import clip_context

    open_menu = inspect.getsource(clip_context.open_clip_menu)
    bulk_menu = inspect.getsource(clip_context.open_bulk_clip_menu)

    # Branches to the bulk menu only when >1 selected AND the clicked row is in it.
    assert "len(window._selected_clip_ids) > 1" in open_menu
    assert "clip.id in window._selected_clip_ids" in open_menu
    assert "open_bulk_clip_menu" in open_menu

    # Bulk menu targets the whole set via the _bulk_* methods and names the count.
    assert "window._bulk_copy" in bulk_menu
    assert "window._bulk_export_proof" in bulk_menu
    assert "window._bulk_move_to_safe" in bulk_menu
    assert "window._bulk_remove" in bulk_menu
    assert "{n}" in bulk_menu  # labels state how many clips are affected


def test_clip_list_keyboard_context_opens_for_selected_row():
    calls = []
    view = object.__new__(ClipList)
    view._row_by_id = {"clip-1": FakeWidget()}
    view._on_context = lambda clip, x, y: calls.append((clip.id, x, y))

    view.open_context_for_selected(_clip("clip-1"))

    assert calls == [("clip-1", 34, 36)]


def test_clip_grid_keyboard_context_opens_for_selected_row():
    calls = []
    view = object.__new__(ClipGrid)
    view._row_by_id = {"clip-1": FakeWidget()}
    view._on_context = lambda clip, x, y: calls.append((clip.id, x, y))

    view.open_context_for_selected(_clip("clip-1"))

    assert calls == [("clip-1", 34, 36)]


def test_shell_selection_keyboard_and_lock_guards_are_wired():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp)

    assert "_bind_selection_keys" in source
    assert "<Shift-F10>" in source
    assert "_keyboard_open_context_menu" in source
    assert "_keyboard_focus_is_text_input" in source
    assert "_selected_clip_id = None" in source
    assert "_update_selected_action_strip(None)" in source


def test_command_center_recent_clip_context_selects_before_menu(tk_root):
    from cache_vault.ui.home_dashboard import HomeDashboard
    from cache_vault.core.models import Clip
    import tkinter as tk

    selected_clips = []
    context_calls = []

    c1 = Clip(content="hello", title="Hello")
    c1.id = "clip-1"

    dashboard = HomeDashboard(
        tk_root,
        on_filter=lambda k: None,
        on_open_receipts=lambda: None,
        on_mobile_settings=lambda: None,
        on_pair_android=lambda: None,
        on_export=lambda: None,
        on_select_clip=lambda c: selected_clips.append(c),
        on_copy=lambda _id: None,
        on_clip_context=lambda c, x, y: context_calls.append((c, x, y)),
    )

    summary = {
        "all": 1, "favorites": 0, "screenshots": 0, "duplicates": 0,
        "recently_removed": 0, "receipts": 0, "sensitive": 0, "expired": 0,
        "capture_paused": False, "mobile_enabled": False,
    }
    dashboard.render(summary, [c1], [], [])
    dashboard.update_idletasks()

    event = tk.Event()
    event.x_root = 100
    event.y_root = 200

    dashboard._on_card_context_menu(event, c1)

    assert dashboard._selected_ids == {"clip-1"}
    assert len(selected_clips) == 1
    assert selected_clips[0].id == "clip-1"

    assert len(context_calls) == 1
    assert context_calls[0] == (c1, 100, 200)

    # Multi-selection context preservation check
    c2 = Clip(content="world", title="World")
    c2.id = "clip-2"
    dashboard.render(summary, [c1, c2], [], [])
    dashboard.update_idletasks()

    dashboard._selected_ids = {"clip-1", "clip-2"}
    dashboard._on_card_context_menu(event, c1)

    # Must preserve the multi-selection count/ids
    assert dashboard._selected_ids == {"clip-1", "clip-2"}

    dashboard.destroy()


def test_command_center_empty_space_menu_has_only_app_commands():
    from cache_vault.ui import clip_context

    source = inspect.getsource(clip_context.open_home_app_menu)

    assert "open_locked_menu" in source
    assert "Quick Paste" in source
    assert "Save Current Clipboard" in source
    assert "Open All Clips" in source
    assert "Mobile Inbox" in source
    assert "Stamped Receipts" in source
    assert "Settings" in source
    assert "Remove" not in source
    assert "Delete" not in source
    assert "Clear" not in source


def test_command_center_dashboard_card_menu_is_navigation_not_clip_menu():
    from cache_vault.ui import clip_context

    source = inspect.getsource(clip_context.open_home_card_menu)

    assert "open_locked_menu" in source
    assert "_navigate_filter" in source
    assert "_navigate_screen" in source
    assert "_open_clip_menu" not in source
    assert "Remove from History" not in source


def test_command_center_status_menu_has_relevant_status_actions_only():
    from cache_vault.ui import clip_context

    source = inspect.getsource(clip_context.open_home_status_menu)

    assert "open_locked_menu" in source
    assert "Open Safe" in source
    assert "Copy Safe Summary" in source
    assert "Open Receipts" in source
    assert "Open Mobile Inbox" in source
    assert "_open_clip_menu" not in source
    assert "Remove from History" not in source


def test_command_center_context_copy_avoids_forbidden_claims():
    from cache_vault.ui import clip_context

    source = "\n".join(
        inspect.getsource(fn)
        for fn in (
            clip_context.open_home_app_menu,
            clip_context.open_home_card_menu,
            clip_context.open_home_status_menu,
        )
    ).lower()

    for claim in ("cloud sync", "encrypted safes", "final release", "bank-grade", "military-grade"):
        assert claim not in source
