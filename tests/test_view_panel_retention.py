"""Regression: only the visible clip view may hold rendered rows.

Each clip row is a deep CustomTkinter tree, and on Windows every widget is a
process USER object drawn from a ~10,000 per-process quota. Before this fix
the shell built the Cards view, the Grid view, and every vault screen once and
only ever hid them with grid_remove/pack_forget, so a large real profile kept
both fully-populated clip views (plus all screens) alive at the same time. The
retained tree plateaued near the quota, and the next menu/tooltip/dialog
allocation tipped it over, surfacing as "No more menus can be allocated."

The fix frees the non-visible clip view(s) in the refresh dispatch:
- on a vault screen or Command Center, both clip views are cleared;
- in clips mode, only the active view keeps rows and the inactive one is
  cleared.
refresh() rebuilds the active view on return, so this is behavior-preserving.
"""

import pytest

from cache_vault.core import storage as S
from cache_vault.ui.filters import NAV_STAMPED_RECEIPTS
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

OK, REASON = probe_tk_ui()


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n):
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=settings)
    for i in range(n):
        vault.capture(f"clip {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app) -> None:
    for _ in range(10):
        wait_for_refresh(app)
        if (
            app._refresh_job is None
            and app._refresh_workers_in_flight == 0
            and app._refresh_request_queue.qsize() == 0
            and app._main_thread_calls.qsize() == 0
            and getattr(app, "_resize_job", None) is None
            and getattr(app, "_render_active", False) is False
            and getattr(app, "_pending_refresh_signature", None) is None
        ):
            return
    raise AssertionError("app did not reach a fully idle refresh state")


@pytest.mark.skipif(not OK, reason=REASON)
def test_clip_views_have_clear(tmp_path):
    vault = _vault_with_clips(tmp_path, 0)
    app = _make_app(vault)
    try:
        assert callable(getattr(app._list, "clear", None))
        assert callable(getattr(app._grid, "clear", None))
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_hidden_clip_views_cleared_on_screen_and_home(tmp_path):
    vault = _vault_with_clips(tmp_path, 40)
    app = _make_app(vault)
    try:
        app.withdraw()

        # Cards view showing clips: populated, grid empty.
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        assert len(app._list._row_by_id) > 0
        assert len(app._grid._row_by_id) == 0

        # A vault screen frees both clip views.
        app._navigate_screen(NAV_STAMPED_RECEIPTS)
        _settle(app)
        assert len(app._list._row_by_id) == 0
        assert len(app._grid._row_by_id) == 0

        # Command Center likewise frees both clip views.
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        assert len(app._list._row_by_id) > 0
        app._navigate_screen(S.FILTER_HOME)
        _settle(app)
        assert len(app._list._row_by_id) == 0
        assert len(app._grid._row_by_id) == 0
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_only_active_clip_view_holds_rows(tmp_path):
    vault = _vault_with_clips(tmp_path, 40)
    app = _make_app(vault)
    try:
        app.withdraw()

        app._navigate_screen(S.FILTER_ALL)  # Cards is the default view mode
        _settle(app)
        assert len(app._list._row_by_id) > 0
        assert len(app._grid._row_by_id) == 0

        app._set_view_mode("grid")
        _settle(app)
        assert len(app._grid._row_by_id) > 0
        assert len(app._list._row_by_id) == 0

        app._set_view_mode("cards")
        _settle(app)
        assert len(app._list._row_by_id) > 0
        assert len(app._grid._row_by_id) == 0
    finally:
        app.destroy()
