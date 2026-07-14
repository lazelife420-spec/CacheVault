"""Tests for first-use guide, tooltips, and empty-state copy."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from cache_vault.core.settings import Settings
from cache_vault.ui.guide_copy import (
    EMPTY_EXPORTS,
    EMPTY_MOBILE_INBOX,
    EMPTY_SAFES,
    EMPTY_STAMPED_RECEIPTS,
    GUIDE_BTN_DISMISS,
    GUIDE_BTN_RECEIPTS,
    GUIDE_BTN_START,
    GUIDE_TITLE,
    NAV_TOOLTIPS,
    SETTINGS_SHOW_GUIDE_AGAIN,
    TOOLTIP_EXPORT_PROOF,
    TOOLTIP_MOBILE_INBOX,
    TOOLTIP_STAMPED_RECEIPTS,
    guide_copy_has_no_forbidden_claims,
)


def test_first_use_guide_default_not_dismissed():
    s = Settings()
    assert s.first_use_guide_dismissed is False


def test_first_use_guide_dismiss_persists(tmp_path: Path):
    path = tmp_path / "settings.json"
    s = Settings(first_use_guide_dismissed=True)
    s.save(path)
    loaded = Settings.load(path)
    assert loaded.first_use_guide_dismissed is True


def test_first_use_guide_reset_via_settings_field(tmp_path: Path):
    path = tmp_path / "settings.json"
    s = Settings(first_use_guide_dismissed=True)
    s.save(path)
    s2 = Settings.load(path)
    s2.first_use_guide_dismissed = False
    s2.save(path)
    assert Settings.load(path).first_use_guide_dismissed is False


def test_guide_strings_present():
    assert GUIDE_TITLE == "Welcome to Cache Vault"
    assert GUIDE_BTN_START == "Start using Cache Vault"
    assert GUIDE_BTN_RECEIPTS == "Show me receipts"
    assert GUIDE_BTN_DISMISS == "Do not show again"
    assert SETTINGS_SHOW_GUIDE_AGAIN == "Show first-use guide again"


def test_nav_tooltips_cover_key_areas():
    assert "nav_stamped_receipts" in NAV_TOOLTIPS
    assert "nav_exports" in NAV_TOOLTIPS
    assert "nav_mobile_inbox" in NAV_TOOLTIPS
    assert "nav_vault_macros" in NAV_TOOLTIPS
    assert TOOLTIP_STAMPED_RECEIPTS in NAV_TOOLTIPS.values()
    assert TOOLTIP_EXPORT_PROOF in NAV_TOOLTIPS.values()
    assert TOOLTIP_MOBILE_INBOX in NAV_TOOLTIPS.values()


def test_empty_state_copy_present():
    assert "No receipts yet" in EMPTY_STAMPED_RECEIPTS
    assert "Nothing from your phone yet" in EMPTY_MOBILE_INBOX
    assert "Default Safe" in EMPTY_SAFES
    assert "No proof exports yet" in EMPTY_EXPORTS


def test_guide_copy_has_no_forbidden_claims():
    assert guide_copy_has_no_forbidden_claims()


def test_guide_copy_no_encrypted_safes_claim():
    from cache_vault.ui.guide_copy import GUIDE_CARDS, TOOLTIP_SAFES

    safes_card = next(t for t, _ in GUIDE_CARDS if t == "Organize with Safes")
    assert safes_card
    body = next(b for t, b in GUIDE_CARDS if t == "Organize with Safes")
    assert "not encryption" in body.lower()
    assert "encrypted" not in TOOLTIP_SAFES.lower()


def test_close_destroys_window():
    """BUG-8 regression: clicking X must destroy the dialog, not leave it open."""
    import inspect

    from cache_vault.ui.first_use_guide import FirstUseGuideDialog

    src = inspect.getsource(FirstUseGuideDialog._close_only)
    # Both the from_settings branch and the non-settings fallback must call
    # self.destroy() so the window actually closes.
    assert "self.destroy()" in src
    from_settings_idx = src.index("_from_settings")
    destroy_calls = [i for i in range(len(src)) if src.startswith("self.destroy()", i)]
    assert len(destroy_calls) >= 2, (
        "_close_only must call self.destroy() in both branches"
    )


def test_settings_round_trip_includes_first_use_flag(tmp_path: Path):
    path = tmp_path / "settings.json"
    Settings().save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("first_use_guide_dismissed") is False
