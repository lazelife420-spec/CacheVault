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
    attempt = _open_clipboard_with_retry(clip, attempts=5, delay_s=0)
    assert clip.calls == 3
    assert attempt == 3


def test_succeeds_immediately_when_uncontended():
    clip = _FlakyClipboard(fail_times=0)
    attempt = _open_clipboard_with_retry(clip, attempts=5, delay_s=0)
    assert clip.calls == 1
    assert attempt == 1


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
    Was 4 x 15ms = 60ms for the original defaults; the delay was reconciled
    to 20ms during the clipboard-custody integration (Gate 5F-B, see
    _CLIPBOARD_OPEN_RETRY_DELAY_S's own comment in paste_delivery.py), so the
    sum below is computed from the live constant rather than hardcoded."""
    sleep_calls: list[float] = []
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: sleep_calls.append(s))

    clip = _FlakyClipboard(fail_times=99)
    with pytest.raises(OSError):
        _open_clipboard_with_retry(clip, attempts=5, delay_s=_CLIPBOARD_OPEN_RETRY_DELAY_S)

    assert clip.calls == 5
    assert len(sleep_calls) == 4, "must sleep only between attempts, never after the last"
    assert sleep_calls == [_CLIPBOARD_OPEN_RETRY_DELAY_S] * 4
    assert sum(sleep_calls) == pytest.approx(_CLIPBOARD_OPEN_RETRY_DELAY_S * 4)


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

    outcome = _write_clipboard_text("hello", operation="test")

    assert outcome.content_set is True
    assert outcome.closed is True
    assert outcome.custody_should_commit is True
    assert outcome.user_visible_success is True
    assert fake.opened == 1
    assert fake.closed == 1
    assert fake.emptied == 1
    assert fake.set_calls == [(13, "hello")]


def test_failed_open_does_not_call_close(monkeypatch):
    fake = _StagedClipboard(fail_stage="OpenClipboard")
    _install_fake_clipboard(monkeypatch, fake)
    # exhaust retries fast
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: None)

    outcome = _write_clipboard_text("hello", operation="test")

    assert outcome.opened is False
    assert outcome.custody_should_commit is False
    assert outcome.user_visible_success is False
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

    outcome = _write_clipboard_text("hello", operation="test")

    assert outcome.content_set is False, "nothing was actually placed on the clipboard"
    assert outcome.custody_should_commit is False
    assert outcome.user_visible_success is False
    assert outcome.error_stage == fail_stage
    assert fake.opened == 1, "OpenClipboard must be attempted exactly once, not retried"
    assert fake.closed == 1, "CloseClipboard must still run after a partial-mutation failure"


def test_close_clipboard_failure_commits_content_but_reports_user_visible_failure(monkeypatch):
    """A close failure AFTER content was genuinely set is a different case
    from a close failure with nothing set: the payload IS on the clipboard
    (custody must commit to suppress recapture), but the transaction did not
    close cleanly, so the UI-facing signal must be False. A single bool
    return value cannot represent this split -- ClipboardWriteOutcome can."""
    class _CloseFailsClipboard(_StagedClipboard):
        def CloseClipboard(self) -> None:
            super().CloseClipboard()
            raise OSError("CloseClipboard failed")

    fake = _CloseFailsClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    # must not raise even though CloseClipboard itself fails
    outcome = _write_clipboard_text("hello", operation="test")
    assert fake.set_calls == [(13, "hello")]  # the content really was set
    assert fake.closed == 1
    assert outcome.content_set is True
    assert outcome.closed is False
    assert outcome.error_stage == "CloseClipboard"
    assert outcome.custody_should_commit is True, "content was set -- must suppress recapture"
    assert outcome.user_visible_success is False, "did not close cleanly -- must not claim success"


def test_diagnostic_logger_failure_after_successful_open_does_not_leak_ownership_or_retry(monkeypatch):
    """If the diagnostic logger itself raises right after OpenClipboard
    succeeds, that must never be mistaken for an OpenClipboard failure (which
    would trigger a second, unbalanced OpenClipboard call and could leak
    clipboard ownership). OpenClipboard must be called exactly once,
    CloseClipboard exactly once, no retry, and the write outcome must be
    based purely on the real clipboard operations -- not on logger
    behavior."""
    import cache_vault.core.capture_debug as capture_debug_mod

    def _raising_log(stage, detail=""):
        raise RuntimeError("simulated broken diagnostics")

    monkeypatch.setattr(capture_debug_mod, "log", _raising_log)

    fake = _StagedClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    outcome = _write_clipboard_text("hello", operation="test")  # must not raise

    assert fake.opened == 1, "OpenClipboard must be called exactly once, not retried"
    assert fake.closed == 1
    assert fake.set_calls == [(13, "hello")]
    assert outcome.content_set is True
    assert outcome.closed is True
    assert outcome.user_visible_success is True, "outcome must reflect clipboard ops, not logger failures"


def test_diagnostic_logger_failure_during_open_retry_failure_logging_does_not_alter_retry(monkeypatch):
    """Logger raises while logging an OpenClipboard retry failure (a
    different call site than the success-path test above) -- must not add
    extra attempts, must not change the exhaustion outcome."""
    import cache_vault.core.capture_debug as capture_debug_mod

    def _raising_log(stage, detail=""):
        raise RuntimeError("simulated broken diagnostics")

    monkeypatch.setattr(capture_debug_mod, "log", _raising_log)
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: None)

    fake = _StagedClipboard(fail_stage="OpenClipboard")
    _install_fake_clipboard(monkeypatch, fake)

    outcome = _write_clipboard_text("hello", operation="test")  # must not raise

    assert fake.opened == 0
    assert fake.closed == 0
    assert outcome.opened is False
    assert outcome.user_visible_success is False


@pytest.mark.parametrize("fail_stage", ["EmptyClipboard", "SetClipboardData"])
def test_diagnostic_logger_failure_during_mutation_failure_logging_does_not_alter_outcome(monkeypatch, fail_stage):
    """Logger raises while logging an EmptyClipboard/SetClipboardData
    failure -- must not alter the real outcome, must not trigger a retry,
    must not skip the guaranteed CloseClipboard."""
    import cache_vault.core.capture_debug as capture_debug_mod

    def _raising_log(stage, detail=""):
        raise RuntimeError("simulated broken diagnostics")

    monkeypatch.setattr(capture_debug_mod, "log", _raising_log)

    fake = _StagedClipboard(fail_stage=fail_stage)
    _install_fake_clipboard(monkeypatch, fake)

    outcome = _write_clipboard_text("hello", operation="test")  # must not raise

    assert fake.opened == 1, "must not retry OpenClipboard due to logger failures"
    assert fake.closed == 1, "CloseClipboard must still run despite the logger failure"
    assert outcome.content_set is False
    assert outcome.error_stage == fail_stage


def test_diagnostic_logger_failure_during_close_failure_logging_does_not_alter_outcome(monkeypatch):
    """Logger raises while logging a CloseClipboard failure -- the write's
    own content_set/closed/custody signals must still be computed purely
    from the real clipboard operations."""
    import cache_vault.core.capture_debug as capture_debug_mod

    def _raising_log(stage, detail=""):
        raise RuntimeError("simulated broken diagnostics")

    monkeypatch.setattr(capture_debug_mod, "log", _raising_log)

    class _CloseFailsClipboard(_StagedClipboard):
        def CloseClipboard(self) -> None:
            super().CloseClipboard()
            raise OSError("CloseClipboard failed")

    fake = _CloseFailsClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    outcome = _write_clipboard_text("hello", operation="test")  # must not raise

    assert fake.opened == 1
    assert fake.closed == 1
    assert outcome.content_set is True
    assert outcome.closed is False
    assert outcome.error_stage == "CloseClipboard"
    assert outcome.custody_should_commit is True
    assert outcome.user_visible_success is False


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

    outcome = _write_clipboard_text("hello", operation="quick_paste_restore")

    assert outcome.user_visible_success is True
    complete = [d for s, d in logged if s == "clipboard_write_stage" and "stage=complete" in d]
    assert complete and "result=ok" in complete[0] and "operation=quick_paste_restore" in complete[0]
    # the deferred OpenClipboard success diagnostic must also have fired,
    # after CloseClipboard was attempted (not before, per _open_clipboard_with_retry).
    open_ok = [d for s, d in logged if s == "clipboard_write_stage" and "stage=OpenClipboard" in d and "result=ok" in d]
    assert open_ok


@pytest.mark.parametrize(
    "fail_stage, expected_complete_result",
    [
        (None, "ok"),
        ("EmptyClipboard", "fail"),
        ("SetClipboardData", "fail"),
    ],
)
def test_complete_diagnostic_reflects_content_and_close_state(monkeypatch, fail_stage, expected_complete_result):
    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))

    fake = _StagedClipboard(fail_stage=fail_stage)
    _install_fake_clipboard(monkeypatch, fake)

    _write_clipboard_text("hello", operation="test")

    complete = [d for s, d in logged if s == "clipboard_write_stage" and "stage=complete" in d]
    assert complete and f"result={expected_complete_result}" in complete[0]


def test_complete_diagnostic_is_partial_success_not_ok_when_content_set_but_close_fails(monkeypatch):
    """A close failure after a successful set must never be reported as a
    plain 'ok' complete -- that would misrepresent an unclean transaction as
    a clean one in the diagnostic trail itself."""
    class _CloseFailsClipboard(_StagedClipboard):
        def CloseClipboard(self) -> None:
            super().CloseClipboard()
            raise OSError("CloseClipboard failed")

    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))

    fake = _CloseFailsClipboard(fail_stage=None)
    _install_fake_clipboard(monkeypatch, fake)

    _write_clipboard_text("hello", operation="test")

    complete = [d for s, d in logged if s == "clipboard_write_stage" and "stage=complete" in d]
    assert complete and "result=partial_success" in complete[0]
    assert not any("result=ok" in d for d in complete)
