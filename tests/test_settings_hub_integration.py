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
        """Verify that _open_settings attempts to open SettingsHub first."""
        with patch('cache_vault.ui.shell.SettingsHub') as mock_hub:
            self.app._open_settings()
            mock_hub.assert_called_once()
            # Ensure SettingsDialog was NOT called if Hub succeeded
            with patch('cache_vault.ui.shell.SettingsDialog') as mock_dialog:
                self.app._open_settings()
                mock_dialog.assert_not_called()

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
