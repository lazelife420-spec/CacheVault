"""Integration tests for Settings Hub and Shell fallback."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from cache_vault.core.settings import Settings
from cache_vault.core.vault import Vault
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.ui.settings_hub import SettingsHub
from cache_vault.ui.dialogs import SettingsDialog
from tk_support import probe_tk_ui

# Check if UI tests can run in this environment
TK_OK, TK_REASON = probe_tk_ui()


class TestSettingsHubIntegration(unittest.TestCase):
    def setUp(self):
        if not TK_OK:
            self.skipTest(TK_REASON)
        
        # We need a real-ish vault for the app because it accesses .storage etc.
        self.vault = MagicMock(spec=Vault)
        self.vault.settings = Settings()
        self.vault.storage = MagicMock()
        self.vault.events = MagicMock()
        
        # Patch some heavy initializers to speed up or avoid side effects
        with patch('cache_vault.ui.shell.ClipboardMonitor'), \
             patch('cache_vault.ui.shell.HotkeyListener'), \
             patch('cache_vault.ui.shell.MultiHotkeyListener'), \
             patch('cache_vault.ui.shell.TrayController'), \
             patch('cache_vault.ui.shell.install_mouse_handler'), \
             patch('cache_vault.ui.shell.install_windows_scroll_patch'), \
             patch('cache_vault.ui.shell.CacheVaultApp._apply_window_icon'), \
             patch('cache_vault.ui.shell.CacheVaultApp.refresh'):
            self.app = CacheVaultApp(vault=self.vault)
            self.app.withdraw()

    def tearDown(self):
        try:
            if hasattr(self, "app"):
                self.app.destroy()
        except Exception:
            pass

    def test_open_settings_prefers_hub(self):
        """Verify that _open_settings opens once and reuses the existing hub."""
        hub_window = MagicMock()
        hub_window.winfo_exists.return_value = True
        with patch('cache_vault.ui.shell.SettingsHub', return_value=hub_window) as mock_hub:
            self.app._open_settings()
            self.assertIs(self.app._settings_window, hub_window)
            self.app._open_settings()
        mock_hub.assert_called_once()
        self.assertEqual(hub_window.present.call_count, 2)

    def test_open_settings_close_clears_reference(self):
        """Verify the shell forgets the hub when the window closes."""
        hub_window = MagicMock()
        hub_window.winfo_exists.return_value = True
        with patch('cache_vault.ui.shell.SettingsHub', return_value=hub_window) as mock_hub:
            self.app._open_settings()
        on_close = mock_hub.call_args.kwargs["on_close"]
        on_close(hub_window)
        self.assertIsNone(self.app._settings_window)

    def test_open_settings_recreates_window_after_destroy(self):
        """Verify a destroyed hub does not block opening a fresh one."""
        first_window = MagicMock()
        second_window = MagicMock()
        first_window.winfo_exists.return_value = False
        second_window.winfo_exists.return_value = True
        with patch(
            'cache_vault.ui.shell.SettingsHub',
            side_effect=[first_window, second_window],
        ) as mock_hub:
            self.app._open_settings()
            self.app._open_settings()
        self.assertEqual(mock_hub.call_count, 2)
        self.assertIs(self.app._settings_window, second_window)
        second_window.present.assert_called_once()

    def test_open_settings_fallback_on_construction_failure(self):
        """Verify fallback to SettingsDialog if SettingsHub construction fails."""
        # Simulate construction failure (e.g. missing registry or internal error)
        with patch('cache_vault.ui.shell.SettingsHub', side_effect=Exception("Hub crash")), \
             patch('cache_vault.ui.shell.SettingsDialog') as mock_dialog:
            self.app._open_settings()
            mock_dialog.assert_called_once()

    def test_open_settings_fallback_on_import_failure(self):
        """Verify fallback to SettingsDialog if SettingsHub cannot be imported."""
        # We simulate this by patching the SettingsHub class in the shell module to None
        with patch('cache_vault.ui.shell.SettingsHub', None), \
             patch('cache_vault.ui.shell.SettingsDialog') as mock_dialog:
            self.app._open_settings()
            mock_dialog.assert_called_once()


if __name__ == "__main__":
    unittest.main()
