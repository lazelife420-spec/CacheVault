"""Tests for cache_vault.ui.crashlog."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

from cache_vault.ui import crashlog


def test_crashlog_log_path_respects_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = crashlog.log_path()
    assert path == tmp_path / "CacheVault" / "crash.log"


def test_crashlog_write_crash_creates_and_appends(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    try:
        raise ValueError("simulated test crash 1")
    except ValueError as exc1:
        log_path = crashlog.write_crash("first error", exc1)

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "first error" in content
    assert "ValueError: simulated test crash 1" in content
    assert "test_crashlog_write_crash_creates_and_appends" in content

    # Second error appends
    try:
        raise KeyError("simulated key error")
    except KeyError as exc2:
        crashlog.write_crash("second error", exc2)

    content2 = log_path.read_text(encoding="utf-8")
    assert "first error" in content2
    assert "second error" in content2
    assert "KeyError: 'simulated key error'" in content2


def test_crashlog_install_global_hook(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    orig_hook = sys.excepthook

    called_orig = []

    def mock_orig(exc_type, exc, tb):
        called_orig.append((exc_type, exc))

    monkeypatch.setattr(sys, "excepthook", mock_orig)

    try:
        crashlog.install_global_hook()

        test_err = RuntimeError("uncaught UI failure")
        sys.excepthook(RuntimeError, test_err, None)

        # Original hook was chained
        assert len(called_orig) == 1
        assert called_orig[0] == (RuntimeError, test_err)

        # Crash log was written
        log = crashlog.log_path()
        assert log.exists()
        text = log.read_text(encoding="utf-8")
        assert "uncaught exception" in text
        assert "RuntimeError: uncaught UI failure" in text
    finally:
        sys.excepthook = orig_hook
