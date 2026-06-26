
import pytest
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.core.storage import FILTER_ALL, FILTER_SEARCH_ALL
from cache_vault.ui.filters import NAV_SETTINGS, NAV_STAMPED_RECEIPTS
from tests.tk_support import probe_tk_ui, _tcl_unavailable  # noqa: PLC2701

OK, REASON = probe_tk_ui()


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


@pytest.mark.skipif(not OK, reason=REASON)
class TestNavigation:
    def test_navigation_history_push(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        
        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        app = _make_app(vault)
        try:
            app.withdraw()
            
            # Initial screen is S.FILTER_HOME ('home')
            assert app._filters.active == S.FILTER_HOME
            
            # Navigate to All Clips
            app._navigate_screen(S.FILTER_ALL)
            assert app._filters.active == S.FILTER_ALL
            assert app._nav_history == [S.FILTER_HOME]
            
            # Navigate to Settings
            app._navigate_screen(NAV_SETTINGS)
            assert app._nav_history == [S.FILTER_HOME, S.FILTER_ALL]
            assert app._nav_forward_stack == []
            
            # Navigate to Receipts
            app._navigate_screen(NAV_STAMPED_RECEIPTS)
            assert app._nav_history == [S.FILTER_HOME, S.FILTER_ALL, NAV_SETTINGS]
        finally:
            app.destroy()

    def test_navigation_back_forward(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        
        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        app = _make_app(vault)
        try:
            app.withdraw()
            app._nav_history = [] # Reset for easier testing
            
            app._navigate_screen(S.FILTER_ALL)
            app._navigate_screen(NAV_STAMPED_RECEIPTS)
            app._navigate_screen(NAV_SETTINGS)
            
            # Current: SETTINGS, History: [HOME, ALL, RECEIPTS]
            assert app._filters.active == NAV_SETTINGS
            assert app._nav_history == [S.FILTER_HOME, S.FILTER_ALL, NAV_STAMPED_RECEIPTS]
            
            # Back
            app._navigate_back()
            assert app._filters.active == NAV_STAMPED_RECEIPTS
            assert app._nav_history == [S.FILTER_HOME, S.FILTER_ALL]
            assert app._nav_forward_stack == [NAV_SETTINGS]
            
            # Back again
            app._navigate_back()
            assert app._filters.active == S.FILTER_ALL
            assert app._nav_history == [S.FILTER_HOME]
            assert app._nav_forward_stack == [NAV_SETTINGS, NAV_STAMPED_RECEIPTS]
            
            # Back again (to Home)
            app._navigate_back()
            assert app._filters.active == S.FILTER_HOME
            assert app._nav_history == []
            assert app._nav_forward_stack == [NAV_SETTINGS, NAV_STAMPED_RECEIPTS, S.FILTER_ALL]

            # Forward
            app._navigate_forward()
            assert app._filters.active == S.FILTER_ALL
            assert app._nav_history == [S.FILTER_HOME]
        finally:
            app.destroy()

    def test_escape_clears_search(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        
        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        app = _make_app(vault)
        try:
            app.withdraw()
            
            app._search_var.set("test search")
            app._on_escape_pressed()
            assert app._search_var.get() == ""
        finally:
            app.destroy()

    def test_back_with_empty_history_is_safe(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        
        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        app = _make_app(vault)
        try:
            app.withdraw()
            
            app._nav_history = []
            app._navigate_back() # Should not crash
        finally:
            app.destroy()
