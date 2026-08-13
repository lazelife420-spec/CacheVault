"""Quick Paste must not take the clipboard back before the paste lands.

Both defects here were found by driving the real app against a real Windows
target (Notepad) and reading back what it actually received:

* with "restore clipboard after paste" on, the target pasted the *previous*
  clipboard instead of the chosen clip, 5/5 trials, because the restore ran on
  the line after deliver_ctrl_v while the target consumes the keystroke
  asynchronously (restore at +0.170s, target read at +0.34s);
* with auto-paste off, the chosen clip was wiped from the clipboard
  immediately, 3/3 trials, making Quick Paste do nothing at all.

These exercise the real _do_paste with a stand-in for the Tk app, so the
ordering decisions are tested rather than the source text.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cache_vault.core import models
from cache_vault.ui import shell as shell_mod
from cache_vault.ui.shell import CacheVaultApp


class FakeApp:
    """Only the surface _do_paste actually touches."""

    def __init__(self, *, auto_paste=True, restore=True, target=1234):
        self.vault = SimpleNamespace(
            settings=SimpleNamespace(
                auto_paste=auto_paste,
                restore_clipboard_after_paste=restore,
            ),
            events=SimpleNamespace(record=lambda *a, **k: None),
        )
        self.events = []
        self.vault.events.record = (
            lambda name, cid, details: self.events.append(name))
        self._monitor = SimpleNamespace(note_local_copy=lambda _t: None)
        self._paste_target = target
        self.scheduled = []
        self.finished = []
        self.alive = True

    # --- the bits _do_paste calls on itself
    def _locked(self):
        return False

    def _guard_unlocked(self):
        pass

    def _alive(self):
        return self.alive

    def after(self, delay, func=None, *args):
        self.scheduled.append((delay, func, args))
        return f"after#{len(self.scheduled)}"

    def _quick_paste_text_for_action(self, clip, action):
        return clip.content

    def _finish_paste(self, clip, ok, item_type, title, reason, clipboard_restored):
        self.finished.append(
            {"ok": ok, "reason": reason, "clipboard_restored": clipboard_restored})

    # --- bind the real implementations under test
    _do_paste = CacheVaultApp._do_paste
    if hasattr(CacheVaultApp, "_schedule_clipboard_restore"):
        # Bound conditionally so this file still *runs* against a build without
        # the fix: those runs must fail on behaviour, not on collection.
        _schedule_clipboard_restore = CacheVaultApp._schedule_clipboard_restore

    def run_scheduled(self):
        """Fire every pending callback, innermost first."""
        while self.scheduled:
            _delay, func, args = self.scheduled.pop(0)
            if func is not None:
                func(*args)


@pytest.fixture
def clipboard(monkeypatch):
    state = {"value": "PRIOR USER CLIPBOARD", "restores": [], "written": []}

    def _write(_widget, text):
        state["value"] = text
        state["written"].append(text)
        return text

    def _restore(text):
        state["value"] = text
        state["restores"].append(text)
        return True

    monkeypatch.setattr(shell_mod.clipboard_out, "write_via_tk", _write)
    monkeypatch.setattr(shell_mod, "restore_clipboard_text", _restore)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: state["value"])
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda *_a: False)
    state["toasts"] = []
    monkeypatch.setattr(
        shell_mod, "Toast",
        lambda _parent, message="", *a, **k: state["toasts"].append(message))
    return state


def _clip(content="line one\nline two"):
    return SimpleNamespace(
        id="clip-1", content=content, content_type=models.CONTENT_TEXT,
        classification=models.CLASS_PLAIN, is_sensitive=False)


def _delivers(monkeypatch, ok=True):
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda _t: SimpleNamespace(ok=ok, reason="ok" if ok else "focus_restore_failed",
                                   target_title="Notepad"))


# --- defect 1: the restore raced the paste --------------------------------

def test_restore_is_deferred_not_run_beside_the_keystroke(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp()
    clip = _clip()
    app._do_paste(clip)

    # _deliver itself is deferred; run it, then check the clipboard still holds
    # the clip -- the target has not been given a chance to read it yet.
    deliver = app.scheduled.pop(0)
    deliver[1]()
    assert clipboard["value"] == clip.content, (
        "the clip must still be on the clipboard when the keystroke is sent")
    assert clipboard["restores"] == [], "the restore must not run inline"
    assert app.scheduled, "a deferred restore should have been scheduled"


def test_deferred_restore_puts_the_previous_clipboard_back(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp()
    app._do_paste(_clip())
    app.run_scheduled()
    assert clipboard["restores"] == ["PRIOR USER CLIPBOARD"]
    assert clipboard["value"] == "PRIOR USER CLIPBOARD"


def test_restore_delay_outlasts_the_measured_target_read(clipboard, monkeypatch):
    """The target was measured reading the clipboard ~170ms after delivery."""
    _delivers(monkeypatch)
    app = FakeApp()
    app._do_paste(_clip())
    app.scheduled.pop(0)[1]()          # run _deliver
    assert app.scheduled, "no deferred restore was scheduled at all"
    delay = app.scheduled[0][0]
    assert delay >= 250, f"restore delay {delay}ms is too tight for the target"


def test_late_restore_does_not_clobber_a_newer_user_copy(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp()
    app._do_paste(_clip())
    app.scheduled.pop(0)[1]()          # deliver; clip is on the clipboard
    assert app.scheduled, "no deferred restore was scheduled at all"
    clipboard["value"] = "USER COPIED SOMETHING ELSE"
    app.run_scheduled()                # the deferred restore fires late
    assert clipboard["restores"] == []
    assert clipboard["value"] == "USER COPIED SOMETHING ELSE"


def test_no_restore_when_delivery_failed(clipboard, monkeypatch):
    """A failed paste must leave the clip available for a manual Ctrl+V."""
    _delivers(monkeypatch, ok=False)
    app = FakeApp()
    clip = _clip()
    app._do_paste(clip)
    app.run_scheduled()
    assert clipboard["restores"] == []
    assert clipboard["value"] == clip.content
    assert app.finished[-1]["clipboard_restored"] is False


def test_finish_paste_is_told_the_truth_about_restoring(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp()
    app._do_paste(_clip())
    app.run_scheduled()
    assert app.finished[-1]["clipboard_restored"] is True


# --- a restore that cannot get the clipboard must not fail silently -------
# Measured natively: another process holding the clipboard via a real window
# handle makes restore_clipboard_text exhaust its ~0.4s OpenClipboard bound and
# return False, which would otherwise leave the pasted clip on the user's
# clipboard with no indication anything went wrong.

def test_restore_is_retried_when_the_clipboard_is_held(clipboard, monkeypatch):
    _delivers(monkeypatch)
    attempts = {"n": 0}

    def _busy(_text):
        attempts["n"] += 1
        return False                      # someone else owns the clipboard

    monkeypatch.setattr(shell_mod, "restore_clipboard_text", _busy)
    app = FakeApp()
    app._do_paste(_clip())
    app.run_scheduled()
    assert attempts["n"] == shell_mod.CLIPBOARD_RESTORE_ATTEMPTS


def test_exhausted_restore_tells_the_user(clipboard, monkeypatch):
    _delivers(monkeypatch)
    monkeypatch.setattr(shell_mod, "restore_clipboard_text", lambda _t: False)
    app = FakeApp()
    app._do_paste(_clip())
    app.run_scheduled()
    assert clipboard["toasts"], "a silent failure leaves the wrong clipboard"
    assert "clipboard" in clipboard["toasts"][-1].lower()
    assert "clipboard_restore_failed" in app.events


def test_a_retry_that_succeeds_stays_quiet(clipboard, monkeypatch):
    _delivers(monkeypatch)
    calls = {"n": 0}

    def _second_time_lucky(text):
        calls["n"] += 1
        if calls["n"] < 2:
            return False
        clipboard["value"] = text
        return True

    monkeypatch.setattr(shell_mod, "restore_clipboard_text", _second_time_lucky)
    app = FakeApp()
    app._do_paste(_clip())
    app.run_scheduled()
    assert calls["n"] == 2
    assert clipboard["toasts"] == []
    assert "clipboard_restore_failed" not in app.events


# --- defect 2: auto-paste off wiped the chosen clip -----------------------

def test_clip_survives_when_auto_paste_is_off(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp(auto_paste=False)
    clip = _clip()
    app._do_paste(clip)
    app.run_scheduled()
    assert clipboard["value"] == clip.content, (
        "with auto-paste off the chosen clip is the entire point")
    assert clipboard["restores"] == []
    assert app.finished[-1]["clipboard_restored"] is False


def test_clip_survives_when_there_is_no_target_window(clipboard, monkeypatch):
    _delivers(monkeypatch)
    app = FakeApp(target=None)
    clip = _clip()
    app._do_paste(clip)
    app.run_scheduled()
    assert clipboard["value"] == clip.content
    assert app.finished[-1]["reason"] == "no_target_window"
