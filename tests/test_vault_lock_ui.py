from __future__ import annotations

import inspect

import customtkinter as ctk

from cache_vault import brand
from cache_vault.core import models, vault_lock
from cache_vault.core.models import Clip
from cache_vault.core.settings import Settings
from cache_vault.core.storage import FILTER_ALL, FILTER_FAVORITES
from cache_vault.ui.filters import FILTER_GROUPS, FilterNav
from cache_vault.ui.preview import PreviewPanel
from cache_vault.ui.vault_lock import LOCK_COPY, VaultControlStrip, VaultLockScreen


def test_lock_copy_has_no_forbidden_claims():
    assert "Safes organize your items" in LOCK_COPY
    assert vault_lock.no_forbidden_lock_claims(LOCK_COPY)


def test_shell_has_lock_guards():
    from cache_vault.ui.shell import CacheVaultApp

    src = inspect.getsource(CacheVaultApp)
    assert "VaultLockScreen" in src
    assert "_guard_unlocked" in src
    assert "EVENT_VAULT_UNLOCK_FAILED" in src
    assert "_on_window_unmap" in src
    assert "vault_lock_when_minimized" in src


def test_control_strip_renders_and_calls_actions(tk_root):
    calls: list[str] = []
    strip = VaultControlStrip(
        tk_root,
        callbacks={
            "lock_now": lambda: calls.append("lock_now"),
            "pair_device": lambda: calls.append("pair_device"),
            "quick_paste": lambda: calls.append("quick_paste"),
        },
    )
    strip.update_state({
        "capture_paused": False,
        "mobile_enabled": True,
        "paired_count": 1,
        "default_safe": "default",
    })
    strip._quick_action("Quick Paste")
    strip._mobile_action("Pair Device")
    strip._quick_action("Lock Vault")

    assert calls == ["quick_paste", "pair_device", "lock_now"]
    assert "Mobile: Paired" in strip._mobile.get()
    strip.destroy()


def test_lock_screen_valid_and_invalid_unlock(tk_root):
    calls: list[str] = []

    def unlock(secret: str) -> bool:
        calls.append(secret)
        return secret == "1234"

    screen = VaultLockScreen(tk_root, on_unlock=unlock, on_quit=lambda: None)
    screen._entry.insert(0, "0000")
    screen._submit()
    assert calls[-1] == "0000"
    assert screen._error_var.get() == "Unlock failed."

    screen._entry.insert(0, "1234")
    screen._submit()
    assert calls[-1] == "1234"
    assert screen._error_var.get() == ""
    screen.destroy()


def test_inspector_tabs_render(tk_root):
    panel = PreviewPanel(tk_root, actions={})
    clip = Clip(
        id="clip-1",
        content="hello inspector",
        preview="hello inspector",
        classification=models.CLASS_PLAIN,
        content_type=models.CONTENT_TEXT,
        created_at=models.now_iso(),
        updated_at=models.now_iso(),
        content_hash=models.content_hash("hello inspector"),
        safe_id="default",
        safe_name="Default Safe",
    )

    panel.show(clip)
    assert panel._tabs.cget("values") == ["Actions", "Seal", "Metadata", "History"]
    panel._set_tab("Seal")
    assert panel._active_tab == "Seal"
    panel._set_tab("Metadata")
    assert panel._active_tab == "Metadata"
    panel.destroy()


def test_sidebar_title_uses_brand_constant(tk_root):
    # Guards against the title reverting to a literal that bypasses
    # brand.py, which would silently stop following brand changes.
    settings = Settings()
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)
    title_label = nav.winfo_children()[0]
    assert brand.PRODUCT_NAME in title_label.cget("text")
    nav.destroy()


def test_sidebar_sections_collapse_and_persist(tk_root, tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    settings.save(path)
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)

    # Fresh profile: VAULT starts collapsed by default.
    assert "VAULT" in settings.sidebar_collapsed_sections

    nav._toggle_section("VAULT")
    assert "VAULT" not in settings.sidebar_collapsed_sections
    assert "VAULT" not in Settings.load(path).sidebar_collapsed_sections

    nav._toggle_section("VAULT")
    assert "VAULT" in settings.sidebar_collapsed_sections
    nav.set_active(FILTER_ALL)
    assert nav.active == FILTER_ALL
    nav.destroy()


def test_sidebar_all_sections_collapsed_on_fresh_profile(tk_root):
    settings = Settings()  # no file on disk, no prior interaction
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)
    headings = [h for h, _items in FILTER_GROUPS if h] + ["COLLECTIONS", "SAFES"]
    for heading in headings:
        assert heading in nav._collapsed, f"{heading} should start collapsed"
        assert heading in settings.sidebar_collapsed_sections
    nav.destroy()


def test_sidebar_manually_opened_group_persists_open(tk_root, tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    settings.save(path)
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)
    assert "ACCESS" in nav._collapsed  # fresh default starts collapsed

    nav._toggle_section("ACCESS")  # user opens it
    nav.destroy()

    reloaded = Settings.load(path)
    assert "ACCESS" not in reloaded.sidebar_collapsed_sections
    nav2 = FilterNav(tk_root, on_select=lambda _key: None, settings=reloaded)
    assert "ACCESS" not in nav2._collapsed
    nav2.destroy()


def test_sidebar_manually_collapsed_group_persists_collapsed(tk_root, tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    settings.save(path)
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)

    nav._toggle_section("REVIEW")  # open it first, away from the collapsed default
    assert "REVIEW" not in settings.sidebar_collapsed_sections
    nav._toggle_section("REVIEW")  # user explicitly re-collapses it
    nav.destroy()

    reloaded = Settings.load(path)
    assert "REVIEW" in reloaded.sidebar_collapsed_sections
    nav2 = FilterNav(tk_root, on_select=lambda _key: None, settings=reloaded)
    assert "REVIEW" in nav2._collapsed
    nav2.destroy()


def test_sidebar_filtering_works_when_group_starts_collapsed(tk_root):
    selected = []
    settings = Settings()
    nav = FilterNav(tk_root, on_select=selected.append, settings=settings)
    assert "VAULT" in nav._collapsed  # the group containing FILTER_FAVORITES

    nav._select(FILTER_FAVORITES)
    assert nav.active == FILTER_FAVORITES
    assert selected == [FILTER_FAVORITES]
    nav.destroy()


def test_sidebar_sections_expand_in_place_not_at_end(tk_root):
    settings = Settings()  # fresh profile: every section starts collapsed
    nav = FilterNav(tk_root, on_select=lambda _key: None, settings=settings)

    # Expand out of the sidebar's fixed visual order (VAULT, TIME, COMMAND
    # are not adjacent in FILTER_GROUPS). A regression here would show up
    # as content sinking to the end of the sibling list instead of staying
    # directly under its own heading.
    for heading in ("VAULT", "TIME", "COMMAND"):
        nav._toggle_section(heading)

    slaves = nav.pack_slaves()
    for heading in ("VAULT", "TIME", "COMMAND"):
        btn = nav._section_buttons[heading]
        frame = nav._section_frames[heading]
        assert slaves.index(frame) == slaves.index(btn) + 1, (
            f"{heading} content should be immediately after its own heading"
        )

    # Collapsing and re-expanding an already-opened section must not move
    # it either (this is the exact forget/re-pack path the fix targets).
    nav._toggle_section("TIME")
    nav._toggle_section("TIME")
    slaves = nav.pack_slaves()
    time_btn = nav._section_buttons["TIME"]
    time_frame = nav._section_frames["TIME"]
    assert slaves.index(time_frame) == slaves.index(time_btn) + 1
    nav.destroy()
