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
        """The default height must be tall enough for all controls + footer."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        assert dialog._current_width == 440, (
            f"expected width 440, got {dialog._current_width}"
        )
        assert dialog._current_height >= 560, (
            f"Settings dialog requested height is {dialog._current_height}px; "
            f"expected >= 560px to prevent footer clipping under display scaling"
        )

        dialog.destroy()
        root.destroy()

    def test_dialog_is_vertically_resizable(self):
        """Users must be able to grow the dialog taller if needed."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

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

        assert dialog._min_width == 440, (
            f"expected min width 440, got {dialog._min_width}"
        )
        assert dialog._min_height == 360, (
            f"expected min height 360, got {dialog._min_height}"
        )

        dialog.destroy()
        root.destroy()

    def test_footer_has_save_and_cancel(self):
        """The fixed footer must expose Save and Cancel buttons at all times."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        # Walk immediate children: title label, scrollable-frame, footer frame.
        children = dialog.winfo_children()
        assert len(children) >= 3, (
            f"expected >= 3 top-level children (title, body, footer), got {len(children)}"
        )

        # The footer frame should be the last child and contain two buttons.
        footer = children[-1]
        buttons = [w for w in footer.winfo_children()
                   if isinstance(w, ctk.CTkButton)]
        button_texts = {b.cget("text") for b in buttons}
        assert button_texts == {"Save", "Cancel"}, (
            f"footer buttons should be {{Save, Cancel}}, got {button_texts}"
        )

        dialog.destroy()
        root.destroy()

    def test_content_is_scrollable(self):
        """The settings fields must live inside a scrollable frame."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        root = ctk.CTk()
        dialog = SettingsDialog(root, Settings(), on_save=lambda s: None)

        # Walk the widget tree to find a CTkScrollableFrame anywhere.
        def _find_scrollable(w):
            if isinstance(w, ctk.CTkScrollableFrame):
                return True
            for child in w.winfo_children():
                if _find_scrollable(child):
                    return True
            return False

        assert _find_scrollable(dialog), (
            "Settings dialog must contain a CTkScrollableFrame for content"
        )

        dialog.destroy()
        root.destroy()
