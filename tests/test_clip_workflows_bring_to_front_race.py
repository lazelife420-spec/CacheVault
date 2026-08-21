"""Real-Tk proof of the _bring_to_front teardown race through an actual
affected dialog's close path (EditClipTextDialog).

Companion to tests/test_dialog_bring_to_front_teardown_race.py, which proves
the mechanism deterministically via a fake scheduler. This file drives the
real, unmodified widget instead, timed against the real Tk event loop, to
confirm the deterministic proof reflects what actually happens in the shipped
app -- not just an idealized model of it.

EditClipTextDialog.destroy() withdraws immediately and defers the real
super().destroy() by 50ms (see its own docstring for why). Scheduling
destroy() at 180ms after construction lands inside the vulnerable window:
_bring_to_front's _raise() fires at the fixed 200ms mark while the widget is
still alive (only withdrawn, not yet actually destroyed at 180+50=230ms).
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.clip_workflows import EditClipTextDialog
from cache_vault.ui.dialogs import AboutDialog
from tests.tk_support import probe_tk_ui

OK, REASON = probe_tk_ui()


def _pump(widget, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        widget.update()
        time.sleep(0.01)


def _make_dialog(tk_root):
    return EditClipTextDialog(
        tk_root, title="Edit", initial_text="hello world",
        on_save=lambda _t: None,
    )


def _track_reshow_calls(dialog) -> list:
    """Instance-level wrap (not class-level -- must not affect other tests
    or other dialog instances) around the exact methods _raise() calls,
    recording (name, monotonic_time) for each without changing real
    behavior. Timestamped rather than filtered-by-a-settle-pump: CustomTkinter
    itself calls deiconify() once, immediately at construction (~0.1ms,
    confirmed by direct timing) as part of its own normal window-draw cycle
    -- unrelated to the teardown race -- and a fixed settle delay before
    scheduling destroy() would shift destroy() outside the 150-200ms
    vulnerable window this test targets. Timestamping instead lets the
    assertion distinguish "called before destroy()" (legitimate) from
    "called after destroy() began" (the defect) without touching timing
    elsewhere in the test.
    """
    calls: list[tuple[str, float]] = []
    for name in ("deiconify", "lift", "focus_force", "grab_set"):
        original = getattr(dialog, name)

        def _wrapped(_name=name, _original=original):
            calls.append((_name, time.monotonic()))
            return _original()

        setattr(dialog, name, _wrapped)
    return calls


@pytest.mark.skipif(not OK, reason=REASON)
def test_destroy_during_the_staged_teardown_window_leaves_the_dialog_gone(tk_root):
    """The real-dialog proof: destroy() scheduled at 180ms (inside the
    150-200ms vulnerable window), pumped past both _raise()'s 200ms mark and
    _finalize_destroy's 230ms mark. The dialog must end up destroyed, not
    resurrected, and nothing tracked may fire after destroy() begins."""
    dialog = _make_dialog(tk_root)
    calls = _track_reshow_calls(dialog)

    destroy_at = {}

    def _destroy_and_stamp():
        destroy_at["t"] = time.monotonic()
        dialog.destroy()

    tk_root.after(180, _destroy_and_stamp)
    _pump(tk_root, 0.4)

    assert "t" in destroy_at, "destroy() was never actually invoked"
    late_calls = [(n, t) for n, t in calls if t >= destroy_at["t"]]
    assert late_calls == [], (
        "a dialog closed inside the staged-teardown race window must not "
        f"be deiconified/lifted/focused/grabbed afterward, but saw: {late_calls} "
        f"(destroy() began at {destroy_at['t']}; full call log: {calls})"
    )
    assert not dialog.winfo_exists(), "the dialog must end up actually destroyed"


@pytest.mark.skipif(not OK, reason=REASON)
def test_normal_bring_to_front_still_raises_a_live_dialog(tk_root):
    """The fix must not break the feature: a dialog that is never closed
    during the window must still be raised/focused/grabbed at 200ms."""
    dialog = _make_dialog(tk_root)
    calls = _track_reshow_calls(dialog)

    _pump(tk_root, 0.4)

    names = [n for n, _t in calls]
    assert names.count("deiconify") >= 2, (
        "a live, never-closed dialog must still receive CustomTkinter's "
        "own initial draw AND _bring_to_front's own deiconify at 200ms, "
        f"but saw: {names}"
    )
    assert "lift" in names and "focus_force" in names and "grab_set" in names, names
    dialog.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_unrelated_synchronous_destroy_dialog_still_behaves_normally(tk_root):
    """One of the 10 dialogs.py-side classes that never overrides destroy()
    (synchronous teardown -- see the E2 call-site inventory in the salvage
    receipt) -- must still open, raise, and close normally. This guard is
    shared code; it must be provably inert for callers that never set
    _closing."""
    dialog = AboutDialog(tk_root)
    calls = _track_reshow_calls(dialog)

    _pump(tk_root, 0.3)  # past _bring_to_front's fixed 200ms mark

    names = [n for n, _t in calls]
    assert "deiconify" in names and "lift" in names and "focus_force" in names, (
        f"AboutDialog (never sets _closing) must still be raised normally, saw: {names}"
    )
    assert "grab_set" in names, "AboutDialog opens modal=True"

    dialog.destroy()  # synchronous default destroy(); must not raise
    assert not dialog.winfo_exists()
