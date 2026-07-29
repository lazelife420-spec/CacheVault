"""Unit tests for the OpenClipboard contention retry and stage diagnostics.

Added to fix Quick Paste restoration silently failing when the paste target
window is still consuming the delivered clipboard content at the exact moment
CacheVault attempts the restoration write. Reading the Win32 clipboard API
contract: the paste target briefly holds the clipboard open right after a
synthetic Ctrl+V to read the delivered content, so the restoration write's own
``OpenClipboard`` can race it and raise. That failure was previously swallowed
with no retry and no diagnostic trail. (This is a code-level diagnosis of the
race, not a claim of native/live OS-level reproduction -- none has been
recorded as part of this change.)

See test_clipboard_self_capture.py for the higher-level ``clipboard_restored``
regression that covers the app-level contract, including an integrated test
that drives this exact retry path end-to-end.
"""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import pytest

from cache_vault.core import paste_delivery
from cache_vault.core.paste_delivery import (
    _CLIPBOARD_OPEN_RETRY_ATTEMPTS,
    _CLIPBOARD_OPEN_RETRY_DELAY_S,
    _open_clipboard_with_retry,
    _write_clipboard_text,
)


class _FlakyClipboard:
    """Stands in for win32clipboard: OpenClipboard fails a fixed number of
    times (simulating transient contention) before succeeding."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def OpenClipboard(self) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise OSError("Cannot open Clipboard (transient)")


# --- OpenClipboard retry: attempts, timing, exhaustion ------------------------

def test_retries_and_succeeds_after_transient_contention():
    clip = _FlakyClipboard(fail_times=2)
    _open_clipboard_with_retry(clip, attempts=5, delay_s=0)
    assert clip.calls == 3


def test_succeeds_immediately_when_uncontended():
    clip = _FlakyClipboard(fail_times=0)
    _open_clipboard_with_retry(clip, attempts=5, delay_s=0)
    assert clip.calls == 1


def test_gives_up_after_bounded_attempts_not_indefinitely():
    clip = _FlakyClipboard(fail_times=99)
    with pytest.raises(OSError):
        _open_clipboard_with_retry(clip, attempts=4, delay_s=0)
    assert clip.calls == 4  # bounded -- never retries past the configured cap


def test_default_retry_window_is_small_and_bounded():
    # Guards against the fix regressing into "add a large sleep": contention
    # is normally microseconds to a few ms, so the retry budget must stay tiny.
    assert 2 <= _CLIPBOARD_OPEN_RETRY_ATTEMPTS <= 10


def test_sleeps_only_between_attempts_never_after_the_last(monkeypatch):
    """5 attempts -> at most 4 sleeps (gaps between attempts), never 5.
    For the shipped defaults that is 4 x 15ms = 60ms max, not 75ms."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: sleep_calls.append(s))

    clip = _FlakyClipboard(fail_times=99)
    with pytest.raises(OSError):
        _open_clipboard_with_retry(clip, attempts=5, delay_s=_CLIPBOARD_OPEN_RETRY_DELAY_S)

    assert clip.calls == 5
    assert len(sleep_calls) == 4, "must sleep only between attempts, never after the last"
    assert sleep_calls == [_CLIPBOARD_OPEN_RETRY_DELAY_S] * 4
    assert sum(sleep_calls) == pytest.approx(0.06)


def test_no_sleep_when_first_attempt_succeeds(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: sleep_calls.append(s))

    clip = _FlakyClipboard(fail_times=0)
    _open_clipboard_with_retry(clip, attempts=5, delay_s=_CLIPBOARD_OPEN_RETRY_DELAY_S)

    assert sleep_calls == []


# --- CloseClipboard balance ---------------------------------------------------

class _StagedClipboard:
    """Configurable fake win32clipboard tracking Open/Close balance and which
    stage (if any) raises."""

    def __init__(self, fail_stage: str | None = None) -> None:
        self.fail_stage = fail_stage
        self.opened = 0
        self.closed = 0
        self.emptied = 0
        self.set_calls: list[tuple[int, str]] = []

    def OpenClipboard(self) -> None:
        if self.fail_stage == "OpenClipboard":
            raise OSError("Cannot open Clipboard")
        self.opened += 1

    def EmptyClipboard(self) -> None:
        if self.fail_stage == "EmptyClipboard":
            raise OSError("EmptyClipboard failed")
        self.emptied += 1

    def SetClipboardData(self, fmt, text) -> None:
        if self.fail_stage == "SetClipboardData":
            raise OSError("SetClipboardData failed")
        self.set_calls.append((fmt, text))

    def CloseClipboard(self) -> None:
        self.closed += 1


