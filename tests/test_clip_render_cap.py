"""Regression: the clip list must cap how many rows it materialises.

Each rendered row is a deep CustomTkinter tree (~45 Tk widgets, each a Windows
USER object). An unbounded history exhausts the ~10,000 per-process USER-object
quota and makes Tk raise "No more menus can be allocated" on the next menu,
which froze multi-clip copy. The shell caps rendering at MAX_VISIBLE_CLIPS and
surfaces the remainder, instead of rendering the whole vault.
"""

import pytest

from cache_vault.ui.shell import CacheVaultApp, MAX_VISIBLE_CLIPS
from tests.tk_support import probe_tk_ui, _tcl_unavailable  # noqa: PLC2701

OK, REASON = probe_tk_ui()


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def test_cap_constant_is_safe():
    # ~45 Tk/USER objects per row; stay well under the 10k Windows quota with
    # headroom for menus, dialogs, and the preview pane.
    assert 0 < MAX_VISIBLE_CLIPS <= 200


@pytest.mark.skipif(not OK, reason=REASON)
def test_large_history_is_capped(tmp_path):
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.settings import Settings
    from cache_vault.core.vault import Vault
    from cache_vault.core import storage as S

    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings())
    extra = 30
    total = MAX_VISIBLE_CLIPS + extra
    for i in range(total):
        vault.capture(f"clip {i} https://example{i}.com/path", force=True)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        # refresh() is debounced — call _do_refresh_sync() directly for
        # synchronous test behaviour so _visible_clip_ids is populated
        # before the assertions.
        app._do_refresh_sync()
        app.update()

        assert len(app._visible_clip_ids) == MAX_VISIBLE_CLIPS
        actual_total = len(vault.storage.list_clips())
        assert app._list._more_count == actual_total - MAX_VISIBLE_CLIPS
    finally:
        app.destroy()
