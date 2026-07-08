"""Unit tests for the Desktop Photo Viewer MVP."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import customtkinter as ctk

from cache_vault.core.models import Clip
from cache_vault.ui.photo_viewer import PhotoViewer
from tk_support import probe_tk_ui

TK_OK, TK_REASON = probe_tk_ui()


class TestPhotoViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("dark")

    def setUp(self):
        if not TK_OK:
            self.skipTest(TK_REASON)
        try:
            self.root = ctk.CTk()
        except Exception as exc:
            raise unittest.SkipTest(f"Tk/CTk runtime unavailable: {exc}")
        self.root.withdraw()

        # Set up mock data
        self.clips = {
            "clip_1": Clip(id="clip_1", content_type="IMAGE", preview="Image 1"),
            "clip_2": Clip(id="clip_2", content_type="TEXT", preview="Text 1"),
            "clip_3": Clip(id="clip_3", content_type="IMAGE", preview="Image 2"),
        }
        self.assets = {
            "clip_1": (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95\x2b\x0e\x1b\x00\x00\x00\x0cIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82", "image/png"),
            "clip_3": (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01\x95\x2b\x0e\x1b\x00\x00\x00\x0cIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82", "image/png"),
        }

        self.get_clip_fn = lambda cid: self.clips.get(cid)
        self.load_asset_fn = lambda cid: self.assets.get(cid)
        self.asset_meta_fn = lambda cid: {"width": 10, "height": 10, "size_bytes": 100, "sha256": "abc"}
        self.copy_image_fn = MagicMock()
        self.save_image_as_fn = MagicMock()
        self.open_asset_folder_fn = MagicMock()

        self.all_clip_ids = ["clip_1", "clip_2", "clip_3"]

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def _viewer(self, initial_clip_id="clip_1") -> PhotoViewer:
        viewer = PhotoViewer(
            self.root,
            initial_clip_id=initial_clip_id,
            all_clip_ids=self.all_clip_ids,
            get_clip_fn=self.get_clip_fn,
            load_asset_fn=self.load_asset_fn,
            asset_meta_fn=self.asset_meta_fn,
            copy_image_fn=self.copy_image_fn,
            save_image_as_fn=self.save_image_as_fn,
            open_asset_folder_fn=self.open_asset_folder_fn,
        )
        viewer.withdraw()
        return viewer

    def test_photo_viewer_initialization_and_filtering(self):
        viewer = self._viewer("clip_1")
        try:
            # clip_2 is TEXT, so it must be filtered out
            self.assertEqual(viewer._image_ids, ["clip_1", "clip_3"])
            self.assertEqual(viewer._current_index, 0)
        finally:
            viewer.destroy()

    def test_photo_viewer_navigation(self):
        viewer = self._viewer("clip_1")
        try:
            # Initially at clip_1
            self.assertEqual(viewer._get_current_clip_id(), "clip_1")
            
            # Go to next -> clip_3
            viewer._next_image()
            self.assertEqual(viewer._current_index, 1)
            self.assertEqual(viewer._get_current_clip_id(), "clip_3")

            # Prev -> clip_1
            viewer._prev_image()
            self.assertEqual(viewer._current_index, 0)
            self.assertEqual(viewer._get_current_clip_id(), "clip_1")
        finally:
            viewer.destroy()

    def test_photo_viewer_zoom(self):
        viewer = self._viewer("clip_1")
        try:
            # Set to 1.0 zoom reset
            viewer._zoom_reset()
            self.assertAlmostEqual(viewer._zoom_factor, 1.0)

            # Zoom in
            viewer._zoom_in()
            self.assertAlmostEqual(viewer._zoom_factor, 1.2)

            # Zoom out
            viewer._zoom_out()
            self.assertAlmostEqual(viewer._zoom_factor, 1.0)
        finally:
            viewer.destroy()

    def test_photo_viewer_action_callbacks(self):
        viewer = self._viewer("clip_3")
        try:
            viewer._action_copy()
            self.copy_image_fn.assert_called_once_with("clip_3")

            viewer._action_save()
            self.save_image_as_fn.assert_called_once_with("clip_3")

            viewer._action_folder()
            self.open_asset_folder_fn.assert_called_once_with("clip_3")
        finally:
            viewer.destroy()

    def test_photo_viewer_missing_asset(self):
        # clip_4 is an image but has no asset bytes
        self.clips["clip_4"] = Clip(id="clip_4", content_type="IMAGE", preview="Missing")
        viewer = self._viewer("clip_4")
        try:
            self.assertIsNone(viewer._pil_image)
        finally:
            viewer.destroy()


if __name__ == "__main__":
    unittest.main()
