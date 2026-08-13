"""CACHEVAULT ALL CLIPS SEARCH DISCOVERABILITY FIX — focused tests.

Covers the visual/affordance slice that made the All Clips search field
hard to discover:

* the search field exists and is wrapped in a differentiated, outlined well;
* the intended placeholder cue ("Search clips…") is present;
* the search icon label is wired into the well;
* the focus state reconfigures the well outline;
* the search callback remains wired — typing narrows results, clearing
  restores them (filtering behavior unchanged);
* Cards/Grid controls and toolbar layout are not regressed.

Source-level structural assertions run unconditionally (no Tk runtime
required) so the affordance wiring is covered even in headless CI.
Functional assertions are gated on Tk/CustomTkinter availability,
matching the existing pattern in tests/test_shell_selection_keys.py.
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
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

OK, REASON = probe_tk_ui()

_SHELL_SRC = Path(_shell_mod.__file__)


# ---------------------------------------------------------------------------
# Source-level structural assertions (no Tk required).
# ---------------------------------------------------------------------------

def test_search_field_wrapper_and_icon_present_in_source():
    """The All Clips search entry must be wrapped in a differentiated,
    outlined well with a visible magnifier icon — not a bare CTkEntry
    packed straight onto the toolbar panel (which blended in)."""
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "_search_field_wrap" in src, "search well wrapper missing"
    assert "search_icon_pil" in src, "search icon helper not wired"
    assert "_search_icon_label" in src, "search icon label missing"
    # The icon PhotoImage must be bound to the app root (not a CTkImage that
    # binds to Tk._default_root and breaks across many app lifecycles).
    assert "ImageTk.PhotoImage" in src and "master=self" in src, (
        "search icon photo must be root-bound"
    )
    # The well is differentiated from the IRON_GRAY panel and outlined.
    assert "brand.BLACK_METAL" in src
    assert "brand.VAULT_BORDER" in src


def test_intended_placeholder_cue_present_in_source():
    """The placeholder must lead with the clear 'Search clips…' cue, and an
    explicit overlay must render it (CTkEntry suppresses its own placeholder
    when a textvariable is bound, so the widget-level arg alone is not enough)."""
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert 'placeholder_text="Search clips' in src, (
        "intended 'Search clips…' placeholder cue not found in shell source"
    )
    assert "_search_placeholder" in src, "explicit placeholder overlay missing"
    assert '"Search clips…"' in src, "overlay placeholder text missing"
    assert "_update_search_placeholder" in src, "placeholder toggle logic missing"


def test_focus_state_bindings_present_in_source():
    """FocusIn/FocusOut must reconfigure the well outline (clear focus state)."""
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "<FocusIn>" in src and "<FocusOut>" in src, (
        "search field focus state bindings missing"
    )
    assert "brand.PROOF_TEAL" in src, "focus accent color not wired"


def test_cards_grid_controls_not_removed_from_source():
    """Cards/Grid controls and the toolbar rows must remain in place."""
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert "_grid_btn" in src, "Grid control missing"
    assert "_toolbar_row1" in src and "_toolbar_row2" in src and "_toolbar_row3" in src, (
        "toolbar rows regressed"
    )


def test_search_callback_path_preserved_in_source():
    """The search StringVar -> _on_search_changed wiring must remain."""
    src = _SHELL_SRC.read_text(encoding="utf-8")
    assert '_search_var.trace_add("write", self._on_search_changed)' in src, (
        "search callback wiring changed"
    )


# ---------------------------------------------------------------------------
# Functional assertions (Tk/CustomTkinter required).
# ---------------------------------------------------------------------------

def _isolated_settings() -> Settings:
    """capture_paused=True keeps the app from reading the live OS clipboard
    so count-based assertions stay deterministic (see test_shell_selection_keys)."""
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
def test_search_field_and_well_constructed(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        # The search control exists and is a CTkEntry.
        assert isinstance(app._clips_search, ctk.CTkEntry)
        # The differentiated well wrapper exists.
        assert hasattr(app, "_search_field_wrap")
        assert isinstance(app._search_field_wrap, ctk.CTkFrame)
        # The well is outlined (border_width >= 1) and differentiated from the
        # bare IRON_GRAY panel surface.
        assert int(app._search_field_wrap.cget("border_width")) >= 1
        # The magnifier icon is wired: a root-bound PhotoImage retained on the
        # app plus a visible label inside the well.
        assert app._search_icon_photo is not None, "search icon PhotoImage not retained"
        assert app._search_icon_label is not None, "search icon label not created"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_intended_placeholder_present_on_widget(tmp_path):
    vault = _vault_with_clips(tmp_path, 2)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        placeholder = str(app._clips_search.cget("placeholder_text"))
        assert placeholder.startswith("Search clips"), (
            f"placeholder cue missing/changed: {placeholder!r}"
        )

        # The overlay label carries the visible cue and reads "Search clips…".
        assert app._search_placeholder is not None
        assert app._search_placeholder.cget("text") == "Search clips…"

        # Empty + unfocused => the placeholder overlay is mapped (visible).
        app._search_placeholder_focused = False
        app._update_search_placeholder()
        app.update_idletasks()
        assert app._search_placeholder.winfo_manager() == "place", (
            "placeholder overlay should be visible when empty and unfocused"
        )

        # Non-empty => overlay hidden.
        app._search_var.set("anything")
        app.update_idletasks()
        assert app._search_placeholder.winfo_manager() == "", (
            "placeholder overlay should hide once a query is present"
        )

        # Cleared again => overlay returns.
        app._search_var.set("")
        app.update_idletasks()
        assert app._search_placeholder.winfo_manager() == "place", (
            "placeholder overlay should return when the query is cleared"
        )
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_search_callback_narrows_then_clear_restores(tmp_path):
    """Filtering behavior must be unchanged: a query narrows the visible
    result set, and clearing it restores all clips."""
    total = 6
    vault = _vault_with_clips(tmp_path, total, prefix="needle")
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)
        assert len(app._visible_clip_ids) == total

        # A query that matches only a subset narrows the results.
        app._search_var.set("needle 3")
        _settle(app)
        assert len(app._visible_clip_ids) == 1, (
            f"expected 1 match for 'needle 3', got {len(app._visible_clip_ids)}"
        )

        # Clearing the query restores the full set.
        app._search_var.set("")
        _settle(app)
        assert len(app._visible_clip_ids) == total, (
            f"clearing search did not restore all {total} clips"
        )
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_cards_grid_controls_present_after_search_change(tmp_path):
    """Cards/Grid controls must remain functional alongside the search
    affordance change — no layout regression."""
    vault = _vault_with_clips(tmp_path, 4)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        assert hasattr(app, "_grid_btn"), "Grid control missing"
        # Toggling a search value must not disturb the Cards/Grid buttons.
        app._search_var.set("needle 0")
        _settle(app)
        assert hasattr(app, "_grid_btn"), "Grid control lost after search change"
        app._search_var.set("")
        _settle(app)
        assert hasattr(app, "_grid_btn"), "Grid control lost after clearing search"
    finally:
        app.destroy()
