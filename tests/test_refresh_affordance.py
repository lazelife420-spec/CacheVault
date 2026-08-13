"""CACHEVAULT ALL CLIPS REFRESH AFFORDANCE — focused tests.

Covers the slice that exposes the EXISTING refresh subsystem as a visible,
supported All Clips control (the packaged UI previously had no way to invoke
refresh, which forced evidence substitution in the prior candidate):

* the Refresh control exists on All Clips and is a real button with the
  accessible word "Refresh";
* the control invokes the existing refresh() path (no second implementation);
* activating it while a render is active coalesces (no overlapping workers);
* a busy/disabled state appears while a refresh is in flight and clears on
  completion;
* a failed refresh preserves the previously visible results and keeps the
  existing honest failure feedback ("Refresh failed — showing previous
  results");
* Search, Cards/Grid, and Sort/Type remain wired (no regression).

Source-level structural assertions run unconditionally (no Tk runtime).
Functional assertions are gated on Tk/CustomTkinter availability, matching
tests/test_search_discoverability.py and tests/test_refresh_nondestructive.py.
The failure path reuses the proven owned-refresh helper from
test_refresh_nondestructive rather than duplicating refresh logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import customtkinter as ctk

from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.core import storage as S
from cache_vault.ui import shell as _shell_mod
from cache_vault.ui import page_header as _page_header_mod
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

OK, REASON = probe_tk_ui()

_SHELL_SRC = Path(_shell_mod.__file__)
_PAGE_HEADER_SRC = Path(_page_header_mod.__file__)


# ---------------------------------------------------------------------------
# Source-level structural assertions (no Tk required).
# ---------------------------------------------------------------------------

def test_refresh_control_wired_in_source():
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "_refresh_btn" in src, "Refresh control widget missing"
    assert "_on_refresh_clicked" in src, "Refresh click handler missing"
    # The control lives on the page-level row (row2 with Sort/Type), not the
    # Cards/Grid view-toggle row (row3).
    assert "self._toolbar_row2, text=self._REFRESH_LABEL" in src, (
        "Refresh control must be built on _toolbar_row2 (page-level controls)"
    )
    # Accessible affordance: a tooltip literally reading "Refresh".
    assert 'bind_tooltip(self._refresh_btn, "Refresh")' in src, (
        "Refresh tooltip not wired"
    )
    assert '_REFRESH_LABEL = "⟳ Refresh"' in src, "Refresh label constant missing"


def test_refresh_click_invokes_existing_path_in_source():
    src = _SHELL_SRC.read_text(encoding="utf-8")
    # The handler must call the existing refresh() entry point, not a new impl.
    handler_idx = src.index("def _on_refresh_clicked")
    handler_body = src[handler_idx:handler_idx + 800]
    assert "self.refresh()" in handler_body, (
        "_on_refresh_clicked must call the existing refresh() path"
    )
    # No new worker/queue/thread machinery introduced by the handler.
    for banned in ("Thread(", "Queue(", "_collect_refresh_snapshot", "reader_connection"):
        assert banned not in handler_body, (
            f"_on_refresh_clicked must not reimplement refresh ({banned!r} found)"
        )


def test_busy_state_centralized_in_source():
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "def _set_refreshing(" in src, "centralized busy helper missing"
    # The engine's busy/idle transitions route through the wrapper so the
    # indicator and the button never drift.
    assert "self._set_refreshing(True)" in src
    assert "self._set_refreshing(False)" in src
    assert "self._set_refreshing(False, error=True)" in src
    # The button is disabled while busy (strongest overlap guard) and restored.
    assert 'state="disabled"' in src and "_REFRESH_BUSY_LABEL" in src


def test_honest_failure_feedback_preserved_in_source():
    ph = _PAGE_HEADER_SRC.read_text(encoding="utf-8")
    assert "Refresh failed — showing previous results" in ph, (
        "honest refresh-failure message must be preserved"
    )


# ---------------------------------------------------------------------------
# Functional assertions (Tk/CustomTkinter required).
# ---------------------------------------------------------------------------

def _isolated_settings() -> Settings:
    return Settings(capture_paused=True)


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n, prefix="clip"):
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=_isolated_settings())
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app):
    app._do_refresh_sync()
    wait_for_refresh(app)


@pytest.mark.skipif(not OK, reason=REASON)
def test_refresh_control_exists_on_all_clips(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        assert hasattr(app, "_refresh_btn"), "Refresh control missing"
        assert isinstance(app._refresh_btn, ctk.CTkButton)
        assert "Refresh" in app._refresh_btn.cget("text"), (
            f"Refresh control text lost its accessible word: {app._refresh_btn.cget('text')!r}"
        )
        # It is a child of the page-level row (row2), not the Cards/Grid row.
        assert str(app._refresh_btn.winfo_parent()) == str(app._toolbar_row2), (
            "Refresh control must sit on the page-level toolbar row, not with Cards/Grid"
        )
        # And it is clearly distinct from the Cards/Grid view toggle.
        assert app._refresh_btn is not app._cards_btn
        assert app._refresh_btn is not app._grid_btn
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_refresh_control_invokes_existing_refresh_path(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        calls = {"n": 0}
        real_refresh = app.refresh

        def counting_refresh(*a, **k):
            calls["n"] += 1
            return real_refresh(*a, **k)

        app.refresh = counting_refresh  # type: ignore[method-assign]
        try:
            cmd = app._refresh_btn.cget("command")
            assert callable(cmd), "Refresh control has no command wired"
            cmd()  # exercise the actual wired control
        finally:
            wait_for_refresh(app)
            app.refresh = real_refresh  # type: ignore[method-assign]

        assert calls["n"] >= 1, "Refresh control did not invoke refresh()"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_busy_state_appears_while_active_and_clears_after_success(tmp_path):
    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        # Idle: control enabled and showing its normal label.
        assert str(app._refresh_btn.cget("state")) == "normal"
        assert app._refresh_btn.cget("text") == app._REFRESH_LABEL

        # Activate via the real control command. refresh() sets the busy state
        # synchronously (before the 50ms debounce/worker), so we can assert it
        # immediately without pumping.
        cmd = app._refresh_btn.cget("command")
        cmd()
        assert str(app._refresh_btn.cget("state")) == "disabled", (
            "Refresh control must be disabled/busy while a refresh is in flight"
        )
        assert app._refresh_btn.cget("text") == app._REFRESH_BUSY_LABEL
        # And the existing non-blocking indicator is also active.
        assert app._page_header._refreshing_label.cget("text") == "Refreshing…"

        wait_for_refresh(app)

        # Settled: busy state cleared on both the control and the indicator.
        assert str(app._refresh_btn.cget("state")) == "normal", (
            "Refresh control must return to normal after a successful refresh"
        )
        assert app._refresh_btn.cget("text") == app._REFRESH_LABEL
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_rapid_activation_does_not_create_overlapping_refreshes(tmp_path):
    vault = _vault_with_clips(tmp_path, 6)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)

        # Put the app into a render-active state using its own machinery.
        app.refresh()
        app._do_refresh_sync()
        assert app._render_active is True, "precondition: a render must be active"

        gen_before = app._refresh_generation
        workers_before = app._refresh_workers_in_flight

        # Rapidly activate the control several times while render-active.
        cmd = app._refresh_btn.cget("command")
        for _ in range(5):
            cmd()

        # The engine must coalesce: no new generation, no additional worker.
        assert app._refresh_generation == gen_before, (
            "rapid activation must not start new refresh generations while a "
            "render is active"
        )
        assert app._refresh_workers_in_flight <= workers_before, (
            "rapid activation must not spin up overlapping refresh workers"
        )
        assert app._pending_refresh_signature is not None, (
            "a coalesced activation should record a single pending request"
        )

        wait_for_refresh(app)
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_failure_preserves_results_and_keeps_honest_feedback(tmp_path, monkeypatch):
    # Reuse the proven owned-refresh helper rather than duplicating refresh
    # control flow — it guarantees we observe OUR scripted failure generation.
    from tests.test_refresh_nondestructive import _start_owned_refresh_and_wait

    vault = _vault_with_clips(tmp_path, 6)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        before_ids = list(app._visible_clip_ids)
        before_children = len(app._list.winfo_children()) + len(app._grid.winfo_children())
        assert before_ids, "precondition: results are visible"

        def boom(*a, **k):
            raise RuntimeError("simulated vault read failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)

        _start_owned_refresh_and_wait(
            app,
            ui_settled=lambda: (
                "failed" in app._page_header._refreshing_label.cget("text").lower()
                and app._page_header._refreshing_label.place_info() != {}
            ),
            ui_description="honest failure indicator visible after a failed refresh",
        )

        # Previous results survive a failed refresh.
        assert app._visible_clip_ids == before_ids, "results must survive a failed refresh"
        assert (
            len(app._list.winfo_children()) + len(app._grid.winfo_children())
        ) == before_children
        # Honest failure feedback stays visible.
        assert "failed" in app._page_header._refreshing_label.cget("text").lower()
        assert app._page_header._refreshing_label.place_info() != {}
        # The control itself re-enables so the user can retry.
        assert str(app._refresh_btn.cget("state")) == "normal", (
            "Refresh control must re-enable after a failed refresh so retry is possible"
        )
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_search_cards_grid_sort_type_intact_with_refresh_control(tmp_path):
    total = 6
    vault = _vault_with_clips(tmp_path, total, prefix="needle")
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        # Refresh control coexists with the other controls.
        assert hasattr(app, "_refresh_btn")
        assert hasattr(app, "_clips_search") and isinstance(app._clips_search, ctk.CTkEntry)
        assert hasattr(app, "_cards_btn") and hasattr(app, "_grid_btn")
        assert hasattr(app, "_sort_var") and hasattr(app, "_type_var")

        # Search still narrows and clearing restores (unchanged behavior).
        assert len(app._visible_clip_ids) == total
        app._search_var.set("needle 3")
        _settle(app)
        assert len(app._visible_clip_ids) == 1
        app._search_var.set("")
        _settle(app)
        assert len(app._visible_clip_ids) == total

        # A refresh via the control leaves the other controls wired.
        cmd = app._refresh_btn.cget("command")
        cmd()
        wait_for_refresh(app)
        assert hasattr(app, "_grid_btn") and hasattr(app, "_cards_btn")
        assert app._sort_var.get() and app._type_var.get()
    finally:
        app.destroy()
