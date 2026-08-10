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
        
        # render_batched with batch_size = 8 should render initial 8 rows synchronously
        clip_list.render_batched(clips)
        self.assertEqual(len(clip_list._rows), 8)
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
        # Verify rows reflect second clip set's first batch
        self.assertEqual(len(clip_list._rows), 8)
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


if __name__ == "__main__":
    unittest.main()
