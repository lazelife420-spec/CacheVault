"""Regression tests for dialog windows — sizing, layout, and behaviour."""

from __future__ import annotations

import pytest

try:
    import customtkinter as ctk
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

# Still need the guard for headless CI where Tk can import but fail to init.
if _HAS_DISPLAY:
    try:
        _root = ctk.CTk()
        _root.destroy()
    except Exception:
        _HAS_DISPLAY = False


pytestmark = pytest.mark.skipif(not _HAS_DISPLAY, reason="requires a display")


class TestSettingsDialog:
    def test_default_geometry_prevents_button_clipping(self):
        """The default height must be tall enough for all controls + Save button."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        # CustomTkinter stores the requested geometry internally; check
        # those values directly to avoid window-mapping side effects.
        assert dialog._current_width == 420, (
            f"expected width 420, got {dialog._current_width}"
        )
        assert dialog._current_height >= 460, (
            f"Settings dialog requested height is {dialog._current_height}px; "
            f"expected >= 460px to prevent Save-button clipping "
            f"under display scaling"
        )

        dialog.destroy()
        root.destroy()

    def test_dialog_is_vertically_resizable(self):
        """Users must be able to grow the dialog taller if needed."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        # Tk resizable() returns (0|1, 0|1) — use equality, not identity.
        can_resize_w, can_resize_h = dialog.resizable()
        assert can_resize_h == 1, (
            f"Settings dialog should be vertically resizable; got {dialog.resizable()}"
        )

        dialog.destroy()
        root.destroy()

    def test_minimum_size_enforced(self):
        """The dialog must not shrink below a usable minimum."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        # CTkToplevel.minsize() is setter-only; read the backing attrs.
        assert dialog._min_width == 420, (
            f"expected min width 420, got {dialog._min_width}"
        )
        assert dialog._min_height == 420, (
            f"expected min height 420, got {dialog._min_height}"
        )

        dialog.destroy()
        root.destroy()
