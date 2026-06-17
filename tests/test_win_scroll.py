"""Tests for Windows wheel scroll normalization."""

from __future__ import annotations

import sys

import pytest

from cache_vault.ui.win_scroll import (
    ScrollConfig,
    horizontal_canvas_units,
    set_scroll_config_supplier,
    vertical_canvas_units,
    vertical_text_units,
)


@pytest.fixture(autouse=True)
def _default_config():
    set_scroll_config_supplier(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    yield


def test_vertical_canvas_units_three_lines_default():
    import cache_vault.ui.win_scroll as ws

    ws._cached_lines = 3
    assert vertical_canvas_units(120, line_pixels=22) == -66
    ws._cached_lines = None


def test_vertical_canvas_units_smooth_scroll():
    set_scroll_config_supplier(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    # Simulate smooth mode by patching get_wheel_scroll_lines via multiplier path:
    # use lines=0 path through direct call with custom supplier + monkeypatch
    import cache_vault.ui.win_scroll as ws

    ws._cached_lines = 0
    assert vertical_canvas_units(120) == -120
    ws._cached_lines = None


def test_vertical_text_units_respects_multiplier():
    set_scroll_config_supplier(
        lambda: ScrollConfig(use_windows_settings=True, multiplier=2.0),
    )
    import cache_vault.ui.win_scroll as ws

    ws._cached_lines = 3
    assert vertical_text_units(120) == -6
    ws._cached_lines = None


def test_legacy_ctk_fallback_when_disabled():
    set_scroll_config_supplier(
        lambda: ScrollConfig(use_windows_settings=False, multiplier=1.0),
    )
    assert vertical_canvas_units(120) == -20


def test_horizontal_canvas_units():
    import cache_vault.ui.win_scroll as ws

    ws._cached_chars = 3
    assert horizontal_canvas_units(120, char_pixels=8) == -24
    ws._cached_chars = None


def test_build_meta_rc_tuple_still_pads():
    from cache_vault.build_meta import windows_version_tuple as wvt

    assert wvt("0.1.3-rc3") == (0, 1, 3, 0)
