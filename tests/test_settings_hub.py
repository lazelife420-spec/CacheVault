"""Tests for the Settings Hub UI skeleton."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from cache_vault import brand
from cache_vault.core.settings import Settings
from cache_vault.modules.registry import build_default_registry
from cache_vault.ui.settings_hub import SettingsHub
from tk_support import _tcl_unavailable, probe_tk_ui

# Check if UI tests can run in this environment
TK_OK, TK_REASON = probe_tk_ui()


def _find_all(widget, widget_type):
    """Recursively collect all descendant widgets of ``widget_type``."""
    found = []
    for child in widget.winfo_children():
        if isinstance(child, widget_type):
            found.append(child)
        found.extend(_find_all(child, widget_type))
    return found


def _wait_viewable(widget, timeout: float = 2.0) -> None:
    """Pump the Tk event loop until ``widget`` is actually mapped.

    CTkToplevel briefly withdraws itself on Windows while applying the
    dark-titlebar attribute, then reverts via a deferred callback; a single
    ``update()`` right after construction is not enough to observe the
    window as viewable/focusable, which real keyboard-event tests need.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        widget.update()
        if widget.winfo_viewable():
            return
        time.sleep(0.02)


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

    def test_present_uses_owned_raise_helper(self):
        """Verify the hub schedules a delayed raise tied to the main window."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        with patch.object(hub, "transient") as mock_transient, \
             patch.object(hub, "after", return_value="raise-job") as mock_after:
            hub.present()
        mock_transient.assert_called_once_with(self.root)
        mock_after.assert_called_once()
        self.assertEqual(hub._present_job, "raise-job")
        hub.destroy()

    def test_destroy_clears_pending_present_and_notifies_once(self):
        """Verify closing cancels delayed raise work and clears the owner once."""
        on_close = MagicMock()
        hub = SettingsHub(
            self.root,
            self.settings,
            self.registry,
            self.on_save,
            on_close=on_close,
        )
        hub._present_job = "raise-job"
        with patch.object(hub, "after_cancel") as mock_after_cancel:
            hub.destroy()
        mock_after_cancel.assert_called_once_with("raise-job")
        on_close.assert_called_once_with(hub)

    def test_category_rendering(self):
        """Verify that categories from the registry appear in the sidebar."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        
        # Check that category buttons were created
        categories = self.registry.settings_categories()
        # Find all buttons in the category list scrollable frame
        buttons = [w for w in hub._category_list.winfo_children() if isinstance(w, ctk.CTkButton)]
        
        self.assertEqual(len(buttons), len(categories))
        hub.destroy()

    def test_status_row_without_action_renders_no_button(self):
        """StatusRow.action=None (the default) draws no button — matches
        pre-12A behavior exactly (see CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS
        _AUDIT_2026-07-03.md, Q3/Q4)."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("mobile_bridge")
        buttons = _find_all(hub._settings_scroll, ctk.CTkButton)
        self.assertEqual(buttons, [])
        hub.destroy()

    def test_status_row_action_renders_and_invokes_button(self):
        """12A: a StatusRow with .action set draws a real button that calls
        it, for each of the three wired Mobile Bridge actions."""
        pair = MagicMock()
        devices = MagicMock()
        receipts = MagicMock()
        registry = build_default_registry(
            mobile_pair_action=pair,
            mobile_devices_action=devices,
            mobile_receipts_action=receipts,
        )
        hub = SettingsHub(self.root, self.settings, registry, self.on_save)
        hub._select_category("mobile_bridge")

        buttons_by_text = {
            b.cget("text"): b for b in _find_all(hub._settings_scroll, ctk.CTkButton)
        }
        expected_labels = {
            "Pair Android Device": pair,
            "Paired Devices": devices,
            brand.TERM_MOBILE_ACCESS_RECEIPTS: receipts,
        }
        self.assertEqual(set(buttons_by_text), set(expected_labels))
        for label, mock in expected_labels.items():
            buttons_by_text[label].cget("command")()
            mock.assert_called_once()
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

    def test_excluded_apps_renders_as_textarea(self):
        """excluded_apps is list[str]; it must render as a multi-line
        CTkTextbox (one app per line), not a single-line CTkEntry showing
        a raw Python list repr (the real-controls audit's fake-control
        finding)."""
        self.settings.excluded_apps = ["notepad.exe", "chrome.exe"]
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("capture")

        var, widget = hub._field_bindings["excluded_apps"]
        self.assertIsInstance(widget, ctk.CTkTextbox)
        self.assertEqual(widget.get("1.0", "end-1c"), "notepad.exe\nchrome.exe")
        hub.destroy()

    def test_excluded_apps_collect_saves_edits(self):
        """Editing the excluded_apps textarea and saving must actually
        persist the new list -- previously _collect_settings() silently
        discarded any edit to a list-typed field."""
        self.settings.excluded_apps = ["notepad.exe"]
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("capture")

        _var, widget = hub._field_bindings["excluded_apps"]
        widget.delete("1.0", "end")
        widget.insert("1.0", "foo.exe\n\n  bar.exe  \nnotepad.exe\n")
        hub._sync_list_textarea("excluded_apps", widget)

        new_settings = hub._collect_settings()
        self.assertEqual(
            new_settings.excluded_apps, ["foo.exe", "bar.exe", "notepad.exe"]
        )
        hub.destroy()

    def test_excluded_apps_collect_handles_empty_textarea(self):
        """Clearing every line must save an empty list, not keep the old
        one and not crash on blank/whitespace-only lines."""
        self.settings.excluded_apps = ["notepad.exe"]
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("capture")

        _var, widget = hub._field_bindings["excluded_apps"]
        widget.delete("1.0", "end")
        hub._sync_list_textarea("excluded_apps", widget)

        new_settings = hub._collect_settings()
        self.assertEqual(new_settings.excluded_apps, [])
        hub.destroy()

    def test_excluded_apps_preserved_across_category_switch(self):
        """Category switches destroy and recreate every field widget; the
        in-progress textarea edit must survive that (and must not crash
        _collect_settings(), which calls .get() on every ever-rendered
        binding regardless of which category is currently shown)."""
        self.settings.excluded_apps = ["notepad.exe"]
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("capture")

        _var, widget = hub._field_bindings["excluded_apps"]
        widget.delete("1.0", "end")
        widget.insert("1.0", "foo.exe\nbar.exe")
        hub._sync_list_textarea("excluded_apps", widget)

        hub._select_category("general")  # destroys the capture-tab widgets
        # Must not raise even though the old textbox widget is now gone.
        new_settings_mid_switch = hub._collect_settings()
        self.assertEqual(
            new_settings_mid_switch.excluded_apps, ["foo.exe", "bar.exe"]
        )

        hub._select_category("capture")
        _var2, widget2 = hub._field_bindings["excluded_apps"]
        self.assertEqual(widget2.get("1.0", "end-1c"), "foo.exe\nbar.exe")
        hub.destroy()

    def test_other_text_fields_unaffected_by_textarea_change(self):
        """Plain str "text" fields (e.g. default_safe_id) must keep using
        a single-line CTkEntry; only list[str] fields switch to a
        textarea."""
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save)
        hub._select_category("capture")

        _var, widget = hub._field_bindings["default_safe_id"]
        self.assertIsInstance(widget, ctk.CTkEntry)
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


class _KeyEvent:
    def __init__(self, keysym: str):
        self.keysym = keysym


class TestSettingsHubHotkeyRecorder(unittest.TestCase):
    """The Settings Hub hotkey fields use the shared DialogHotkeyRecorder."""

    @classmethod
    def setUpClass(cls):
        if not TK_OK:
            raise unittest.SkipTest(TK_REASON)
        ctk.set_appearance_mode("dark")
        # One shared root per class keeps Tcl-interpreter churn low; CTk()
        # can transiently fail on CI runner images, so skip (not fail) then.
        try:
            cls.root = ctk.CTk()
        except Exception as exc:  # noqa: BLE001 - transient Tcl runtime flake
            if _tcl_unavailable(exc):
                raise unittest.SkipTest(f"Tk/CTk runtime unavailable: {exc}")
            raise
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        root = getattr(cls, "root", None)
        if root is not None:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass

    def setUp(self):
        self.settings = Settings()
        self.registry = build_default_registry()
        self.on_save = MagicMock()
        self._hubs = []

    def tearDown(self):
        for hub in self._hubs:
            try:
                if hub.winfo_exists():
                    hub.destroy()
            except Exception:  # noqa: BLE001
                pass

    def _hub(self, category_id: str | None = None):
        hub = SettingsHub(self.root, self.settings, self.registry, self.on_save, category_id=category_id)
        if category_id is None:
            hub._select_category("shortcuts")
        self._hubs.append(hub)
        return hub

    def _recorder_for(self, hub, key):
        _var, entry = hub._field_bindings[key]
        for rec in hub._active_recorders:
            if rec._entry is entry:
                return rec
        return None

    def test_hotkey_field_has_recorder(self):
        hub = self._hub()
        self.assertTrue(hub._active_recorders)
        self.assertIsNotNone(self._recorder_for(hub, "manual_save_hotkey"))
        hub.destroy()

    def test_record_writes_combo_into_field(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "quick_paste_hotkey")
        _var, entry = hub._field_bindings["quick_paste_hotkey"]
        rec.toggle()
        self.assertTrue(rec.recording)
        rec._on_key_press(_KeyEvent("Control_L"))
        rec._on_key_press(_KeyEvent("b"))
        self.assertEqual(entry.get(), "ctrl+b")
        self.assertFalse(rec.recording)
        hub.destroy()

    def test_escape_cancels_without_recording_esc(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "manual_save_hotkey")
        _var, entry = hub._field_bindings["manual_save_hotkey"]
        before = entry.get()
        rec.toggle()
        rec._on_key_press(_KeyEvent("Escape"))
        self.assertFalse(rec.recording)
        self.assertEqual(entry.get(), before)
        self.assertNotIn("esc", entry.get().lower())
        hub.destroy()

    def test_retry_after_cancel_records(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "manual_save_hotkey")
        _var, entry = hub._field_bindings["manual_save_hotkey"]
        rec.toggle()
        rec._on_key_press(_KeyEvent("Escape"))
        rec.toggle()
        rec._on_key_press(_KeyEvent("Control_L"))
        rec._on_key_press(_KeyEvent("j"))
        self.assertEqual(entry.get(), "ctrl+j")
        self.assertFalse(rec.recording)
        hub.destroy()

    def test_duplicate_hotkey_blocks_save(self):
        hub = self._hub()
        var_manual, _ = hub._field_bindings["manual_save_hotkey"]
        var_arm, _ = hub._field_bindings["arm_next_copy_hotkey"]
        var_arm.set(var_manual.get())
        hub._save()
        self.on_save.assert_not_called()
        self.assertTrue(hub._save_error.cget("text"))
        hub.destroy()

    def test_valid_hotkeys_allow_save(self):
        hub = self._hub()
        hub._save()
        self.on_save.assert_called_once()

    def test_close_while_recording_is_safe(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "manual_save_hotkey")
        rec.toggle()
        self.assertTrue(rec.recording)
        hub.destroy()  # must not raise

    def test_category_switch_tears_down_recorders(self):
        hub = self._hub()
        self.assertTrue(hub._active_recorders)
        hub._select_category("general")
        self.assertEqual(hub._active_recorders, [])
        hub.destroy()

    def test_real_keypress_dispatch_captures_combo(self):
        """Regression test for the focus-only capture bug: drive the real
        Tk event pipeline (event_generate) instead of calling
        ``_on_key_press`` directly, so a bindtag/focus regression would
        actually be caught here.
        """
        hub = self._hub()
        rec = self._recorder_for(hub, "quick_paste_hotkey")
        _var, entry = hub._field_bindings["quick_paste_hotkey"]
        _wait_viewable(hub)
        try:
            rec.toggle()
            hub.update()
            entry.event_generate("<KeyPress>", keysym="Control_L")
            hub.update()
            entry.event_generate("<KeyPress>", keysym="b")
            hub.update()
            self.assertEqual(entry.get(), "ctrl+b")
            self.assertFalse(rec.recording)
            # Grab must not still be held by the hub once capture completes,
            # regardless of whether grab_set() actually succeeded on this
            # environment/display (see _release_grab: releasing an unowned
            # grab is a no-op, so this holds either way).
            self.assertNotEqual(str(hub.grab_current()), str(hub))
        finally:
            hub.withdraw()
            hub.destroy()

    def test_numpad_digit_keysym_with_numpad_keycode(self):
        """Windows often reports keysym '2' for numpad — keycode disambiguates."""
        hub = self._hub()
        rec = self._recorder_for(hub, "quick_paste_hotkey")
        _var, entry = hub._field_bindings["quick_paste_hotkey"]
        _wait_viewable(hub)
        try:
            rec.toggle()
            hub.update()
            entry.event_generate("<KeyPress>", keysym="Control_L")
            hub.update()
            entry.event_generate("<KeyPress>", keysym="2", keycode=98)
            hub.update()
            self.assertEqual(entry.get(), "ctrl+num2")
            self.assertFalse(rec.recording)
        finally:
            hub.withdraw()
            hub.destroy()

    def test_top_row_digit_keycode_stays_top_row(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "quick_paste_hotkey")
        _var, entry = hub._field_bindings["quick_paste_hotkey"]
        _wait_viewable(hub)
        try:
            rec.toggle()
            hub.update()
            entry.event_generate("<KeyPress>", keysym="Control_L")
            hub.update()
            entry.event_generate("<KeyPress>", keysym="2", keycode=50)
            hub.update()
            self.assertEqual(entry.get(), "ctrl+2")
        finally:
            hub.withdraw()
            hub.destroy()

    def test_recording_grab_released_on_cancel(self):
        hub = self._hub()
        rec = self._recorder_for(hub, "manual_save_hotkey")
        _wait_viewable(hub)
        try:
            rec.toggle()
            hub.update()
            rec.stop(cancelled=True)
            self.assertFalse(rec.recording)
            self.assertNotEqual(str(hub.grab_current()), str(hub))
        finally:
            hub.withdraw()
            hub.destroy()


    def test_category_deep_linking(self):
        # Category ID "shortcuts" should be selected
        hub = self._hub(category_id="shortcuts")
        _wait_viewable(hub)
        try:
            self.assertEqual(hub._selected_category_id, "shortcuts")
        finally:
            hub.withdraw()
            hub.destroy()

        # Invalid category ID should fallback to default first category ("general")
        hub2 = self._hub(category_id="nonexistent_category")
        _wait_viewable(hub2)
        try:
            self.assertEqual(hub2._selected_category_id, "general")
        finally:
            hub2.withdraw()
            hub2.destroy()


if __name__ == "__main__":
    unittest.main()