def _install_fake_clipboard(monkeypatch, fake) -> None:
    fake_module = SimpleNamespace(
        OpenClipboard=fake.OpenClipboard,
        EmptyClipboard=fake.EmptyClipboard,
        SetClipboardData=fake.SetClipboardData,
        CloseClipboard=fake.CloseClipboard,
    )
    monkeypatch.setitem(sys.modules, "win32clipboard", fake_module)
    monkeypatch.setattr(paste_delivery, "win32con", SimpleNamespace(CF_UNICODETEXT=13), raising=False)


def test_successful_open_has_exactly_one_close_in_finally(monkeypatch):
    fake = _StagedClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    ok = _write_clipboard_text("hello", operation="test")

    assert ok is True
    assert fake.opened == 1
    assert fake.closed == 1
    assert fake.emptied == 1
    assert fake.set_calls == [(13, "hello")]


def test_failed_open_does_not_call_close(monkeypatch):
    fake = _StagedClipboard(fail_stage="OpenClipboard")
    _install_fake_clipboard(monkeypatch, fake)
    # exhaust retries fast
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: None)

    ok = _write_clipboard_text("hello", operation="test")

    assert ok is False
    assert fake.opened == 0
    assert fake.closed == 0, "CloseClipboard must never run when OpenClipboard never succeeded"


@pytest.mark.parametrize("fail_stage", ["EmptyClipboard", "SetClipboardData"])
def test_partial_mutation_failure_still_closes_and_is_not_retried(monkeypatch, fail_stage):
    """If OpenClipboard succeeded but a later stage fails, CloseClipboard must
    still run (the clipboard was genuinely opened), and the failure must NOT
    trigger another OpenClipboard retry cycle -- a partial mutation is a
    different failure class than contention and isn't safe to blindly retry."""
    fake = _StagedClipboard(fail_stage=fail_stage)
    _install_fake_clipboard(monkeypatch, fake)

    ok = _write_clipboard_text("hello", operation="test")

    assert ok is False
    assert fake.opened == 1, "OpenClipboard must be attempted exactly once, not retried"
    assert fake.closed == 1, "CloseClipboard must still run after a partial-mutation failure"


def test_close_clipboard_failure_is_logged_but_does_not_raise(monkeypatch):
    class _CloseFailsClipboard(_StagedClipboard):
        def CloseClipboard(self) -> None:
            super().CloseClipboard()
            raise OSError("CloseClipboard failed")

    fake = _CloseFailsClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    # must not raise even though CloseClipboard itself fails
    ok = _write_clipboard_text("hello", operation="test")
    assert ok is True  # the mutation itself (Empty+Set) succeeded
    assert fake.closed == 1


# --- diagnostics: operation, stage, attempt, total_attempts, error_code -------

def test_diagnostics_capture_operation_stage_attempt_and_error_code(monkeypatch):
    # capture_debug is imported lazily inside the functions under test, so
    # patch the module it's imported from directly.
    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: None)

    class _Err(OSError):
        winerror = 1418  # ERROR_CLIPBOARD_NOT_OPEN, arbitrary realistic code

    class _AlwaysFails:
        def OpenClipboard(self):
            raise _Err("Cannot open Clipboard")

    with pytest.raises(_Err):
        _open_clipboard_with_retry(_AlwaysFails(), operation="quick_paste_restore", attempts=3, delay_s=0)

    stage_logs = [detail for stage, detail in logged if stage == "clipboard_write_stage"]
    assert len(stage_logs) == 3, "one diagnostic line per attempt"
    for i, detail in enumerate(stage_logs, start=1):
        assert "operation=quick_paste_restore" in detail
        assert "stage=OpenClipboard" in detail
        assert "result=fail" in detail
        assert f"attempt={i}" in detail
        assert "total_attempts=3" in detail
        assert "error_code=1418" in detail
        assert "error_type=_Err" in detail


def test_diagnostics_final_result_logged_on_success(monkeypatch):
    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))

    fake = _StagedClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    ok = _write_clipboard_text("hello", operation="quick_paste_restore")

    assert ok is True
    complete = [d for s, d in logged if s == "clipboard_write_stage" and "stage=complete" in d]
    assert complete and "result=ok" in complete[0] and "operation=quick_paste_restore" in complete[0]
