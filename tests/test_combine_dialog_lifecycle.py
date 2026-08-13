"""Combine Clips dialog lifecycle.

User report: the Combine popup stayed open after the combine had already
succeeded, so it had to be dismissed by hand.

Cause: ``ClipComposerDialog._copy`` ran ``on_copy`` and returned, never closing,
while the two save buttons closed from a ``finally:`` -- which had the opposite
bug, closing (and discarding the edited text) even when the save had raised.

Contract now: an action closes the dialog only after it has actually succeeded,
runs at most once, and leaves the dialog usable when it cannot run.
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.clip_workflows import ClipComposerDialog
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()
pytestmark = pytest.mark.skipif(not OK, reason=REASON)

PARTS = ["first clip\nsecond line", "another clip"]


def _pump(widget, seconds: float = 0.15) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            widget.update()
        except Exception:  # noqa: BLE001 - widget may be gone mid-pump
            return
        time.sleep(0.01)


def _make(tk_root, *, on_copy=None, on_save_clip=None, on_save_macro=None):
    return ClipComposerDialog(
        tk_root,
        parts=list(PARTS),
        on_copy=on_copy or (lambda _t: None),
        on_save_clip=on_save_clip or (lambda _t: None),
        on_save_macro=on_save_macro or (lambda _t: None),
    )


def _alive(dialog) -> bool:
    try:
        return bool(dialog.winfo_exists())
    except Exception:  # noqa: BLE001
        return False


# --- successful actions dismiss ------------------------------------------------

def test_successful_copy_dismisses_the_dialog(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    dialog._copy()
    _pump(tk_root)
    assert copied, "the combine must actually have run"
    assert not _alive(dialog), "a successful combine must close the dialog"


def test_successful_copy_runs_exactly_once(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    dialog._copy()
    _pump(tk_root)
    assert len(copied) == 1


def test_repeated_copy_invocation_cannot_combine_twice(tk_root):
    """A second click, or a duplicate event, must not produce a second result."""
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    dialog._copy()
    dialog._copy()
    dialog._copy()
    _pump(tk_root)
    assert len(copied) == 1


def test_successful_save_clip_dismisses_and_saves_once(tk_root):
    saved = []
    dialog = _make(tk_root, on_save_clip=saved.append)
    dialog._save_clip()
    dialog._save_clip()
    _pump(tk_root)
    assert len(saved) == 1
    assert not _alive(dialog)


def test_successful_save_macro_dismisses_and_saves_once(tk_root):
    saved = []
    dialog = _make(tk_root, on_save_macro=saved.append)
    dialog._save_macro()
    dialog._save_macro()
    _pump(tk_root)
    assert len(saved) == 1
    assert not _alive(dialog)


# --- failed actions keep the dialog -------------------------------------------

def test_failed_copy_keeps_the_dialog_open(tk_root):
    def boom(_text):
        raise RuntimeError("clipboard unavailable")

    dialog = _make(tk_root, on_copy=boom)
    with pytest.raises(RuntimeError):
        dialog._copy()
    _pump(tk_root)
    assert _alive(dialog), "a failed combine must not close over the user's text"
    try:
        assert dialog._copy_btn.cget("state") == "normal", "must be retryable"
        assert dialog._text().strip(), "the composed text must still be there"
    finally:
        dialog.destroy()


def test_failed_save_keeps_the_dialog_open(tk_root):
    def boom(_text):
        raise RuntimeError("storage unavailable")

    dialog = _make(tk_root, on_save_clip=boom)
    with pytest.raises(RuntimeError):
        dialog._save_clip()
    _pump(tk_root)
    assert _alive(dialog)
    try:
        assert dialog._save_clip_btn.cget("state") == "normal"
    finally:
        dialog.destroy()


def test_retry_after_failure_succeeds(tk_root):
    calls = []

    def flaky(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("transient")

    dialog = _make(tk_root, on_copy=flaky)
    with pytest.raises(RuntimeError):
        dialog._copy()
    _pump(tk_root)
    assert _alive(dialog)
    dialog._copy()
    _pump(tk_root)
    assert len(calls) == 2
    assert not _alive(dialog)


# --- nothing to combine -------------------------------------------------------

def test_empty_buffer_disables_actions_and_keeps_dialog(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    try:
        dialog._body.delete("1.0", "end")
        dialog._on_body_edited()
        _pump(tk_root)
        assert dialog._copy_btn.cget("state") == "disabled"
        assert dialog._save_clip_btn.cget("state") == "disabled"
        dialog._copy()
        _pump(tk_root)
        assert copied == [], "an empty buffer must not be combined"
        assert _alive(dialog), "the dialog stays so the user can fix the input"
    finally:
        if _alive(dialog):
            dialog.destroy()


def test_whitespace_only_buffer_is_treated_as_empty(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    try:
        dialog._body.delete("1.0", "end")
        dialog._body.insert("1.0", "   \n\t\n  ")
        dialog._on_body_edited()
        assert dialog.has_composable_text() is False
        assert dialog._copy_btn.cget("state") == "disabled"
        dialog._copy()
        assert copied == []
        assert _alive(dialog)
    finally:
        if _alive(dialog):
            dialog.destroy()


def test_typing_content_re_enables_the_actions(tk_root):
    dialog = _make(tk_root)
    try:
        dialog._body.delete("1.0", "end")
        dialog._on_body_edited()
        assert dialog._copy_btn.cget("state") == "disabled"
        dialog._body.insert("1.0", "now there is text")
        dialog._on_body_edited()
        assert dialog._copy_btn.cget("state") == "normal"
    finally:
        dialog.destroy()


# --- a declined action is not a successful one ---------------------------------
# vault.capture returns None when it declines (duplicate suppression, sensitive
# content rules, capture paused). The shell callbacks report that as False, and
# "the callback returned" must not be mistaken for "the combine happened".

def test_declined_save_keeps_the_dialog_open(tk_root):
    dialog = _make(tk_root, on_save_clip=lambda _t: False)
    dialog._save_clip()
    _pump(tk_root)
    assert _alive(dialog), "a declined save must not discard the composed text"
    try:
        assert dialog._save_clip_btn.cget("state") == "normal"
        assert dialog._text().strip()
    finally:
        dialog.destroy()


def test_declined_copy_keeps_the_dialog_open(tk_root):
    dialog = _make(tk_root, on_copy=lambda _t: False)
    dialog._copy()
    _pump(tk_root)
    assert _alive(dialog)
    try:
        assert dialog._copy_btn.cget("state") == "normal"
    finally:
        dialog.destroy()


def test_declined_then_accepted_save_closes(tk_root):
    results = [False, True]
    calls = []

    def on_save(text):
        calls.append(text)
        return results.pop(0)

    dialog = _make(tk_root, on_save_clip=on_save)
    dialog._save_clip()
    _pump(tk_root)
    assert _alive(dialog)
    dialog._save_clip()
    _pump(tk_root)
    assert len(calls) == 2
    assert not _alive(dialog)


def test_callback_returning_none_still_counts_as_success(tk_root):
    """Most callbacks return nothing; that must keep meaning success."""
    dialog = _make(tk_root, on_copy=lambda _t: None)
    dialog._copy()
    _pump(tk_root)
    assert not _alive(dialog)


# --- the failure has to be visible --------------------------------------------
# Found by a native run of the real dialog: after a withheld save the dialog
# correctly stayed open, but the status line was empty, because _action_failed
# set the message and then _sync_action_states cleared it again. The user was
# left with a dialog that had simply refused to close, with no reason given.

def test_withheld_save_leaves_a_visible_reason(tk_root):
    dialog = _make(tk_root, on_save_clip=lambda _t: False)
    dialog._save_clip()
    _pump(tk_root)
    try:
        status = dialog._status.cget("text")
        assert status.strip(), "the dialog must say why it stayed open"
        assert "still here" in status
    finally:
        dialog.destroy()


def test_failed_copy_leaves_a_visible_reason(tk_root):
    def boom(_text):
        raise RuntimeError("clipboard unavailable")

    dialog = _make(tk_root, on_copy=boom)
    with pytest.raises(RuntimeError):
        dialog._copy()
    _pump(tk_root)
    try:
        assert dialog._status.cget("text").strip()
    finally:
        dialog.destroy()


def test_editing_does_not_erase_the_failure_notice(tk_root):
    """A state sync triggered by ordinary editing must not wipe the notice."""
    dialog = _make(tk_root, on_save_clip=lambda _t: False)
    dialog._save_clip()
    _pump(tk_root)
    try:
        dialog._body.insert("end", " more text")
        dialog._on_body_edited()
        _pump(tk_root)
        assert dialog._status.cget("text").strip()
    finally:
        dialog.destroy()


def test_a_new_attempt_clears_the_previous_notice(tk_root):
    results = [False, True]
    dialog = _make(tk_root, on_save_clip=lambda _t: results.pop(0))
    dialog._save_clip()
    _pump(tk_root)
    assert dialog._status.cget("text").strip()
    dialog._save_clip()
    _pump(tk_root)
    assert not _alive(dialog), "the retry succeeded, so it closed"


def test_empty_buffer_hint_still_clears_once_there_is_text(tk_root):
    dialog = _make(tk_root)
    try:
        dialog._body.delete("1.0", "end")
        dialog._on_body_edited()
        dialog._copy()
        assert dialog._status.cget("text").strip()
        dialog._body.insert("1.0", "text again")
        dialog._on_body_edited()
        _pump(tk_root)
        assert dialog._status.cget("text") == ""
    finally:
        dialog.destroy()


# --- teardown must not raise into the crash log -------------------------------

def test_close_does_not_raise_stale_focus_error(tk_root):
    """A native run logged "bad window path name .!clipcomposerdialog" from
    CustomTkinter's own deferred focus restore firing after teardown."""
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda _e, val, _tb: errors.append(val)
    try:
        dialog = _make(tk_root)
        _pump(tk_root, 0.3)
        dialog.destroy()
        _pump(tk_root, 0.4)
    finally:
        tk_root.report_callback_exception = original
    assert not any("bad window path name" in str(e) for e in errors), errors


