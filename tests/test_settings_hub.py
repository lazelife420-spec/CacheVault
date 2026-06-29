"""Tests for the Settings Hub UI skeleton."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import customtkinter as ctk

from cache_vault.core.settings import Settings
from cache_vault.modules.registry import build_default_registry
from cache_vault.ui.settings_hub import SettingsHub
from tk_support import probe_tk_ui

# Check if UI tests can run in this environment
TK_OK, TK_REASON = probe_tk_ui()


class TestSettingsHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize CTk for headless testing if possible
        ctk.set_appearance_mode("dark")

    def setUp(self):
        if not TK_OK:
            self.skipTest(TK_REASON)
        self.root = ctk.CTk()
        self.root.withdraw()  # Don't show the main window
        self.settings = Settings()
        self.registry = build_default_registry()
        self.on_save = MagicMock()

    def tearDown(self):
        try:
            if hasattr(self, "root"):
                self.root.destroy()
        except Exception:
            pass

    def test_settings_hub_construction(self):
        """Verify SettingsHub can be constructed without crashing."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        self.assertIsInstance(hub, SettingsHub)
        self.assertEqual(hub.title(), "Cache Vault™ — Settings Hub")
        hub.destroy()

    def test_category_rendering(self):
        """Verify that categories from the registry appear in the sidebar."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        
        # Check that category buttons were created
        categories = self.registry.settings_categories()
        # Find all buttons in the category list scrollable frame
        buttons = [w for w in hub._category_list.winfo_children() if isinstance(w, ctk.CTkButton)]
        
        self.assertEqual(len(buttons), len(categories))
        hub.destroy()

    def test_search_filtering(self):
        """Verify that search filters settings across categories."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        
        # Search for something known to exist, e.g., "mobile"
        hub._search_var.set("mobile")
        # Trace might not fire instantly in tests without mainloop, call handler manually
        hub._on_search_change()
        
        # Check that we are rendering search results
        # We look for labels in the settings scroll area
        labels = [w.cget("text") for w in hub._settings_scroll.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertTrue(any("Search Results" in l for l in labels))
        self.assertTrue(any("Mobile Bridge" in l for l in labels))
        
        hub.destroy()

    def test_data_binding_collect(self):
        """Verify that _collect_settings gathers values from widgets."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        
        # The 'general' category is selected by default, which contains 'start_with_windows'
        key = "start_with_windows"
        self.assertIn(key, hub._field_bindings)
        var, widget = hub._field_bindings[key]
        
        if isinstance(widget, ctk.CTkSwitch):
            widget.select()
            # Ensure the variable is updated
            self.assertTrue(var.get())
                
        new_settings = hub._collect_settings()
        self.assertTrue(new_settings.start_with_windows)
        hub.destroy()

    def test_save_callback(self):
        """Verify that clicking Save triggers the on_save callback."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._save()
        self.on_save.assert_called_once()
        hub.destroy()

    def test_settings_round_trip(self):
        """Verify that settings can be modified and collected correctly."""
        # Start with default settings
        self.settings.auto_capture_enabled = True
        self.settings.history_max_clips = 100
        self.settings.manual_save_hotkey = "ctrl+shift+c"
        
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        
        # We need to select categories to ensure fields are rendered and bound
        hub._select_category("capture")
        hub._select_category("history")
        hub._select_category("shortcuts")
        
        # Modify some fields in the bindings
        # 1. Toggle
        var_auto, _ = hub._field_bindings["auto_capture_enabled"]
        var_auto.set(False)
        
        # 2. Number
        var_history, _ = hub._field_bindings["history_max_clips"]
        var_history.set("500")
        
        # 3. Hotkey
        var_hotkey, _ = hub._field_bindings["manual_save_hotkey"]
        var_hotkey.set("ctrl+alt+s")
        
        # Collect
        new_settings = hub._collect_settings()
        
        self.assertFalse(new_settings.auto_capture_enabled)
        self.assertEqual(new_settings.history_max_clips, 500)
        self.assertEqual(new_settings.manual_save_hotkey, "ctrl+alt+s")
        
        hub.destroy()


if __name__ == "__main__":
    unittest.main()
