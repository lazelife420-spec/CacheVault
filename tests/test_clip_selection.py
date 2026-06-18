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


def test_command_center_recent_clip_context_selects_before_menu():
    from cache_vault.ui.home_dashboard import HomeDashboard

    source = inspect.getsource(HomeDashboard._bind_clip_card)

    assert "self._selected_clip_id = c.id" in source
    assert "self._on_select_clip(c)" in source
    assert "self._on_clip_context(c, e.x_root, e.y_root)" in source
    assert source.index("self._on_select_clip(c)") < source.index("self._on_clip_context")


def test_command_center_empty_space_menu_has_only_app_commands():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._open_home_app_menu)

    assert "_open_locked_menu" in source
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
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._open_home_card_menu)

    assert "_open_locked_menu" in source
    assert "_navigate_filter" in source
    assert "_navigate_screen" in source
    assert "_open_clip_menu" not in source
    assert "Remove from History" not in source


def test_command_center_status_menu_has_relevant_status_actions_only():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._open_home_status_menu)

    assert "_open_locked_menu" in source
    assert "Open Safe" in source
    assert "Copy Safe Summary" in source
    assert "Open Receipts" in source
    assert "Open Mobile Inbox" in source
    assert "_open_clip_menu" not in source
    assert "Remove from History" not in source


def test_command_center_context_copy_avoids_forbidden_claims():
    from cache_vault.ui.shell import CacheVaultApp

    source = "\n".join(
        inspect.getsource(fn)
        for fn in (
            CacheVaultApp._open_home_app_menu,
            CacheVaultApp._open_home_card_menu,
            CacheVaultApp._open_home_status_menu,
        )
    ).lower()

    for claim in ("cloud sync", "encrypted safes", "final release", "bank-grade", "military-grade"):
        assert claim not in source
