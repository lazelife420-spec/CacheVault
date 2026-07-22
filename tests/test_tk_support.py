"""Focused unit tests for tests/tk_support.py.

Verifies:
  - Clean available return
  - Recognized environment unavailable return
  - Unknown widget defect raises TkProbeCrash
  - Child timeout raises TkProbeTimeout
  - Child crash raises TkProbeCrash
  - Invalid JSON raises TkProbeCrash
  - stdout/stderr preservation on exception
  - Clean results cached; timeout/crash NOT cached
  - Recognized TCL/Tk environment failure tokens
"""

from __future__ import annotations

import json
import subprocess
from unittest import mock
import pytest

from tests.tk_support import (
    TkProbeCrash,
    TkProbeTimeout,
    _TCL_UNAVAILABLE_TOKENS,
    _probe_cached,
    _tcl_unavailable,
    probe_tk_ui,
)


def test_tcl_unavailable_token_matching():
    """Verify all recognized environment failure tokens are matched."""
    for token in _TCL_UNAVAILABLE_TOKENS:
        exc = RuntimeError(f"Something went wrong: {token} was not found")
        assert _tcl_unavailable(exc) is True

    assert _tcl_unavailable(RuntimeError("Arbitrary application error")) is False


def test_probe_available(monkeypatch):
    """Clean 'available' status returns (True, '')."""
    _probe_cached.cache_clear()
    payload = json.dumps({"status": "available", "reason": ""})
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = (payload, "")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        ok, reason = probe_tk_ui()
        assert ok is True
        assert reason == ""


def test_probe_unavailable_env(monkeypatch):
    """Recognized environment failure returns (False, reason)."""
    _probe_cached.cache_clear()
    payload = json.dumps({
        "status": "unavailable",
        "reason": "Tk/ttk runtime unavailable: Can't find a usable init.tcl",
    })
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = (payload, "")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        ok, reason = probe_tk_ui()
        assert ok is False
        assert "Can't find a usable init.tcl" in reason


def test_probe_widget_defect_raises_crash(monkeypatch):
    """Unknown widget defect status raises TkProbeCrash instead of returning False."""
    _probe_cached.cache_clear()
    payload = json.dumps({
        "status": "defect",
        "reason": "CustomTkinter init defect: AttributeError: module 'customtkinter' has no attribute 'X'",
        "exception_type": "AttributeError",
        "traceback": "Traceback...",
    })
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = (payload, "stderr output here")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(TkProbeCrash) as exc_info:
            probe_tk_ui()

        err = exc_info.value
        assert "widget-construction defect" in err.reason
        assert err.stdout == payload
        assert err.stderr == "stderr output here"


def test_probe_timeout_raises_timeout_exception(monkeypatch):
    """Subprocess timeout terminates child and raises TkProbeTimeout."""
    _probe_cached.cache_clear()
    mock_proc = mock.Mock()
    mock_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["python"], timeout=10.0),
        ("partial stdout", "partial stderr"),
    ]

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(TkProbeTimeout) as exc_info:
            probe_tk_ui()

        err = exc_info.value
        assert err.timeout_s == 10.0
        assert err.stdout == "partial stdout"
        assert err.stderr == "partial stderr"
        mock_proc.kill.assert_called_once()


def test_probe_crash_empty_output_raises_crash(monkeypatch):
    """Non-zero exit code or empty stdout raises TkProbeCrash."""
    _probe_cached.cache_clear()
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = ("", "Fatal Python error: Segmentation fault")
    mock_proc.returncode = 139

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(TkProbeCrash) as exc_info:
            probe_tk_ui()

        err = exc_info.value
        assert "produced no output" in err.reason
        assert err.stderr == "Fatal Python error: Segmentation fault"


def test_probe_invalid_json_raises_crash(monkeypatch):
    """Child producing invalid JSON raises TkProbeCrash."""
    _probe_cached.cache_clear()
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = ("NOT JSON AT ALL", "")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc):
        with pytest.raises(TkProbeCrash) as exc_info:
            probe_tk_ui()

        err = exc_info.value
        assert "not valid JSON" in err.reason


def test_probe_cache_only_clean_results(monkeypatch):
    """Clean outcomes are cached by lru_cache; exceptions are NOT cached."""
    _probe_cached.cache_clear()
    payload = json.dumps({"status": "available", "reason": ""})
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = (payload, "")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        r1 = probe_tk_ui()
        r2 = probe_tk_ui()
        assert r1 == r2 == (True, "")
        # Child process spawned exactly ONCE due to caching
        mock_popen.assert_called_once()


