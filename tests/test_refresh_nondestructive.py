"""Non-destructive refresh + refreshing-indicator behavior.

Before this, refresh() destroyed every list/grid row synchronously (via
_show_loading_skeleton), before the 50ms debounce even fired -- i.e.
before any DB work started. That's what produced the reported "list goes
blank" symptom, independent of how long the subsequent DB work took.
refresh() must now leave existing content on screen (and _visible_clip_ids
unchanged) until a fresh snapshot has actually been applied, with only a
small non-blocking indicator signaling that a refresh is in flight.
"""

from __future__ import annotations

import pytest

from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import _tcl_unavailable, probe_tk_ui, wait_for_refresh

OK, REASON = probe_tk_ui()
pytestmark = pytest.mark.skipif(not OK, reason=REASON)


def _make_app(n_clips: int = 10):
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    for i in range(n_clips):
        vault.capture(f"clip {i}", force=True)
    try:
        app = CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable: {exc}")
        raise
    app.withdraw()
    return app


def test_refresh_leaves_visible_clips_untouched_before_debounce_fires():
    app = _make_app(10)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        before = list(app._visible_clip_ids)
        assert before, "precondition: something is actually shown"

        app.refresh()
        # No app.update() / wait here on purpose: this checks the state
        # immediately after refresh() returns, before the 50ms debounce
        # timer (let alone the worker thread) has had any chance to run.
        assert app._visible_clip_ids == before, (
            "refresh() must not clear rendered state before new data is ready"
        )
        assert len(app._list.winfo_children()) > 0 or len(app._grid.winfo_children()) > 0

        wait_for_refresh(app)
    finally:
        app.destroy()


def test_page_header_shows_refreshing_indicator_while_in_flight():
    app = _make_app(5)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        assert app._page_header._refreshing_label.place_info() == {}

        app.refresh()
        assert app._page_header._refreshing_label.cget("text") == "Refreshing…"

        wait_for_refresh(app)
        assert app._page_header._refreshing_label.place_info() == {}
    finally:
        app.destroy()


def test_refresh_failure_shows_error_indicator_and_keeps_old_content(monkeypatch):
    app = _make_app(6)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        before_ids = list(app._visible_clip_ids)
        before_children = len(app._list.winfo_children()) + len(app._grid.winfo_children())
        assert before_ids

        def boom(*a, **k):
            raise RuntimeError("simulated vault read failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)

        app.refresh()
        wait_for_refresh(app)

        assert app._visible_clip_ids == before_ids, "old content must survive a failed refresh"
        assert (
            len(app._list.winfo_children()) + len(app._grid.winfo_children())
        ) == before_children
        assert "failed" in app._page_header._refreshing_label.cget("text").lower()
        assert app._page_header._refreshing_label.place_info() != {}
    finally:
        app.destroy()


def test_successful_refresh_after_a_failure_clears_the_error_indicator(monkeypatch):
    app = _make_app(4)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)

        def boom(*a, **k):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)
        app.refresh()
        wait_for_refresh(app)
        assert app._page_header._refreshing_label.place_info() != {}

        monkeypatch.undo()
        app.refresh()
        wait_for_refresh(app)
        assert app._page_header._refreshing_label.place_info() == {}
    finally:
        app.destroy()