def test_repeated_destroy_is_idempotent(tk_root):
    dialog = _make(tk_root)
    dialog.destroy()
    dialog.destroy()
    dialog.destroy()
    _pump(tk_root, 0.3)
    assert dialog._closing is True


def test_destroy_releases_the_grab(tk_root):
    dialog = _make(tk_root)
    _pump(tk_root, 0.3)
    dialog.destroy()
    _pump(tk_root, 0.3)
    assert tk_root.grab_current() is None


# --- closing is not combining -------------------------------------------------

def test_close_does_not_combine(tk_root):
    copied, saved = [], []
    dialog = _make(tk_root, on_copy=copied.append, on_save_clip=saved.append)
    dialog.destroy()
    _pump(tk_root)
    assert copied == [] and saved == []


# --- the dialog must not damage the text it hands over ------------------------

def test_dialog_hands_over_text_with_blank_lines_intact(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    body = "line one\n\nline three  \n\tindented"
    dialog._body.delete("1.0", "end")
    dialog._body.insert("1.0", body)
    dialog._on_body_edited()
    dialog._copy()
    _pump(tk_root)
    assert copied == [body], "leading/trailing/interior whitespace must survive"


def test_dialog_preserves_user_leading_and_trailing_blank_lines(tk_root):
    copied = []
    dialog = _make(tk_root, on_copy=copied.append)
    body = "\n\nkept\n\n"
    dialog._body.delete("1.0", "end")
    dialog._body.insert("1.0", body)
    dialog._on_body_edited()
    dialog._copy()
    _pump(tk_root)
    assert copied == [body]


def test_initial_body_preserves_source_clip_interiors(tk_root):
    parts = ["alpha\n\nbeta", "gamma"]
    dialog = ClipComposerDialog(
        tk_root, parts=parts,
        on_copy=lambda _t: None, on_save_clip=lambda _t: None,
        on_save_macro=lambda _t: None,
    )
    try:
        assert dialog._text() == "alpha\n\nbeta\n\ngamma"
    finally:
        dialog.destroy()
