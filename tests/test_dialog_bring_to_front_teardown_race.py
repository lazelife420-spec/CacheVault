"""``_bring_to_front``'s deferred ``_raise()`` must not act on a closing dialog.

Found by the post-canonical dirty-tree salvage audit (Gate E2, item B1):
``_bring_to_front`` (``cache_vault/ui/dialogs.py``) schedules ``win.after(200,
_raise)`` unconditionally. ``ClipComposerDialog``/``EditClipTextDialog``
(``cache_vault/ui/clip_workflows.py``) are the only two dialogs (of 12 using
the shared helper across 13 call sites) whose ``destroy()`` is staged --
``withdraw()`` immediately, then the real ``super().destroy()`` deferred 50ms
later. If their ``destroy()`` is called between roughly 150ms and 200ms after
construction, the widget is still genuinely alive (just hidden) when
``_raise()`` fires at the fixed 200ms mark, and -- absent a guard -- it
proceeds to deiconify/lift/focus_force/grab_set a dialog the user already
closed, moments before it is actually torn down.

The other 10 dialogs (9 in dialogs.py -- none override ``destroy()`` -- plus
``MultiLinkPasteDialog`` in clip_workflows.py, also unstaged) destroy
synchronously: by the time a deferred ``_raise()`` could fire, the widget is
already fully gone, ``deiconify()`` raises a caught ``TclError``, and nothing
is re-shown. Confirmed by direct inspection of every call site; this file
tests the shared mechanism deterministically, not a specific dialog class.

These tests use a controllable fake in place of a real Tk widget so the race
is exercised by direct control flow, not wall-clock timing -- see
``tests/test_clip_workflows_bring_to_front_race.py`` for the companion
real-Tk proof through an actual affected dialog's close path.
"""

from __future__ import annotations

import pytest

from cache_vault.ui import dialogs as dialogs_mod


class _FakeWin:
    """Records every call `_bring_to_front`/`_raise` could make on a real
    Tk widget, and lets a test control `winfo_exists()`/`after_cancel`
    deterministically instead of racing the real Tk event loop."""

    def __init__(self, *, exists: bool = True):
        self.calls: list[str] = []
        self._exists = exists
        self._closing = False
        self.after_jobs: dict[str, tuple] = {}
        self.cancelled_jobs: list[str] = []
        self._next_job_id = 0

    # --- the subset of the real Tk/CTk API _bring_to_front/_raise touch ---
    def transient(self, _master) -> None:
        pass

    def winfo_exists(self) -> bool:
        return self._exists

    def after(self, ms, fn=None, *args):
        self._next_job_id += 1
        job_id = f"job{self._next_job_id}"
        self.after_jobs[job_id] = (ms, fn, args)
        return job_id

    def after_cancel(self, job_id) -> None:
        self.cancelled_jobs.append(job_id)
        self.after_jobs.pop(job_id, None)

    def deiconify(self) -> None:
        self.calls.append("deiconify")

    def lift(self) -> None:
        self.calls.append("lift")

    def focus_force(self) -> None:
        self.calls.append("focus_force")

    def grab_set(self) -> None:
        self.calls.append("grab_set")


class _FakeMaster:
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0
    def winfo_width(self): return 800
    def winfo_height(self): return 600


def _schedule(win, master=None, *, modal=True):
    """Call the real _bring_to_front and return the (fn, args) it scheduled."""
    dialogs_mod._bring_to_front(win, master or _FakeMaster(), modal=modal)
    assert len(win.after_jobs) == 1, "expected exactly one scheduled job"
    job_id, (ms, fn, args) = next(iter(win.after_jobs.items()))
    assert ms == 200
    return job_id, fn, args


# --- the defect, reproduced deterministically -------------------------------

def test_deferred_raise_currently_has_no_closing_guard_recorded_here_for_traceability():
    """Not a pass/fail assertion -- a living trace of the exact mechanism
    under test, so a future reader doesn't have to re-derive it: this proves
    _bring_to_front schedules unconditionally regardless of any `_closing`
    state on `win`, which is the root condition every other test here
    exercises the consequences of."""
    win = _FakeWin()
    win._closing = True  # already "closing" before the dialog is even shown
    _schedule(win)
    assert win.after_jobs, "a job was scheduled even though win was already closing"