def test_probe_cache_unavailable_twice_launches_one_child():
    """Recognized unavailable result is cached; 2 calls launch 1 child."""
    _probe_cached.cache_clear()
    payload = json.dumps({"status": "unavailable", "reason": "init.tcl missing"})
    mock_proc = mock.Mock()
    mock_proc.communicate.return_value = (payload, "")
    mock_proc.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        r1 = probe_tk_ui()
        r2 = probe_tk_ui()
        assert r1 == r2 == (False, "init.tcl missing")
        mock_popen.assert_called_once()


def test_probe_timeout_retry_launches_two_children():
    """Timeout exception is NOT cached; retry launches a second child process."""
    _probe_cached.cache_clear()
    mock_timeout = mock.Mock()
    mock_timeout.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["python"], timeout=10.0),
        ("out", "err"),
    ]

    with mock.patch("subprocess.Popen", return_value=mock_timeout) as p1:
        with pytest.raises(TkProbeTimeout):
            probe_tk_ui()
        assert p1.call_count == 1

    mock_avail = mock.Mock()
    mock_avail.communicate.return_value = (json.dumps({"status": "available", "reason": ""}), "")
    mock_avail.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_avail) as p2:
        r = probe_tk_ui()
        assert r == (True, "")
        assert p2.call_count == 1


def test_probe_crash_retry_launches_two_children():
    """Crash exception is NOT cached; retry launches a second child process."""
    _probe_cached.cache_clear()
    mock_crash = mock.Mock()
    mock_crash.communicate.return_value = ("INVALID_JSON", "")
    mock_crash.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_crash) as p1:
        with pytest.raises(TkProbeCrash):
            probe_tk_ui()
        assert p1.call_count == 1

    mock_avail = mock.Mock()
    mock_avail.communicate.return_value = (json.dumps({"status": "available", "reason": ""}), "")
    mock_avail.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_avail) as p2:
        r = probe_tk_ui()
        assert r == (True, "")
        assert p2.call_count == 1


def test_probe_defect_retry_launches_two_children():
    """Defect exception is NOT cached; retry launches a second child process."""
    _probe_cached.cache_clear()
    mock_defect = mock.Mock()
    mock_defect.communicate.return_value = (json.dumps({"status": "defect", "reason": "AttributeError in CTk"}), "")
    mock_defect.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_defect) as p1:
        with pytest.raises(TkProbeCrash):
            probe_tk_ui()
        assert p1.call_count == 1

    mock_avail = mock.Mock()
    mock_avail.communicate.return_value = (json.dumps({"status": "available", "reason": ""}), "")
    mock_avail.returncode = 0

    with mock.patch("subprocess.Popen", return_value=mock_avail) as p2:
        r = probe_tk_ui()
        assert r == (True, "")
        assert p2.call_count == 1


def test_probe_timeout_crash_defect_never_return_unavailable():
    """Timeout, crash, and defect exceptions NEVER return (False, reason)."""
    _probe_cached.cache_clear()
    m_timeout = mock.Mock()
    m_timeout.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["python"], timeout=10.0),
        ("", ""),
    ]
    with mock.patch("subprocess.Popen", return_value=m_timeout):
        with pytest.raises(TkProbeTimeout):
            res = probe_tk_ui()
            assert not isinstance(res, tuple)

    _probe_cached.cache_clear()
    m_crash = mock.Mock()
    m_crash.communicate.return_value = ("", "Fatal error")
    m_crash.returncode = 1
    with mock.patch("subprocess.Popen", return_value=m_crash):
        with pytest.raises(TkProbeCrash):
            res = probe_tk_ui()
            assert not isinstance(res, tuple)

    _probe_cached.cache_clear()
    m_defect = mock.Mock()
    m_defect.communicate.return_value = (json.dumps({"status": "defect", "reason": "Widget flaw"}), "")
    m_defect.returncode = 0
    with mock.patch("subprocess.Popen", return_value=m_defect):
        with pytest.raises(TkProbeCrash):
            res = probe_tk_ui()
            assert not isinstance(res, tuple)


def test_probe_exceptions_cannot_cause_skip_outcome():
    """Verify exceptions raised by probe_tk_ui prevent pytest skipif from evaluating to True."""
    _probe_cached.cache_clear()
    m_defect = mock.Mock()
    m_defect.communicate.return_value = (json.dumps({"status": "defect", "reason": "Widget flaw"}), "")
    m_defect.returncode = 0

    with mock.patch("subprocess.Popen", return_value=m_defect):
        # Evaluating skip condition raises TkProbeCrash directly, causing test ERROR/FAIL instead of SKIP
        with pytest.raises(TkProbeCrash):
            _ = not probe_tk_ui()[0]

