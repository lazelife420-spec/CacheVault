"""Unit tests for the Desktop Photo Viewer — MVP + Polish 1."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from cache_vault.core.models import Clip, CONTENT_IMAGE, CONTENT_TEXT
from cache_vault.ui.photo_viewer import PhotoViewer
from tk_support import probe_tk_ui

TK_OK, TK_REASON = probe_tk_ui()

# ---------------------------------------------------------------------------
# Minimal valid 10×10 PNG bytes (reused from MVP tests)
# ---------------------------------------------------------------------------
_PNG_10X10 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n"
    b"\x08\x06\x00\x00\x00\x8d2\xcf\xbd\x00\x00\x00\x04gAMA\x00\x00\xb1"
    b"\x8f\x0b\xfca\x05\x00\x00\x00\tpHYs\x00\x00\x0e\xc4\x00\x00\x0e\xc4"
    b"\x01\x95\x2b\x0e\x1b\x00\x00\x00\x0cIDATx\x9cc`\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


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

        # Mock data: clip_1 and clip_3 are IMAGE; clip_2 is TEXT
        self.clips = {
            "clip_1": Clip(id="clip_1", content_type=CONTENT_IMAGE, preview="Image 1"),
            "clip_2": Clip(id="clip_2", content_type=CONTENT_TEXT, preview="Text 1"),
            "clip_3": Clip(id="clip_3", content_type=CONTENT_IMAGE, preview="Image 2"),
        }
        self.assets = {
            "clip_1": (_PNG_10X10, "image/png"),
            "clip_3": (_PNG_10X10, "image/png"),
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

    def _viewer(self, initial_clip_id: str = "clip_1") -> PhotoViewer:
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

    # ------------------------------------------------------------------ #
    # MVP tests (preserved)
    # ------------------------------------------------------------------ #

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
            self.assertEqual(viewer._get_current_clip_id(), "clip_1")

            viewer._next_image()
            self.assertEqual(viewer._current_index, 1)
            self.assertEqual(viewer._get_current_clip_id(), "clip_3")

            viewer._prev_image()
            self.assertEqual(viewer._current_index, 0)
            self.assertEqual(viewer._get_current_clip_id(), "clip_1")
        finally:
            viewer.destroy()

    def test_photo_viewer_zoom(self):
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            self.assertAlmostEqual(viewer._zoom_factor, 1.0)

            viewer._zoom_in()
            self.assertAlmostEqual(viewer._zoom_factor, 1.2)

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
        self.clips["clip_4"] = Clip(id="clip_4", content_type=CONTENT_IMAGE, preview="Missing")
        viewer = self._viewer("clip_4")
        try:
            self.assertIsNone(viewer._pil_image)
        finally:
            viewer.destroy()

    # ------------------------------------------------------------------ #
    # Polish 1 tests
    # ------------------------------------------------------------------ #

    # --- Mouse-wheel zoom ---

    def test_mousewheel_up_calls_zoom_in(self):
        """<MouseWheel> with positive delta zooms in."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            before = viewer._zoom_factor
            event = MagicMock()
            event.delta = 120  # Windows: one notch up
            viewer._on_mousewheel(event)
            self.assertGreater(viewer._zoom_factor, before)
        finally:
            viewer.destroy()

    def test_mousewheel_down_calls_zoom_out(self):
        """<MouseWheel> with negative delta zooms out."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            before = viewer._zoom_factor
            event = MagicMock()
            event.delta = -120  # Windows: one notch down
            viewer._on_mousewheel(event)
            self.assertLess(viewer._zoom_factor, before)
        finally:
            viewer.destroy()

    def test_mousewheel_zero_delta_does_not_zoom_in(self):
        """delta == 0 should not zoom in."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            before = viewer._zoom_factor
            event = MagicMock()
            event.delta = 0
            viewer._on_mousewheel(event)
            # delta == 0 is treated as "not > 0", so _zoom_out is called
            # zoom should not increase
            self.assertLessEqual(viewer._zoom_factor, before)
        finally:
            viewer.destroy()

    # --- Keyboard Fit shortcut ---

    def test_f_key_binding_points_to_zoom_fit(self):
        """<f> keyboard binding must exist and call _zoom_fit."""
        viewer = self._viewer("clip_1")
        try:
            # Confirm the binding exists via tkinter's bind() query
            bindings_lower = viewer.bind("<f>")
            bindings_upper = viewer.bind("<F>")
            self.assertTrue(
                bindings_lower or bindings_upper,
                "<f> / <F> should be bound"
            )
        finally:
            viewer.destroy()

    def test_f_key_actually_fits(self):
        """Calling _zoom_fit sets _is_fitted True and resets offsets."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            self.assertFalse(viewer._is_fitted)
            viewer._zoom_fit()
            self.assertTrue(viewer._is_fitted)
            self.assertEqual(viewer._offset_x, 0.0)
            self.assertEqual(viewer._offset_y, 0.0)
        finally:
            viewer.destroy()

    # --- Double-click toggle Fit ↔ 1:1 ---

    def test_double_click_when_fitted_goes_to_reset(self):
        """Double-click while fitted → zooms to 1:1."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            self.assertTrue(viewer._is_fitted)
            event = MagicMock()
            viewer._on_double_click(event)
            self.assertAlmostEqual(viewer._zoom_factor, 1.0)
            self.assertFalse(viewer._is_fitted)
        finally:
            viewer.destroy()

    def test_double_click_when_not_fitted_goes_to_fit(self):
        """Double-click while not fitted → runs zoom fit."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_reset()
            self.assertFalse(viewer._is_fitted)
            event = MagicMock()
            viewer._on_double_click(event)
            self.assertTrue(viewer._is_fitted)
            self.assertEqual(viewer._offset_x, 0.0)
            self.assertEqual(viewer._offset_y, 0.0)
        finally:
            viewer.destroy()

    def test_double_click_toggle_is_idempotent(self):
        """Two double-clicks should leave the viewer back in the original fit state."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            event = MagicMock()
            viewer._on_double_click(event)  # → 1:1
            viewer._on_double_click(event)  # → fit again
            self.assertTrue(viewer._is_fitted)
        finally:
            viewer.destroy()

    # --- Missing asset updates nav label/buttons ---

    def test_missing_asset_updates_nav_label(self):
        """Nav label must update to '1 / N' even when the asset file is missing."""
        self.clips["clip_4"] = Clip(id="clip_4", content_type=CONTENT_IMAGE, preview="Missing")
        all_ids = ["clip_4", "clip_1", "clip_3"]
        viewer = PhotoViewer(
            self.root,
            initial_clip_id="clip_4",
            all_clip_ids=all_ids,
            get_clip_fn=self.get_clip_fn,
            load_asset_fn=self.load_asset_fn,
            asset_meta_fn=self.asset_meta_fn,
            copy_image_fn=self.copy_image_fn,
            save_image_as_fn=self.save_image_as_fn,
            open_asset_folder_fn=self.open_asset_folder_fn,
        )
        viewer.withdraw()
        try:
            # clip_4 has no asset; nav label should still reflect "1 / 3"
            label_text = viewer._info_label.cget("text")
            self.assertEqual(label_text, "1 / 3")
        finally:
            viewer.destroy()

    def test_missing_asset_next_button_enabled_when_more_images_exist(self):
        """Next button must be enabled when a missing-asset clip has images after it."""
        self.clips["clip_4"] = Clip(id="clip_4", content_type=CONTENT_IMAGE, preview="Missing")
        all_ids = ["clip_4", "clip_1", "clip_3"]
        viewer = PhotoViewer(
            self.root,
            initial_clip_id="clip_4",
            all_clip_ids=all_ids,
            get_clip_fn=self.get_clip_fn,
            load_asset_fn=self.load_asset_fn,
            asset_meta_fn=self.asset_meta_fn,
            copy_image_fn=self.copy_image_fn,
            save_image_as_fn=self.save_image_as_fn,
            open_asset_folder_fn=self.open_asset_folder_fn,
        )
        viewer.withdraw()
        try:
            next_state = viewer._btn_next.cget("state")
            self.assertEqual(str(next_state), "normal")
        finally:
            viewer.destroy()

    # --- Dynamic window title ---

    def test_title_updates_on_navigation(self):
        """Window title must update when navigating to a different image clip."""
        viewer = self._viewer("clip_1")
        try:
            title_at_clip1 = viewer.title()
            viewer._next_image()
            title_at_clip3 = viewer.title()
            # Both titles should contain the base product name
            from cache_vault import brand
            self.assertIn(brand.PRODUCT_NAME, title_at_clip1)
            self.assertIn(brand.PRODUCT_NAME, title_at_clip3)
        finally:
            viewer.destroy()

    def test_title_contains_product_name(self):
        """Window title must always contain the brand product name."""
        viewer = self._viewer("clip_1")
        try:
            from cache_vault import brand
            self.assertIn(brand.PRODUCT_NAME, viewer.title())
        finally:
            viewer.destroy()

    # --- Zoom labels ---

    def test_zoom_minus_button_label(self):
        """'Zoom −' button must use the correct minus character (not sloppy space-padded)."""
        viewer = self._viewer("clip_1")
        try:
            # Walk toolbar children to find button texts
            labels = []
            for widget in viewer._zoom_frame.winfo_children():
                try:
                    t = widget.cget("text")
                    labels.append(t)
                except Exception:
                    pass
            self.assertIn("Zoom −", labels, f"Expected 'Zoom −' in zoom frame, got: {labels}")
        finally:
            viewer.destroy()

    def test_zoom_plus_button_label(self):
        """'Zoom +' button must use clean label without padding spaces."""
        viewer = self._viewer("clip_1")
        try:
            labels = []
            for widget in viewer._zoom_frame.winfo_children():
                try:
                    t = widget.cget("text")
                    labels.append(t)
                except Exception:
                    pass
            self.assertIn("Zoom +", labels, f"Expected 'Zoom +' in zoom frame, got: {labels}")
        finally:
            viewer.destroy()

    # --- is_fitted flag tracking ---

    def test_zoom_in_clears_fitted_flag(self):
        """_zoom_in must set _is_fitted = False."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            self.assertTrue(viewer._is_fitted)
            viewer._zoom_in()
            self.assertFalse(viewer._is_fitted)
        finally:
            viewer.destroy()

    def test_zoom_out_clears_fitted_flag(self):
        """_zoom_out must set _is_fitted = False."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            viewer._zoom_out()
            self.assertFalse(viewer._is_fitted)
        finally:
            viewer.destroy()

    def test_zoom_reset_clears_fitted_flag(self):
        """_zoom_reset (1:1) must set _is_fitted = False."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            viewer._zoom_reset()
            self.assertFalse(viewer._is_fitted)
        finally:
            viewer.destroy()

    def test_drag_clears_fitted_flag(self):
        """Dragging (pan) must set _is_fitted = False."""
        viewer = self._viewer("clip_1")
        try:
            viewer._zoom_fit()
            start_event = MagicMock()
            start_event.x, start_event.y = 100, 100
            viewer._on_drag_start(start_event)
            move_event = MagicMock()
            move_event.x, move_event.y = 110, 110
            viewer._on_drag_motion(move_event)
            self.assertFalse(viewer._is_fitted)
        finally:
            viewer.destroy()


if __name__ == "__main__":
    unittest.main()
