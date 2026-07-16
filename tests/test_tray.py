"""Regression coverage for the CACHE_VAULT_DISABLE_TRAY test-suite guard.

See tests/conftest.py for why this exists: a real pystray icon's shutdown
can hang the whole test process (its Windows message-loop thread's clean
exit depends on GC/finalizer timing). These tests never construct a real
pystray.Icon — even the "tray enabled" case is verified through a mock —
so they can't reintroduce the hang they're guarding against.
"""

from unittest.mock import MagicMock, patch

from cache_vault.ui.tray import TrayController


def _controller() -> TrayController:
    return TrayController(
        on_open=lambda: None,
        on_toggle_pause=lambda: None,
        on_clear_sensitive=lambda: None,
        on_quit=lambda: None,
    )


def test_disabled_by_env_var_never_touches_pystray(monkeypatch):
    monkeypatch.setenv("CACHE_VAULT_DISABLE_TRAY", "1")
    controller = _controller()
    with patch("cache_vault.ui.tray.pystray") as mock_pystray:
        controller.start()
        mock_pystray.Icon.assert_not_called()
    assert controller._icon is None


def test_conftest_sets_the_guard_by_default():
    # tests/conftest.py sets this before any test runs — pinned here so a
    # regression that removes it fails loudly instead of just occasionally
    # hanging the suite.
    import os

    assert os.environ.get("CACHE_VAULT_DISABLE_TRAY") == "1"


def test_enabled_creates_an_icon_via_mock_only(monkeypatch):
    # Confirms the guard above is actually gating something real, without
    # ever constructing a live pystray.Icon (which is exactly the resource
    # whose shutdown timing causes the hang this test file exists to guard
    # against).
    monkeypatch.delenv("CACHE_VAULT_DISABLE_TRAY", raising=False)
    controller = _controller()
    with patch("cache_vault.ui.tray.pystray") as mock_pystray, \
            patch("cache_vault.ui.tray._HAS_TRAY", True), \
            patch("cache_vault.ui.tray._make_icon_image", return_value=object()):
        mock_icon = MagicMock()
        mock_pystray.Icon.return_value = mock_icon
        controller.start()
        mock_pystray.Icon.assert_called_once()
        mock_icon.run_detached.assert_called_once()
    assert controller._icon is mock_icon
