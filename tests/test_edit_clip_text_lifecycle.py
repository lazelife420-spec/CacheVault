"""EditClipTextDialog close/destroy lifecycle.

Manual packaged-build QA found that saving and closing this dialog produced
a brief Windows "Not Responding" flicker in 2 of 5 runs, correlated 5/5 with
a "bad window path name" TclError logged from CustomTkinter's own Windows
dark-titlebar workaround (CTkToplevel._windows_set_titlebar_color): it
records whatever widget has focus, and later schedules
``self.after(10, that_widget.focus)`` to restore it. If this dialog's
textbox has already been torn down by the time that fires, the callback
raises trying to touch a widget whose Tcl window no longer exists.

destroy() now withdraws immediately (so the dialog visually disappears at
once and the grab/parent-focus handoff happens synchronously) but defers
the actual widget teardown by 50ms -- long enough for CustomTkinter's own
~20ms internal callback chain to either fire harmlessly against the
still-alive (merely hidden) window, or find it already gone and skip via
its own guards.
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.clip_workflows import EditClipTextDialog
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()
pytestmark = pytest.mark.skipif(not OK, reason=REASON)


def _pump(widget, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        widget.update()
        time.sleep(0.01)


def _make_dialog(tk_root, on_save=None):
    return EditClipTextDialog(
        tk_root,
        title="Edit",
        initial_text="hello world",
        on_save=on_save or (lambda t: None),
    )


class _CallbackErrorRecorder:
    """Swaps in a report_callback_exception recorder on a real Tk root so
    a test can assert no TclError (e.g. "bad window path name") escaped
    from a deferred after()-callback, without needing app.py's
    production crash-log wrapper installed."""

    def __init__(self, root):
        self.root = root
        self.errors: list[BaseException] = []
        self._original = root.report_callback_exception

    def __enter__(self):
        def _record(exc, val, tb):
            self.errors.append(val)
        self.root.report_callback_exception = _record
        return self

    def __exit__(self, *a):
        self.root.report_callback_exception = self._original

    def has_bad_window_path(self) -> bool:
        return any("bad window path name" in str(e) for e in self.errors)


def test_save_then_immediate_destroy_produces_no_stale_focus_set_error(tk_root):
    """Worst case for the race: destroy() called the instant after
    construction, maximizing the chance CustomTkinter's own pending
    focus-restore callback still targets a live textbox reference."""
    with _CallbackErrorRecorder(tk_root) as rec:
        dialog = _make_dialog(tk_root)
        dialog.destroy()
        _pump(tk_root, 0.3)  # let any of CustomTkinter's ~20ms chain fire

    assert not rec.has_bad_window_path(), rec.errors


def test_save_path_then_close_produces_no_stale_focus_set_error(tk_root):
    """The actual reported workflow: type, then Save (which internally
    calls destroy() from EditClipTextDialog._save)."""
    saved = []
    with _CallbackErrorRecorder(tk_root) as rec:
        dialog = _make_dialog(tk_root, on_save=lambda t: saved.append(t))
        dialog._body.delete("1.0", "end")
        dialog._body.insert("1.0", "edited text")
        dialog._save()
        _pump(tk_root, 0.3)

    assert saved == ["edited text"]
    assert not rec.has_bad_window_path(), rec.errors


def test_repeated_destroy_calls_are_idempotent(tk_root):
    dialog = _make_dialog(tk_root)
    dialog.destroy()
    # A second (and third) call must not raise, double-schedule teardown,
    # or double-run any of the close-time side effects.
    dialog.destroy()
    dialog.destroy()
    _pump(tk_root, 0.3)
    assert dialog._closing is True


def test_grab_is_released_on_destroy(tk_root):
    dialog = _make_dialog(tk_root)
    _pump(tk_root, 0.3)  # let the deferred _bring_to_front raise/grab_set fire
    dialog.destroy()
    assert tk_root.grab_current() is None


def test_parent_focus_restoration_is_guarded_when_parent_gone():
    """If the master has already been destroyed by the time this dialog
    closes, restoring focus to it must not raise."""
    import customtkinter as ctk

    ok, reason = probe_tk_ui()
    if not ok:
        pytest.skip(reason)
    root = ctk.CTk()
    root.withdraw()
    try:
        dialog = _make_dialog(root)
        root.destroy()  # parent gone before the dialog closes
        dialog.destroy()  # must not raise
    finally:
        try:
            dialog.destroy()
        except Exception:  # noqa: BLE001
            pass


def test_parent_focus_restoration_runs_when_parent_alive(tk_root):
    dialog = _make_dialog(tk_root)
    _pump(tk_root, 0.3)
    dialog.destroy()
    # No assertion beyond "did not raise" is reliable across window
    # managers for actual OS focus, but the call must have been attempted
    # against a still-alive, guarded target.
    assert tk_root.winfo_exists()


def test_destroy_withdraws_immediately_without_blocking_parent(tk_root):
    dialog = _make_dialog(tk_root)
    _pump(tk_root, 0.3)
    dialog.destroy()
    # Withdrawal (and grab release) must happen synchronously, before the
    # deferred final teardown -- the dialog must not remain visible/mapped
    # even though its widgets aren't torn down for another 50ms.
    assert dialog.winfo_viewable() == 0
    assert tk_root.grab_current() is None
    # Parent must stay fully interactive immediately, not just eventually.
    tk_root.focus_set()
    tk_root.update()


def test_delayed_teardown_eventually_destroys_the_window(tk_root):
    dialog = _make_dialog(tk_root)
    dialog.destroy()
    _pump(tk_root, 0.3)
    assert not dialog.winfo_exists()
