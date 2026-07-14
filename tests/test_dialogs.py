"""Regression tests for dialog windows — sizing, layout, and behaviour."""

from __future__ import annotations

import inspect
import re

import customtkinter as ctk
import pytest


class TestSettingsDialog:
    def test_settings_dialog_declared_geometry(self):
        """Layout contract for Settings — no Tk required (CI-safe gate)."""
        from cache_vault.ui.dialogs import SettingsDialog

        src = inspect.getsource(SettingsDialog.__init__)
        assert re.search(r'geometry\s*\(\s*["\"]520x720["\"]\s*\)', src), (
            "Settings dialog must declare geometry 520x720"
        )
        assert re.search(r'minsize\s*\(\s*520\s*,\s*540\s*\)', src), (
            "Settings dialog must enforce minsize 520x540"
        )
        assert re.search(r'resizable\s*\(\s*False\s*,\s*True\s*\)', src), (
            "Settings dialog must be vertically resizable"
        )
        assert "Capture Rules" in src, (
            "Settings must include Capture Rules section"
        )
        assert "Keyboard Shortcuts" in src, (
            "Settings must include Keyboard Shortcuts section"
        )
        assert "Save to Vault" in src, (
            "Settings must label manual save as Save to Vault"
        )
        assert "Quick Paste menu" in src, (
            "Settings must label quick paste hotkey clearly"
        )
        assert "Manage Safes" in src, (
            "Settings must expose Manage Safes control"
        )

    def test_default_geometry_prevents_button_clipping(self, tk_root):
        """The default height must be tall enough for all controls + footer."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

        assert dialog._current_width == 520, (
            f"expected width 520, got {dialog._current_width}"
        )
        assert dialog._current_height >= 720, (
            f"Settings dialog requested height is {dialog._current_height}px; "
            f"expected >= 720px to prevent footer clipping under display scaling"
        )

        dialog.destroy()

    def test_dialog_is_vertically_resizable(self, tk_root):
        """Users must be able to grow the dialog taller if needed."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

        can_resize_w, can_resize_h = dialog.resizable()
        assert can_resize_h == 1, (
            f"Settings dialog should be vertically resizable; got {dialog.resizable()}"
        )

        dialog.destroy()

    def test_minimum_size_enforced(self, tk_root):
        """The dialog must not shrink below a usable minimum."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

        assert dialog._min_width == 520, (
            f"expected min width 520, got {dialog._min_width}"
        )
        assert dialog._min_height == 540, (
            f"expected min height 540, got {dialog._min_height}"
        )

        dialog.destroy()

    def test_footer_has_save_and_cancel(self, tk_root):
        """The fixed footer must expose Save and Cancel buttons at all times."""
        import customtkinter as ctk

        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

        children = dialog.winfo_children()
        assert len(children) >= 3, (
            f"expected >= 3 top-level children (title, body, footer), got {len(children)}"
        )

        footer = None
        for child in children:
            if isinstance(child, ctk.CTkFrame) and not isinstance(child, ctk.CTkScrollableFrame):
                texts = {b.cget("text") for b in child.winfo_children() if isinstance(b, ctk.CTkButton)}
                if "Save" in texts and "Cancel" in texts:
                    footer = child
                    break
                    
        assert footer is not None, "Footer frame not found"
        buttons = [w for w in footer.winfo_children()
                   if isinstance(w, ctk.CTkButton)]
        button_texts = {b.cget("text") for b in buttons}
        assert button_texts == {"Save", "Cancel"}, (
            f"footer buttons should be {{Save, Cancel}}, got {button_texts}"
        )

        dialog.destroy()

    def test_content_is_scrollable(self, tk_root):
        """The settings fields must live inside a scrollable frame."""
        import customtkinter as ctk

        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

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

    def test_mobile_section_pinned_before_history(self, tk_root):
        """Mobile Access must sit above the scroll area, before History."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(
            tk_root, Settings(), on_save=lambda s: None,
            mobile={"pair": lambda on: None, "devices": lambda: None,
                    "receipts": lambda: None},
        )
        dialog.update_idletasks()

        assert hasattr(dialog, "_mobile_section"), "expected pinned Mobile Access card"
        assert dialog._mobile_section.master is dialog

        def _toplevel_owner(widget):
            parent = widget
            while parent.master is not dialog and parent.master is not None:
                parent = parent.master
            return parent

        scroll_owner = _toplevel_owner(dialog._scroll_body)
        assert scroll_owner.master is dialog

        children = list(dialog.winfo_children())
        mobile_idx = children.index(dialog._mobile_section)
        scroll_idx = children.index(scroll_owner)
        assert mobile_idx < scroll_idx, (
            "Mobile Access card must appear before the scrollable body"
        )

        def _labels_in(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    texts.append(child.cget("text"))
                texts.extend(_labels_in(child))
            return texts

        scroll_labels = _labels_in(dialog._scroll_body)
        assert "History" in scroll_labels
        assert "Mobile Access" not in scroll_labels, (
            "Mobile Access must not live inside the scrollable History section"
        )

        dialog.destroy()

    def test_mobile_buttons_present_when_wired(self, tk_root):
        """Pairing controls must be visible in the pinned Mobile Access card."""
        from cache_vault import brand
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(
            tk_root, Settings(), on_save=lambda s: None,
            mobile={"pair": lambda on: None, "devices": lambda: None,
                    "receipts": lambda: None},
        )
        dialog.update_idletasks()

        def _button_texts(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    texts.append(child.cget("text"))
                texts.extend(_button_texts(child))
            return texts

        mobile_buttons = set(_button_texts(dialog._mobile_section))
        assert mobile_buttons == {
            "Connect Phone",
            "Pair Android Device",
            "Paired Devices",
            brand.TERM_MOBILE_ACCESS_RECEIPTS,
        }

        dialog.destroy()

    def test_mobile_access_off_by_default(self, tk_root):
        """Enable Mobile Access must start unchecked."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)

        assert dialog._mobile_on.get() == 0

        dialog.destroy()

    def test_pair_android_button_invokes_callback(self, tk_root):
        """Pair Android Device must call the supplied pair callback."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        calls: list[bool] = []

        dialog = SettingsDialog(
            tk_root, Settings(), on_save=lambda s: None,
            mobile={"pair": lambda on: calls.append(on)},
        )
        dialog.update_idletasks()

        def _find_pair_button(widget):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton) and child.cget("text") == "Pair Android Device":
                    return child
                found = _find_pair_button(child)
                if found is not None:
                    return found
            return None

        pair_btn = _find_pair_button(dialog._mobile_section)
        assert pair_btn is not None
        pair_btn.invoke()
        assert calls == [False]

        dialog.destroy()

    def test_keyboard_shortcuts_show_status_labels(self, tk_root):
        """Each shortcut row should expose a live status label."""
        from cache_vault.core.settings import Settings
        from cache_vault.ui.dialogs import SettingsDialog

        dialog = SettingsDialog(tk_root, Settings(), on_save=lambda s: None)
        dialog.update_idletasks()

        assert set(dialog._hk_entries) == {
            "manual_save", "arm_next", "ignore_next", "quick_paste", "macro_menu",
        }
        for role in dialog._hk_entries:
            status = dialog._hk_status[role].cget("text")
            assert status.startswith("Ready ·"), f"{role} status: {status!r}"

        dialog._manual_hk.delete(0, "end")
        dialog._manual_hk.insert(0, dialog._hotkey.get())
        dialog._refresh_hotkey_statuses()
        assert "Same shortcut" in dialog._hk_status["manual_save"].cget("text")

        dialog.destroy()
