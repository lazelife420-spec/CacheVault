"""Row/card builders must reuse shared font objects.

Every CTkFont is a tkinter.font.Font whose __del__ calls into Tk ("font
delete").  A render that constructs a font per label orphans well over a
thousand of them, so the garbage collector ends up performing Tk work on
whichever thread it happens to run on.  When that thread is the refresh
worker (mid-query), Tk gets called off the main thread and the refresh
hangs -- observed as "refresh did not settle" with a worker stuck inside
storage.counts.

Caching also removes a Tcl "font create" round-trip per label.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import customtkinter as ctk

from cache_vault.core.models import Clip, now_iso
from cache_vault.ui import theme
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.clip_list import ClipList


def make_clips(count: int) -> list[Clip]:
    return [
        Clip(
            id=f"clip-{i}",
            content_type="text",
            content=f"Clip content {i}",
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        for i in range(count)
    ]


class _FontCounter:
    """Counts CTkFont constructions while active."""

    def __init__(self):
        self.count = 0
        self._orig = ctk.CTkFont.__init__

    def __enter__(self):
        orig = self._orig
        counter = self

        def counting_init(inner_self, *a, **kw):
            counter.count += 1
            return orig(inner_self, *a, **kw)

        ctk.CTkFont.__init__ = counting_init
        return self

    def __exit__(self, *exc):
        ctk.CTkFont.__init__ = self._orig
        return False


class TestThemeFontCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_same_spec_returns_same_instance(self):
        a = theme.font(size=11, weight="bold")
        b = theme.font(size=11, weight="bold")
        self.assertIs(a, b)

    def test_different_specs_return_different_instances(self):
        self.assertIsNot(theme.font(size=11), theme.font(size=12))
        self.assertIsNot(
            theme.font(size=11), theme.font(size=11, weight="bold"),
        )

    def test_body_and_mono_helpers_are_cached(self):
        self.assertIs(theme.body_font(12), theme.body_font(12))
        self.assertIs(theme.mono_font(11), theme.mono_font(11))
        self.assertIsNot(theme.body_font(12), theme.mono_font(12))


class TestRenderAllocatesNoPerRowFonts(unittest.TestCase):
    """The real invariant: font construction must not scale with row count."""

    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _drain(self, view, limit=4000):
        for _ in range(limit):
            if view._render_job is None:
                return True
            self.root.update()
        return view._render_job is None

    def test_clip_list_render_creates_no_new_fonts_once_warm(self):
        clips = make_clips(40)
        view = ClipList(self.root, on_select=MagicMock())

        # Warm the shared cache with whatever variants a row needs.
        view.render_batched(clips)
        self.assertTrue(self._drain(view), "first render did not finish")

        with _FontCounter() as counter:
            view.render_batched(clips)
            self.assertTrue(self._drain(view), "second render did not finish")

        self.assertEqual(
            counter.count, 0,
            "rendering 40 rows must construct no new font objects; "
            f"constructed {counter.count}",
        )
        view.destroy()

    def test_clip_grid_render_creates_no_new_fonts_once_warm(self):
        clips = make_clips(40)
        view = ClipGrid(self.root, on_select=MagicMock())

        view.render_batched(clips)
        self.assertTrue(self._drain(view), "first render did not finish")

        with _FontCounter() as counter:
            view.render_batched(clips)
            self.assertTrue(self._drain(view), "second render did not finish")

        self.assertEqual(
            counter.count, 0,
            "rendering 40 cards must construct no new font objects; "
            f"constructed {counter.count}",
        )
        view.destroy()


if __name__ == "__main__":
    unittest.main()
