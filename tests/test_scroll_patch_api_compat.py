"""Compatibility-probe coverage for the Windows wheel-scroll patch.

Follow-up A (packaging dependency reproducibility): the patch in
``cache_vault/ui/scroll_patch.py`` depends on private CustomTkinter APIs that
changed across releases (5.2.x exposed ``check_if_master_is_canvas``; 6.0.0
exposes ``_check_if_valid_scroll``). ``verify_scroll_patch_compatibility`` is a
non-mutating probe (no Tk root, no patch install) that must fail clearly when
the installed/bundled CustomTkinter is incompatible, and ``app.py --selftest``
must invoke it before reporting success.

These tests are intentionally headless — they never construct a Tk root.
Runtime wheel-scroll behaviour is covered by ``test_scroll_patch.py`` and must
remain unchanged by this work.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cache_vault.ui import scroll_patch as sp
from cache_vault.ui.scroll_patch import (
    ScrollPatchIncompatibleError,
    _REQUIRED_SCROLLFRAME_ATTRS,
    verify_scroll_patch_compatibility,
)


def _fake_frame(**attrs):
    """A stand-in CTkScrollableFrame class exposing only the named attributes."""
    return SimpleNamespace(**attrs)


def _compatible_frame():
    return _fake_frame(_mouse_wheel_all=lambda self, e: None,
                       _check_if_valid_scroll=lambda self, w: True)


def test_installed_customtkinter_is_compatible():
    """The environment that builds the PR #103 EXE (customtkinter 6.0.0) passes."""
    import customtkinter

    assert customtkinter.__version__ == "6.0.0"
    # Real installed class — must not raise.
    verify_scroll_patch_compatibility()


def test_compatible_api_passes():
    verify_scroll_patch_compatibility(_compatible_frame(), version="6.0.0")


def test_missing_mouse_wheel_all_fails_clearly():
    frame = _fake_frame(_check_if_valid_scroll=lambda self, w: True)
    with pytest.raises(ScrollPatchIncompatibleError) as exc:
        verify_scroll_patch_compatibility(frame, version="5.2.2")
    msg = str(exc.value)
    assert "_mouse_wheel_all" in msg
    assert "5.2.2" in msg


def test_missing_check_if_valid_scroll_fails_clearly():
    # This is the real 5.2.x break: _mouse_wheel_all present, validation API absent.
    frame = _fake_frame(_mouse_wheel_all=lambda self, e: None)
    with pytest.raises(ScrollPatchIncompatibleError) as exc:
        verify_scroll_patch_compatibility(frame, version="5.2.2")
    msg = str(exc.value)
    assert "_check_if_valid_scroll" in msg
    assert "5.2.2" in msg


def test_every_required_private_api_is_validated():
    """Removing any single required attribute must be detected and named."""
    assert _REQUIRED_SCROLLFRAME_ATTRS == ("_mouse_wheel_all", "_check_if_valid_scroll")
    for attr in _REQUIRED_SCROLLFRAME_ATTRS:
        present = {a: (lambda *a, **k: None) for a in _REQUIRED_SCROLLFRAME_ATTRS if a != attr}
        frame = _fake_frame(**present)
        with pytest.raises(ScrollPatchIncompatibleError) as exc:
            verify_scroll_patch_compatibility(frame, version="0.0.0")
        assert attr in str(exc.value)


def test_error_names_version_and_all_missing_apis():
    frame = _fake_frame()  # neither attribute present
    with pytest.raises(ScrollPatchIncompatibleError) as exc:
        verify_scroll_patch_compatibility(frame, version="9.9.9")
    msg = str(exc.value)
    assert "9.9.9" in msg
    for attr in _REQUIRED_SCROLLFRAME_ATTRS:
        assert attr in msg


def test_version_falls_back_to_installed_when_unspecified(monkeypatch):
    monkeypatch.setattr(sp.customtkinter, "__version__", "1.2.3", raising=False)
    frame = _fake_frame()
    with pytest.raises(ScrollPatchIncompatibleError) as exc:
        verify_scroll_patch_compatibility(frame)
    assert "1.2.3" in str(exc.value)


def test_install_verifies_before_patching(monkeypatch):
    """install_windows_scroll_patch must run the probe before mutating anything."""
    calls = {"n": 0}

    def _boom(*args, **kwargs):
        calls["n"] += 1
        raise ScrollPatchIncompatibleError("simulated incompatibility")

    monkeypatch.setattr(sp, "verify_scroll_patch_compatibility", _boom)
    with pytest.raises(ScrollPatchIncompatibleError):
        sp.install_windows_scroll_patch(
            lambda: sp.ScrollConfig(use_windows_settings=True, multiplier=1.0)
        )
    assert calls["n"] == 1


def test_selftest_invokes_compatibility_probe(monkeypatch):
    import app

    called = {"n": 0}
    monkeypatch.setattr(sp, "verify_scroll_patch_compatibility",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    rc = app._selftest()
    assert rc == 0
    assert called["n"] == 1


def test_selftest_fails_when_incompatible(monkeypatch):
    import app

    def _boom(*args, **kwargs):
        raise ScrollPatchIncompatibleError("simulated incompatibility")

    monkeypatch.setattr(sp, "verify_scroll_patch_compatibility", _boom)
    rc = app._selftest()
    assert rc == 1
