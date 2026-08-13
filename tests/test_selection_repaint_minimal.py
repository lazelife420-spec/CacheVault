"""Selection repaint must touch only the rows whose appearance changes.

Navigating a filtered view repainted every rendered row, even when the
selection was identical (or empty) and even though those rows were destroyed
milliseconds later by clear(). On a 120-row view that measured ~2.15 s of
blocked main thread out of a ~2.17 s click handler, with 120 of 122
_update_row_visuals calls writing the state the row already had.

These tests pin the contract by counting repaints, not by timing anything.
"""
from __future__ import annotations

from types import SimpleNamespace

from cache_vault import brand
from cache_vault.ui import theme
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.clip_list import ClipList


class RecordingRow:
    """Stands in for a row/card widget, recording every configure()."""

    def __init__(self):
        self.configured: list[dict] = []

    def configure(self, **kwargs) -> None:
        self.configured.append(kwargs)

    def winfo_ismapped(self) -> bool:
        return False

    def pack(self, **kwargs) -> None:
        pass

    def pack_forget(self) -> None:
        pass

    def winfo_rootx(self) -> int:
        return 0

    def winfo_rooty(self) -> int:
        return 0

    def winfo_height(self) -> int:
        return 32


def _list_view(ids, selected=()):
    view = object.__new__(ClipList)
    view._row_by_id = {i: RecordingRow() for i in ids}
    view._rail_by_id = {}
    view._selected_badge_by_id = {}
    view._action_bar_by_id = {}
    view._title_label_by_id = {}
    view._meta_label_by_id = {}
    view._render_order = list(ids)
    view._selected_ids = set(selected)
    view._selected_id = next(iter(selected), None)
    view._anchor_id = view._selected_id
    view._last_clips = []
    view._on_selection_change = None
    # Whatever is selected at setup is already painted that way on screen.
    view._painted_selected_ids = set(selected)
    return view


def _grid_view(ids, selected=()):
    view = object.__new__(ClipGrid)
    view._row_by_id = {i: RecordingRow() for i in ids}
    view._name_label_by_id = {i: RecordingRow() for i in ids}
    view._render_order = list(ids)
    view._selected_ids = set(selected)
    view._selected_id = next(iter(selected), None)
    view._anchor_id = view._selected_id
    view._on_selection_change = None
    view._painted_selected_ids = set(selected)
    return view


def _touched(view):
    """Ids whose row widget received at least one configure() call."""
    return {cid for cid, row in view._row_by_id.items() if row.configured}


# --- A. select one row: only that row repaints -------------------------