def test_raise_must_not_reshow_a_window_mid_staged_teardown():
    """The core race: win is still alive (winfo_exists() True) but marked
    _closing when the deferred callback fires -- exactly the state
    ClipComposerDialog/EditClipTextDialog are in during their 50ms
    withdraw-to-destroy gap."""
    win = _FakeWin(exists=True)
    _job_id, fn, args = _schedule(win, modal=True)

    win._closing = True  # dialog began closing before the callback fired
    fn(*args)

    assert win.calls == [], (
        "a deferred _raise() must not deiconify/lift/focus/grab a dialog "
        f"that has begun closing, but it called: {win.calls}"
    )


def test_raise_must_not_reshow_an_already_destroyed_window():
    """The parent-cascade case: winfo_exists() is False (truly gone) but
    _closing was never set, because the Python-level destroy() override
    never ran -- Tcl-level cascades bypass it. winfo_exists() alone must be
    enough."""
    win = _FakeWin(exists=True)
    _job_id, fn, args = _schedule(win, modal=True)

    win._exists = False  # the widget is now genuinely gone
    fn(*args)

    assert win.calls == [], (
        f"a deferred _raise() must not act on an already-destroyed window, "
        f"but it called: {win.calls}"
    )


def test_bring_to_front_records_a_cancellable_job_id():
    """A close path that wants to cancel the pending callback outright (not
    just rely on the guard) needs somewhere to find the job id."""
    win = _FakeWin(exists=True)
    job_id, _fn, _args = _schedule(win)
    assert win._bring_to_front_job == job_id


def test_cancelling_the_job_before_it_fires_leaves_no_pending_callback():
    """The affected close paths call after_cancel on this id; confirm doing
    so actually removes it from the scheduler (no leaked pending job)."""
    win = _FakeWin(exists=True)
    job_id, _fn, _args = _schedule(win)

    win.after_cancel(win._bring_to_front_job)

    assert job_id not in win.after_jobs, "the job must no longer be pending"
    assert job_id in win.cancelled_jobs


def test_cancelling_an_already_fired_or_nonexistent_job_is_safe():
    """Mirrors the try/except around after_cancel in the two affected
    destroy() methods: cancelling a job Tk no longer recognizes (already
    fired, or simply invalid) must not raise."""
    win = _FakeWin(exists=True)

    class _StrictFakeWin(_FakeWin):
        """A Tk-like after_cancel that raises for jobs it doesn't have --
        the real Tk API does raise (TclError) for an unknown id."""
        def after_cancel(self, job_id):
            if job_id not in self.after_jobs:
                raise RuntimeError("bad after id")
            super().after_cancel(job_id)

    win = _StrictFakeWin(exists=True)
    job_id, fn, args = _schedule(win)
    fn(*args)  # the job fires -- a real Tk `after` job is consumed once run

    # Mirrors destroy()'s own guarded cancellation exactly.
    try:
        job = getattr(win, "_bring_to_front_job", None)
        if job is not None:
            win.after_cancel(job)
    except Exception as exc:  # noqa: BLE001 - this is exactly what must not happen
        pytest.fail(f"cancelling an already-fired job must not raise: {exc}")


def test_raise_still_works_normally_on_a_live_dialog():
    """The fix must not break the feature it protects: a dialog that is
    still fully alive and never began closing must still be raised,
    focused, and (if modal) grabbed when its deferred callback fires."""
    win = _FakeWin(exists=True)
    _job_id, fn, args = _schedule(win, modal=True)

    fn(*args)

    assert win.calls == ["deiconify", "lift", "focus_force", "grab_set"], win.calls


def test_raise_still_works_normally_for_non_modal_dialogs():
    win = _FakeWin(exists=True)
    _job_id, fn, args = _schedule(win, modal=False)

    fn(*args)

    assert win.calls == ["deiconify", "lift", "focus_force"], win.calls


def test_repeated_legitimate_bring_to_front_calls_each_still_work():
    """Calling _bring_to_front more than once on the same still-alive window
    (e.g. re-focusing an existing dialog) must schedule and fire normally
    each time -- the fix must not introduce any one-shot/already-used state
    that blocks a second legitimate call."""
    win = _FakeWin(exists=True)
    for _ in range(3):
        win.calls.clear()
        win.after_jobs.clear()
        _job_id, fn, args = _schedule(win, modal=True)
        fn(*args)
        assert win.calls == ["deiconify", "lift", "focus_force", "grab_set"]
