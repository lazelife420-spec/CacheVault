from __future__ import annotations

from types import SimpleNamespace

from cache_vault import brand
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.clip_list import ClipList


class FakeWidget:
    def __init__(self):
        self.configured: list[dict] = []

    def configure(self, **kwargs) -> None:
        self.configured.append(kwargs)


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
