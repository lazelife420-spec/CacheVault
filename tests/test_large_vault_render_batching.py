"""Tests for large-vault render batching, generation cancellation, and UI responsiveness."""

import unittest
from unittest.mock import MagicMock
import customtkinter as ctk

from cache_vault.core.models import Clip, now_iso
from cache_vault.ui.clip_list import ClipList
from cache_vault.ui.clip_grid import ClipGrid


def make_dummy_clips(count: int) -> list[Clip]:
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


class TestLargeVaultRenderBatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_clip_list_first_batch_renders_immediately(self):
        clips = make_dummy_clips(100)
        on_select = MagicMock()
        clip_list = ClipList(self.root, on_select=on_select)
        
        # First row renders synchronously for responsive first-content;
        # remaining rows are batched via after(5).
        clip_list.render_batched(clips)
        self.assertEqual(len(clip_list._rows), 1)
        self.assertIsNotNone(clip_list._render_job)
        clip_list.destroy()

    def test_clip_grid_first_batch_renders_immediately(self):
        clips = make_dummy_clips(100)
        on_select = MagicMock()
        clip_grid = ClipGrid(self.root, on_select=on_select)
        
        clip_grid.render_batched(clips)
        self.assertIsNotNone(clip_grid._render_job)
        clip_grid.destroy()

    def test_clip_list_generation_cancellation(self):
        clips1 = make_dummy_clips(100)
        clips2 = make_dummy_clips(50)
        on_select = MagicMock()
        clip_list = ClipList(self.root, on_select=on_select)

        # First render job
        clip_list.render_batched(clips1)
        gen1 = clip_list._render_generation

        # Superseding render job immediately cancels previous generation
        clip_list.render_batched(clips2)
        gen2 = clip_list._render_generation

        self.assertNotEqual(gen1, gen2)
        # Verify rows reflect second clip set's first row
        self.assertEqual(len(clip_list._rows), 1)
        clip_list.destroy()

    def test_clip_list_cancel_render_clears_job(self):
        clips = make_dummy_clips(100)
        on_select = MagicMock()
        clip_list = ClipList(self.root, on_select=on_select)

        clip_list.render_batched(clips)
        self.assertIsNotNone(clip_list._render_job)
        
        clip_list.cancel_render()
        self.assertIsNone(clip_list._render_job)
        clip_list.destroy()

    def test_empty_clips_renders_empty_state_immediately(self):
        on_select = MagicMock()
        clip_list = ClipList(self.root, on_select=on_select)
        on_complete = MagicMock()

        clip_list.render_batched([], on_complete=on_complete)
        self.assertEqual(len(clip_list._rows), 0)
        on_complete.assert_called_once()
        clip_list.destroy()


def make_grouped_clips(groups: int, per_group: int) -> list[Clip]:
    """Clips spread across `groups` distinct source_app values."""
    clips = []
    for g in range(groups):
        for i in range(per_group):
            clips.append(
                Clip(
                    id=f"clip-{g}-{i}",
                    content_type="text",
                    content=f"Clip content {g}-{i}",
                    created_at=now_iso(),
                    updated_at=now_iso(),
                    source_app=f"App{g}",
                )
            )
    return clips


class TestGroupedRenderFirstContent(unittest.TestCase):
    """The grouped list path must paint a real clip row synchronously, and
    must never drop a group header while doing so."""

    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _drain(self, clip_list, limit=2000):
        for _ in range(limit):
            if clip_list._render_job is None:
                break
            self.root.update()
        return clip_list._render_job is None

    def test_grouped_render_paints_a_clip_row_synchronously(self):
        """A group header alone is not content. render_batched must return
        with at least one actual clip row already built, otherwise
        first-content latency is gated on the first after() tick."""
        clips = make_grouped_clips(3, 10)
        clip_list = ClipList(self.root, on_select=MagicMock())

        clip_list.render_batched(clips, group_by="source")

        self.assertEqual(
            len(clip_list._rows), 1,
            "exactly one clip row must be built synchronously",
        )
        clip_list.cancel_render()
        clip_list.destroy()

    def test_grouped_render_skips_no_header_when_leading_group_collapsed(self):
        """With the leading group collapsed, flat_pending starts with two
        consecutive headers. Scanning forward to the first clip must still
        build every header it passes over, not jump past them."""
        clips = make_grouped_clips(3, 10)
        clip_list = ClipList(self.root, on_select=MagicMock())

        from cache_vault.core import grouping
        titles = list(grouping.group_clips(clips, "source").keys())
        clip_list._collapsed_groups.add(("source", titles[0]))

        built = []
        orig = clip_list._build_group_header

        def spy(group_by, title, count):
            built.append(title)
            return orig(group_by, title, count)

        clip_list._build_group_header = spy

        clip_list.render_batched(clips, group_by="source")
        # First clip lives under titles[1]; both leading headers must
        # already exist by the time render_batched returns.
        self.assertEqual(built, titles[:2])
        self.assertEqual(len(clip_list._rows), 1)

        self.assertTrue(self._drain(clip_list), "render did not finish")
        self.assertEqual(
            built, titles,
            "every group header must be built exactly once, in order",
        )
        clip_list.destroy()

    def test_grouped_render_all_collapsed_still_completes(self):
        """Every group collapsed means flat_pending is all headers and no
        clips. The synchronous scan must stop at the batch cap and the
        render must still reach on_complete."""
        clips = make_grouped_clips(20, 2)
        clip_list = ClipList(self.root, on_select=MagicMock())

        from cache_vault.core import grouping
        titles = list(grouping.group_clips(clips, "source").keys())
        for t in titles:
            clip_list._collapsed_groups.add(("source", t))

        on_complete = MagicMock()
        clip_list.render_batched(
            clips, group_by="source", on_complete=on_complete,
        )
        self.assertEqual(len(clip_list._rows), 0)

        self.assertTrue(self._drain(clip_list), "render did not finish")
        on_complete.assert_called_once()
        clip_list.destroy()


if __name__ == "__main__":
    unittest.main()
