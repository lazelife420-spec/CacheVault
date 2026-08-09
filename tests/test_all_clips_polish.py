"""Holistic All Clips surface checks.

These assertions keep the finished surface cohesive while allowing the
feature-specific tests to remain focused on their own behavior.
"""

from pathlib import Path

import pytest

import customtkinter as ctk

from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui import shell as shell_module
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import _tcl_unavailable, probe_tk_ui, wait_for_refresh


OK, REASON = probe_tk_ui()
_SHELL_SRC = Path(shell_module.__file__)


def test_all_clips_surface_has_one_cohesive_chrome_path():
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "_update_clip_surface_chrome" in src
    assert "_page_header.set_status_chips(chips)" in src
    assert 'secondary_text="Clear all…"' in src
    assert "sidebar_context.build_sidebar_invocation_context_for_window" in src


def test_all_clips_has_keyboard_search_entry_point():
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert '"<Control-l>"' in src
    assert '"<Control-L>"' in src
    assert "def _focus_clips_search" in src


def _make_app(tmp_path):
    vault = Vault(
        storage=VaultStorage(tmp_path / "vault.db"),
        settings=Settings(capture_paused=True),
    )
    for i in range(3):
        vault.capture(f"polish clip {i}", force=True)
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            vault.close()
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


@pytest.mark.skipif(not OK, reason=REASON)
def test_all_clips_header_reports_state_and_safe_clear_action(tmp_path):
    app = _make_app(tmp_path)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        app._do_refresh_sync()
        wait_for_refresh(app)
        app.update_idletasks()

        assert "3 clips" == app._page_header._subtitle_label.cget("text")
        assert [
            child.cget("text")
            for child in app._page_header._status_frame.winfo_children()
        ] == ["Active clips", "View: Cards"]
        assert [
            child.cget("text")
            for child in app._page_header._actions_frame.winfo_children()
        ] == ["Clear all…"]
    finally:
        app.destroy()
