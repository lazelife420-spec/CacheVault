"""Crash-visibility tests: worker-thread logging and re-entrancy guard."""

from __future__ import annotations

import faulthandler
import sys
import threading
from types import SimpleNamespace

from cache_vault.ui import crashlog
from cache_vault.ui.shell import CacheVaultApp


def test_thread_excepthook_writes_crash_log(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    prev_sys, prev_thread = sys.excepthook, threading.excepthook
    try:
        crashlog.install_global_hook()
        assert threading.excepthook is not prev_thread
        args = SimpleNamespace(
            exc_type=RuntimeError,
            exc_value=RuntimeError("bridge boom"),
            exc_traceback=None,
            thread=SimpleNamespace(name="mobile-bridge"),
        )
        threading.excepthook(args)
    finally:
        sys.excepthook, threading.excepthook = prev_sys, prev_thread

    log_text = (tmp_path / "CacheVault" / "crash.log").read_text(encoding="utf-8")
    assert "bridge boom" in log_text
    assert "mobile-bridge" in log_text


def test_native_crash_capture_arms_faulthandler(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    was_enabled = faulthandler.is_enabled()
    try:
        crashlog.enable_native_crash_capture()
        assert faulthandler.is_enabled()
        native_log = tmp_path / "CacheVault" / "crash_native.log"
        assert native_log.is_file()
        assert "faulthandler armed" in native_log.read_text(encoding="utf-8")
    finally:
        if not was_enabled:
            faulthandler.disable()


def test_report_callback_exception_reentrancy_guard(monkeypatch):
    """When already reporting, a second callback error records once and does not
    recurse into the dialog path."""
    app = object.__new__(CacheVaultApp)
    app._reporting_crash = True

    written = []
    monkeypatch.setattr(
        "cache_vault.ui.shell.write_crash",
        lambda title, exc: written.append(title) or "crash.log",
    )

    calls = []
    app._report_callback_exception = lambda *a, **k: calls.append(a)

    app.report_callback_exception(RuntimeError, RuntimeError("recur"), None)

    assert calls == []  # dialog path not entered
    assert written and "re-entrant" in written[0]
