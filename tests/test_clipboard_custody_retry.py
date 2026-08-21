"""Clipboard custody: snapshot/restore must not give up on a transient lock.

Windows allows one clipboard owner at a time, so OpenClipboard fails outright
whenever anything else holds it at that instant -- including Tk releasing its own
ownership. A single attempt therefore made the snapshot/restore pair that wraps
Quick Paste silently fail, leaving the user's clipboard holding pasted clip
content instead of whatever they had before.

Observed for real while validating this lane: a probe's restore step returned
False on the first attempt and the prior clipboard content was lost.
"""

from __future__ import annotations

import sys
import types

import pytest

from cache_vault.core import paste_delivery


class _FakeClipboard:
    """A win32clipboard stand-in that refuses to open the first ``fail`` times."""

    CF_UNICODETEXT = 13

    def __init__(self, fail: int, initial: str | None = None):
        self.remaining_failures = fail
        self.open_attempts = 0
        self.data = initial
        self.is_open = False

    def OpenClipboard(self, *_a):  # noqa: N802 - mirrors the win32 API
        self.open_attempts += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise OSError("clipboard is held by another process")
        self.is_open = True

    def CloseClipboard(self, *_a):  # noqa: N802
        self.is_open = False

    def EmptyClipboard(self, *_a):  # noqa: N802
        assert self.is_open
        self.data = None

    def SetClipboardData(self, _fmt, data):  # noqa: N802
        assert self.is_open
        self.data = data

    def IsClipboardFormatAvailable(self, _fmt):  # noqa: N802
        return self.data is not None

    def GetClipboardData(self, _fmt):  # noqa: N802
        assert self.is_open
        return self.data


@pytest.fixture
def fake_clipboard(monkeypatch):
    def _install(fail: int, initial: str | None = None) -> _FakeClipboard:
        fake = _FakeClipboard(fail, initial)
        module = types.ModuleType("win32clipboard")
        for name in ("OpenClipboard", "CloseClipboard", "EmptyClipboard",
                     "SetClipboardData", "IsClipboardFormatAvailable",
                     "GetClipboardData"):
            setattr(module, name, getattr(fake, name))
        monkeypatch.setitem(sys.modules, "win32clipboard", module)
        monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True)
        # Adapted during the clipboard-custody integration (Gate 5F-B):
        # _open_clipboard/_CLIPBOARD_OPEN_ATTEMPTS/_CLIPBOARD_OPEN_DELAY were
        # replaced by _open_clipboard_with_retry/_CLIPBOARD_OPEN_RETRY_ATTEMPTS/
        # _CLIPBOARD_OPEN_RETRY_DELAY_S, reconciled to a value that still
        # survives this file's real-observed 5-consecutive-failure scenario.
        # _open_clipboard_with_retry's delay_s is a default *parameter* value
        # bound at function-definition time, not a dynamic module-global
        # lookup like the old _open_clipboard's -- monkeypatching the module
        # attribute alone wouldn't reach it, so patch time.sleep instead to
        # keep these tests instant.
        monkeypatch.setattr(paste_delivery.time, "sleep", lambda *_a, **_k: None)
        return fake

    return _install


def test_restore_retries_a_held_clipboard(fake_clipboard):
    fake = fake_clipboard(fail=5)
    assert paste_delivery.restore_clipboard_text("the user's own text") is True
    assert fake.data == "the user's own text"
    assert fake.open_attempts == 6


def test_restore_gives_up_after_the_bounded_number_of_attempts(fake_clipboard):
    fake = fake_clipboard(fail=10_000)
    assert paste_delivery.restore_clipboard_text("text") is False
    assert fake.open_attempts == paste_delivery._CLIPBOARD_OPEN_RETRY_ATTEMPTS
    assert fake.is_open is False


def test_snapshot_retries_a_held_clipboard(fake_clipboard):
    fake = fake_clipboard(fail=3, initial="prior content")
    assert paste_delivery.snapshot_clipboard_text() == "prior content"
    assert fake.open_attempts == 4


def test_set_clipboard_text_retries_a_held_clipboard(fake_clipboard):
    fake = fake_clipboard(fail=4)
    assert paste_delivery.set_clipboard_text("a\nb") is True
    assert fake.data == "a\r\nb"


def test_snapshot_then_restore_round_trip_is_byte_exact(fake_clipboard):
    original = "kept\r\n\r\nexactly  \tas found\r"
    fake = fake_clipboard(fail=2, initial=original)
    prior = paste_delivery.snapshot_clipboard_text()
    assert prior == original
    # Something else uses the clipboard in between.
    paste_delivery.set_clipboard_text("temporary paste payload")
    assert fake.data != original
    assert paste_delivery.restore_clipboard_text(prior) is True
    assert fake.data == original