def test_list_select_one_row_repaints_only_that_row():
    view = _list_view("abcde")

    view._selected_ids = {"c"}
    view._repaint_selection()

    assert _touched(view) == {"c"}
    assert view._row_by_id["c"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG


# --- B. deselect one row: only that row repaints ----------------------

def test_list_deselect_one_row_repaints_only_that_row():
    view = _list_view("abcde", selected={"c"})

    view._selected_ids = set()
    view._repaint_selection()

    assert _touched(view) == {"c"}
    assert view._row_by_id["c"].configured[-1]["fg_color"] == brand.ROW_BG


# --- C. selection A -> B: symmetric difference repaints ---------------

def test_list_selection_change_repaints_symmetric_difference_only():
    view = _list_view("abcdef", selected={"a", "b", "c"})

    view._selected_ids = {"c", "d", "e"}
    view._repaint_selection()

    # a,b deselected; d,e selected; c unchanged and must NOT be touched.
    assert _touched(view) == {"a", "b", "d", "e"}
    assert view._row_by_id["a"].configured[-1]["fg_color"] == brand.ROW_BG
    assert view._row_by_id["b"].configured[-1]["fg_color"] == brand.ROW_BG
    assert view._row_by_id["d"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG
    assert view._row_by_id["e"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG
    assert view._row_by_id["c"].configured == []


# --- D. selection unchanged: no repaint at all ------------------------

def test_list_unchanged_selection_repaints_nothing():
    view = _list_view("abcdef", selected={"b", "d"})

    view._repaint_selection()

    assert _touched(view) == set()


def test_list_unchanged_empty_selection_repaints_nothing():
    """The navigation case: nothing selected, nothing to repaint."""
    view = _list_view([f"clip{i:03d}" for i in range(120)])

    view._repaint_selection()

    assert _touched(view) == set()


# --- E. navigation that destroys the view: no pointless full repaint --

def test_list_clear_selection_before_teardown_does_not_repaint_every_row():
    """Esc/navigation on a 120-row view with a single selected row must repaint
    that one row, not all 120. This is the measured hitch."""
    ids = [f"clip{i:03d}" for i in range(120)]
    view = _list_view(ids, selected={"clip042"})

    view.clear_selection()

    assert _touched(view) == {"clip042"}
    assert len(view._row_by_id) == 120


def test_list_clear_drops_painted_state_so_rebuild_does_not_repaint_dead_rows():
    ids = [f"clip{i:03d}" for i in range(8)]
    view = _list_view(ids, selected={"clip003"})
    # Simulate clear(): rows destroyed, tracking reset.
    view._row_by_id.clear()
    view._painted_ids().clear()
    view._selected_ids = set()

    view._repaint_selection()

    assert view._painted_ids() == set()


# --- F. row selected after first render gets full presentation --------

def test_list_row_selected_after_render_receives_full_selected_presentation(monkeypatch):
    """Guards the documented behaviour that title/meta presentation must be
    applied on selection change, not only at build time."""
    # theme.font() resolves a per-interpreter cache and needs a Tk root; this
    # test is about which widgets get repainted, not about font objects.
    monkeypatch.setattr(theme, "font", lambda **kw: ("font", tuple(sorted(kw.items()))))
    view = _list_view("abc")
    title = RecordingRow()
    meta = RecordingRow()
    rail = RecordingRow()
    badge = RecordingRow()
    view._title_label_by_id = {"b": title}
    view._meta_label_by_id = {"b": meta}
    view._rail_by_id = {"b": rail}
    view._selected_badge_by_id = {"b": badge}

    view._selected_ids = {"b"}
    view._repaint_selection()

    row_cfg = view._row_by_id["b"].configured[-1]
    assert row_cfg["fg_color"] == brand.ROW_SELECTED_BG
    assert row_cfg["border_color"] == brand.PROOF_TEAL
    assert title.configured, "title font must be repainted on selection"
    assert meta.configured, "meta label must be repainted on selection"
    assert meta.configured[-1]["text_color"] == brand.RECEIPT_WHITE
    assert rail.configured[-1]["fg_color"] == brand.PROOF_TEAL


# --- G. ClipGrid obeys the same contract ------------------------------

def test_grid_selection_change_repaints_symmetric_difference_only():
    view = _grid_view("abcdef", selected={"a", "b", "c"})

    view._selected_ids = {"c", "d", "e"}
    view._repaint_selection()

    assert _touched(view) == {"a", "b", "d", "e"}
    assert view._row_by_id["c"].configured == []
    assert view._name_label_by_id["d"].configured[-1]["text_color"] == brand.PROOF_TEAL


def test_grid_unchanged_empty_selection_repaints_nothing():
    view = _grid_view([f"clip{i:03d}" for i in range(120)])

    view._repaint_selection()

    assert _touched(view) == set()


def test_grid_clear_selection_before_teardown_repaints_only_selected_row():
    ids = [f"clip{i:03d}" for i in range(120)]
    view = _grid_view(ids, selected={"clip077"})

    view.clear_selection()

    assert _touched(view) == {"clip077"}


# --- multi-select paths keep working ---------------------------------

def test_list_select_all_then_clear_repaints_each_row_once_per_transition():
    ids = list("abcde")
    view = _list_view(ids)

    view.select_all()
    assert _touched(view) == set(ids)
    per_row_after_select = {c: len(r.configured) for c, r in view._row_by_id.items()}
    assert all(n == 1 for n in per_row_after_select.values()), per_row_after_select

    view.clear_selection()
    assert all(len(r.configured) == 2 for r in view._row_by_id.values())


def test_list_toggle_select_repaints_only_the_toggled_row():
    view = _list_view("abcde", selected={"a"})

    view._on_select = lambda clip: None
    view._toggle_select(SimpleNamespace(id="d"))

    assert _touched(view) == {"d"}
    assert view._row_by_id["d"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG


def test_list_set_selected_ids_repaints_only_the_difference():
    view = _list_view("abcdef", selected={"a", "b"})

    view.set_selected_ids({"b", "c"})

    assert _touched(view) == {"a", "c"}


# --- the mirror cannot drift -----------------------------------------

def test_painted_mirror_tracks_direct_update_row_visuals_calls():
    view = _list_view("abc")

    view._update_row_visuals("b", True)
    assert view._painted_ids() == {"b"}

    view._update_row_visuals("b", False)
    assert view._painted_ids() == set()


def test_painted_mirror_ignores_ids_without_rows():
    view = _list_view("abc")

    view._update_row_visuals("missing", True)

    assert view._painted_ids() == set()


def test_list_repaint_falls_back_to_full_pass_when_mirror_uninitialised():
    """With no mirror there is no way to know what is on screen, so every row
    must be repainted -- the pre-repair behaviour. Skipping rows here would
    leave a visibly selected row painted after it was deselected."""
    view = object.__new__(ClipList)
    view._row_by_id = {"old": RecordingRow(), "new": RecordingRow()}
    view._rail_by_id = {}
    view._selected_badge_by_id = {}
    view._action_bar_by_id = {}
    view._title_label_by_id = {}
    view._meta_label_by_id = {}
    view._render_order = ["old", "new"]
    view._selected_id = "old"          # painted selected, mirror absent
    view._selected_ids = {"new"}       # newly desired

    view._repaint_selection()

    assert _touched(view) == {"old", "new"}
    assert view._row_by_id["old"].configured[-1]["fg_color"] == brand.ROW_BG
    assert view._row_by_id["new"].configured[-1]["fg_color"] == brand.ROW_SELECTED_BG


def test_grid_repaint_falls_back_to_full_pass_when_mirror_uninitialised():
    view = object.__new__(ClipGrid)
    view._row_by_id = {"old": RecordingRow(), "new": RecordingRow()}
    view._name_label_by_id = {"old": RecordingRow(), "new": RecordingRow()}
    view._render_order = ["old", "new"]
    view._selected_id = "old"
    view._selected_ids = {"new"}

    view._repaint_selection()

    assert _touched(view) == {"old", "new"}
    assert view._row_by_id["old"].configured[-1]["fg_color"] == brand.ROW_BG


def test_list_fallback_pass_leaves_the_mirror_accurate_for_the_next_repaint():
    view = object.__new__(ClipList)
    view._row_by_id = {i: RecordingRow() for i in "abc"}
    view._rail_by_id = {}
    view._selected_badge_by_id = {}
    view._action_bar_by_id = {}
    view._title_label_by_id = {}
    view._meta_label_by_id = {}
    view._render_order = list("abc")
    view._selected_id = None
    view._selected_ids = {"b"}

    view._repaint_selection()               # unknown state -> full pass
    assert _touched(view) == {"a", "b", "c"}
    assert view._painted_ids() == {"b"}

    for row in view._row_by_id.values():
        row.configured.clear()
    view._selected_ids = {"b", "c"}
    view._repaint_selection()               # mirror trusted -> narrow pass

    assert _touched(view) == {"c"}


def test_repaint_drops_stale_ids_whose_rows_are_gone():
    view = _list_view("abc", selected={"a"})
    del view._row_by_id["a"]
    view._selected_ids = {"b"}

    view._repaint_selection()

    assert view._painted_ids() == {"b"}
