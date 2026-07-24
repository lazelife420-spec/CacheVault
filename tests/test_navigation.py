
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

    def test_collection_active_label_shows_display_name_not_raw_key(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        clip = vault.capture("a note")
        vault.set_collection(clip.id, "My Collection")
        app = _make_app(vault)
        try:
            app.withdraw()

            # update_collections() is called during refresh(), which is what
            # actually populates _labels_text for dynamically created
            # collections -- calling it directly would skip the real
            # production wiring this bug lives in (shell.py's refresh path).
            app.refresh()
            wait_for_refresh(app)

            key = S.COLLECTION_PREFIX + "My Collection"
            app._navigate_screen(key)

            assert app._filters.active_label == "My Collection"
            assert app._filters.active_label != key
        finally:
            app.destroy()

    def test_collection_label_removed_when_collection_disappears(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
        clip = vault.capture("a note")
        vault.set_collection(clip.id, "Temp Collection")
        app = _make_app(vault)
        try:
            app.withdraw()
            app.refresh()
            wait_for_refresh(app)

            key = S.COLLECTION_PREFIX + "Temp Collection"
            assert app._filters._labels_text.get(key) == "Temp Collection"

            # Removing the clip from the collection makes it disappear from
            # list_collections(); a fresh refresh should drop the stale
            # label entry rather than leaving it around indefinitely.
            vault.set_collection(clip.id, None)
            app.refresh()
            wait_for_refresh(app)

            assert key not in app._filters._labels_text
        finally:
            app.destroy()

    def test_page_header_count_grammar_is_singular_for_one_clip(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        # This test verifies deterministic header-count grammar and must
        # not observe the host OS clipboard -- a real ClipboardMonitor
        # left active during wait_for_refresh's event pump can auto-capture
        # genuine external clipboard activity into this test's own vault,
        # making the count nondeterministic.
        vault = Vault(
            storage=VaultStorage(tmp_path / "vault.db"),
            settings=Settings(auto_capture_enabled=False, capture_paused=True),
        )
        vault.capture("only clip", force=True)
        app = _make_app(vault)
        try:
            app.withdraw()
            app._navigate_screen(S.FILTER_ALL)
            app._do_refresh_sync()
            wait_for_refresh(app)

            assert app._page_header._subtitle_label.cget("text") == "1 clip"
        finally:
            app.destroy()

    def test_page_header_count_grammar_is_plural_for_multiple_clips(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        # This test verifies deterministic header-count grammar and must
        # not observe the host OS clipboard -- a real ClipboardMonitor
        # left active during wait_for_refresh's event pump can auto-capture
        # genuine external clipboard activity into this test's own vault,
        # making the count nondeterministic.
        vault = Vault(
            storage=VaultStorage(tmp_path / "vault.db"),
            settings=Settings(auto_capture_enabled=False, capture_paused=True),
        )
        vault.capture("first clip", force=True)
        vault.capture("second clip", force=True)
        app = _make_app(vault)
        try:
            app.withdraw()
            app._navigate_screen(S.FILTER_ALL)
            app._do_refresh_sync()
            wait_for_refresh(app)

            assert app._page_header._subtitle_label.cget("text") == "2 clips"
        finally:
            app.destroy()

    def test_page_header_count_grammar_is_plural_for_zero_clips(self, tmp_path):
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        # This test verifies deterministic header-count grammar and must
        # not observe the host OS clipboard -- a real ClipboardMonitor
        # left active during wait_for_refresh's event pump can auto-capture
        # genuine external clipboard activity into this test's own vault,
        # making the count nondeterministic.
        vault = Vault(
            storage=VaultStorage(tmp_path / "vault.db"),
            settings=Settings(auto_capture_enabled=False, capture_paused=True),
        )
        app = _make_app(vault)
        try:
            app.withdraw()
            app._navigate_screen(S.FILTER_ALL)
            app._do_refresh_sync()
            wait_for_refresh(app)

            assert app._page_header._subtitle_label.cget("text") == "0 clips"
        finally:
            app.destroy()

    def test_page_header_count_tests_settings_leave_monitor_paused(self, tmp_path):
        """Regression guard for the auto-capture contamination bug: the
        count-grammar tests' settings (auto_capture_enabled=False,
        capture_paused=True) must leave the real ClipboardMonitor paused
        after construction. A monitor-start spy confirms the app still
        genuinely attempts to start the monitor thread (this isn't a
        skipped/no-op construction) while ending up paused."""
        from unittest.mock import patch
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core.clipboard import ClipboardMonitor

        vault = Vault(
            storage=VaultStorage(tmp_path / "vault.db"),
            settings=Settings(auto_capture_enabled=False, capture_paused=True),
        )
        with patch.object(
            ClipboardMonitor, "start", autospec=True, side_effect=ClipboardMonitor.start
        ) as start_spy:
            app = _make_app(vault)
        try:
            assert start_spy.called, (
                "Construction should still genuinely attempt to start the "
                "monitor thread -- this guard is about it ending up paused, "
                "not about skipping startup"
            )
            assert app._monitor.paused is True, (
                "The count tests' settings must leave the monitor paused so "
                "a started thread can never deliver a capture"
            )
        finally:
            app.destroy()

    def test_page_header_count_tests_event_pump_cannot_capture_external_clipboard_change(self, tmp_path):
        """Regression guard, directly reproducing the traced defect's
        mechanism without touching the real OS clipboard or logging any
        clipboard content: with a real (paused) ClipboardMonitor after a
        real Tk event-loop pump, a controlled fake external clipboard
        change must not reach the vault. Only a fixed placeholder string
        is used as the fake signal -- never real clipboard content."""
        from unittest.mock import patch
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.settings import Settings
        from cache_vault.core.vault import Vault
        from cache_vault.core import storage as S
        from tests.tk_support import wait_for_refresh

        vault = Vault(
            storage=VaultStorage(tmp_path / "vault.db"),
            settings=Settings(auto_capture_enabled=False, capture_paused=True),
        )
        app = _make_app(vault)
        try:
            app.withdraw()
            app._navigate_screen(S.FILTER_ALL)
            app._do_refresh_sync()
            wait_for_refresh(app)

            assert app._monitor.paused is True
            # Controlled fake: drive the monitor's real _emit() path (the
            # same one a live background thread calls on a genuine
            # clipboard change) with a fixed placeholder value standing in
            # for external content, instead of writing to the real
            # clipboard. If the pause guard is ever removed or bypassed,
            # this becomes a real captured clip and the count assertion
            # below fails.
            with patch(
                "cache_vault.core.clipboard._read_clipboard_text",
                return_value="PLACEHOLDER-SIMULATED-EXTERNAL-CLIPBOARD-CHANGE",
            ), patch("cache_vault.core.clipboard._read_clipboard_image", return_value=None):
                app._monitor._emit()

            # _on_clip_captured only queues the ingest via _call_on_main;
            # the actual storage write happens when _pump_main_thread next
            # drains that queue (normally via the Tk event loop's own
            # after(50, ...) schedule) -- give it that chance explicitly so
            # this test exercises the real end-to-end path, not just the
            # queuing half of it.
            app._pump_main_thread()

            assert vault.storage.count_clips() == 0, (
                "A simulated external clipboard change must not be captured "
                "into the vault while the monitor is paused, even after "
                "driving its real _emit() dispatch path"
            )
        finally:
            app.destroy()
