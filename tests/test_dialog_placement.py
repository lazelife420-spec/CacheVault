"""Dialog ownership/centering/modality: Combined Clip Preview, Edit Clip
Text, Settings Hub.

Before this, all three were transient(parent) but placed at a fixed
geometry with no +x+y offset -- left to whatever the window manager
picked, not centered over the app -- and Combined Preview/Edit Clip Text's
Close/Cancel/<Escape> paths relied on Tk's implicit grab release on
destroy rather than an explicit one.
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.dialogs import _center_on_parent
from cache_vault.ui.clip_workflows import ClipComposerDialog, EditClipTextDialog
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()


class _FakeWin:
    def __init__(self, sw: int, sh: int):
        self._sw, self._sh = sw, sh
        self.geometry_calls: list[str] = []

    def winfo_screenwidth(self) -> int:
        return self._sw

    def winfo_screenheight(self) -> int:
        return self._sh

    def geometry(self, spec: str) -> None:
        self.geometry_calls.append(spec)


class _FakeMaster:
    def __init__(self, x: int, y: int, w: int, h: int):
        self._x, self._y, self._w, self._h = x, y, w, h
        self.idle_calls = 0

    def update_idletasks(self) -> None:
        self.idle_calls += 1

    def winfo_rootx(self) -> int:
        return self._x

    def winfo_rooty(self) -> int:
        return self._y

    def winfo_width(self) -> int:
        return self._w

    def winfo_height(self) -> int:
        return self._h


def test_center_on_parent_centers_within_a_large_screen():
    master = _FakeMaster(x=100, y=100, w=1000, h=800)
    win = _FakeWin(sw=1920, sh=1080)

    _center_on_parent(win, master, 400, 300)

    assert master.idle_calls == 1
    assert win.geometry_calls == ["400x300+400+350"]


def test_center_on_parent_clamps_to_zero_when_parent_near_top_left_edge():
    master = _FakeMaster(x=-50, y=-50, w=200, h=200)
    win = _FakeWin(sw=1920, sh=1080)

    _center_on_parent(win, master, 800, 600)

    assert win.geometry_calls == ["800x600+0+0"]


def test_center_on_parent_clamps_to_screen_bounds_when_parent_near_bottom_right():
    master = _FakeMaster(x=1800, y=900, w=200, h=200)
    win = _FakeWin(sw=1920, sh=1080)

    _center_on_parent(win, master, 800, 600)

    assert win.geometry_calls == ["800x600+1120+480"]


def test_center_on_parent_is_a_no_op_when_master_is_unreadable():
    class _Dead:
        def update_idletasks(self):
            raise RuntimeError("widget is gone")

    win = _FakeWin(1920, 1080)
    _center_on_parent(win, _Dead(), 400, 300)
    assert win.geometry_calls == []


@pytest.mark.skipif(not OK, reason=REASON)
class TestDialogPlacementLive:
    """Real-Tk checks: dialogs still construct/destroy cleanly with the new
    centering wired in, and Close/Cancel/<Escape> release any grab."""

    def _settle(self, dialog, timeout: float = 1.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            dialog.update()
            time.sleep(0.02)

    def test_combined_preview_sizes_and_centers_without_error(self, tk_root):
        tk_root.geometry("1200x800+50+50")
        tk_root.update_idletasks()
        dialog = ClipComposerDialog(
            tk_root, parts=["one", "two"],
            on_copy=lambda t: None, on_save_clip=lambda t: None, on_save_macro=lambda t: None,
        )
        try:
            self._settle(dialog)
            geo = dialog.geometry()
            assert geo.startswith("760x560")
        finally:
            dialog.destroy()  # must not raise even though grab_set() may have fired

    def test_edit_clip_text_sizes_and_centers_without_error(self, tk_root):
        tk_root.geometry("1200x800+50+50")
        tk_root.update_idletasks()
        dialog = EditClipTextDialog(
            tk_root, title="Edit", initial_text="hello", on_save=lambda t: None,
        )
        try:
            self._settle(dialog)
            geo = dialog.geometry()
            assert geo.startswith("720x520")
        finally:
            dialog.destroy()

    def test_combined_preview_destroy_releases_grab(self, tk_root):
        dialog = ClipComposerDialog(
            tk_root, parts=["one"],
            on_copy=lambda t: None, on_save_clip=lambda t: None, on_save_macro=lambda t: None,
        )
        self._settle(dialog)  # lets the deferred grab_set() actually run
        dialog.destroy()
        # A held grab would make grab_current() still point at (the now
        # destroyed) dialog, or at minimum raise on further interaction --
        # asserting it's cleared confirms destroy() didn't leak the grab.
        assert tk_root.grab_current() is None

    def test_edit_clip_text_close_via_escape_releases_grab(self, tk_root):
        dialog = EditClipTextDialog(
            tk_root, title="Edit", initial_text="x", on_save=lambda t: None,
        )
        self._settle(dialog)
        dialog.event_generate("<Escape>")
        dialog.update()
        assert tk_root.grab_current() is None
