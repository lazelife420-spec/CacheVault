"""Regression coverage for the root CacheVaultApp titlebar-icon teardown leak.

CTk.__init__ (invoked by CacheVaultApp's own super().__init__()) schedules
CustomTkinter's Windows titlebar-icon workaround via
self.after(200, self._windows_set_titlebar_icon) before any of
CacheVaultApp's own __init__ body runs -- before _init_jobs even exists.
Nothing tracked or cancelled that job's id, so a CacheVaultApp destroyed
within 200ms of construction (a real scenario in a test suite building many
app instances back-to-back) could leave it pending against an
already-destroyed interpreter (issue #80).

CacheVaultApp.__init__ now installs a narrowly-scoped instance override of
self.after solely for the duration of super().__init__() (see
_capture_titlebar_icon_job in cache_vault/ui/shell.py), which records only
that one specific callback's id -- every other self.after(...) call made
during super().__init__() passes straight through untouched -- and
destroy() cancels it. This is deliberately not the same mechanism as
FirstUseGuideDialog's blanket self.after tracking (see
test_first_use_guide_titlebar_teardown.py): that dialog tracks its entire
self.after surface for its whole lifetime, which would be far broader than
necessary here and would risk interfering with CacheVaultApp's own existing
per-purpose job tracking (_pump_job, _init_jobs, etc.).
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.shell import CacheVaultApp

#  Deliberately specific rather than the broad "invalid command name" --
#  this repo has a separate, still-open, out-of-scope leak
#  (_check_if_scrollbars_needed, issue #79) that also raises "invalid
#  command name" errors during these same construct/destroy cycles. A
#  broad marker would couple this lane's tests to that unrelated bug;
#  these three substrings are specific to the callbacks this fix (and the
#  already-merged PR #81 lifecycle fixes) actually own.
_DIAGNOSTIC_MARKERS = (
    "_windows_set_titlebar_icon",
    "_pump_main_thread",
    "_revert_withdraw_after_windows_set_titlebar_color",
)


def _pump(widget, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        widget.update()
        time.sleep(0.02)


@pytest.fixture
def app(tk_root, vault):
    app = CacheVaultApp(vault=vault)
    yield app
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        pass


def test_titlebar_icon_job_captured_at_construction(app):
    """1 & 2: CTk.__init__ schedules the callback, and CacheVault tracks it
    under its own attribute by the time construction finishes."""
    job_id = app._titlebar_icon_job
    assert job_id is not None, "the titlebar-icon job must be captured during super().__init__()"
    pending = [str(p) for p in app.tk.call("after", "info")]
    assert str(job_id) in pending, "the captured id must actually be Tcl's own live schedule"


def test_after_override_does_not_leak_past_construction(app):
    """The self.after override is instance-scoped to super().__init__() only
    -- after construction, self.after must be the normal inherited method,
    not the tracking wrapper, so nothing else accidentally goes through it."""
    assert "after" not in app.__dict__, (
        "the instance-level self.after override must be removed once "
        "super().__init__() returns"
    )


def test_normal_titlebar_icon_callback_fires_while_alive(app, capfd):
    """3: normal titlebar-icon behavior executes fine while the root window
    is alive -- the tracking override must not suppress or break it."""
    capfd.readouterr()
    job_id = app._titlebar_icon_job
    assert job_id is not None
    _pump(app, 0.35)  # > the original 200ms delay
    pending = [str(p) for p in app.tk.call("after", "info")]
    assert str(job_id) not in pending, "the job must fire naturally while the window is alive"
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear from the callback's normal execution; captured: {combined!r}"
        )


def test_destroy_before_delay_cancels_titlebar_icon_job(app):
    """4: destroying the app before the 200ms callback fires cancels it."""
    job_id = app._titlebar_icon_job
    assert job_id is not None

    cancelled = []
    real_after_cancel = app.after_cancel

    def traced_cancel(jid):
        cancelled.append(jid)
        return real_after_cancel(jid)

    app.after_cancel = traced_cancel
    app.destroy()

    assert job_id in cancelled, "destroy() must cancel the tracked titlebar-icon job"
    assert app._titlebar_icon_job is None, "the tracked id must be cleared after cancellation"


def test_destroy_before_delay_prevents_execution_against_dead_interpreter(tk_root, vault, capfd):
    """5: the callback must not execute against a destroyed Tcl interpreter.

    app is its own separate CTk() root (its own Tcl interpreter), so once
    destroyed there is nothing left to pump directly -- instead, pump a
    different, still-alive interpreter (tk_root) across the original 200ms
    window and confirm no stray diagnostic surfaces anywhere in the process.
    """
    capfd.readouterr()
    app = CacheVaultApp(vault=vault)
    job_id = app._titlebar_icon_job
    assert job_id is not None
    app.destroy()

    _pump(tk_root, 0.35)  # well past the original 200ms delay

    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after destroying before the delay elapsed; captured: {combined!r}"
        )


def test_repeated_construct_destroy_cycles_leave_no_unresolved_job(tk_root, vault, capfd):
    """6: repeated construct/destroy cycles around the 200ms boundary must
    leave no unresolved titlebar-icon callback and no diagnostics."""
    capfd.readouterr()
    for i in range(30):
        app = CacheVaultApp(vault=vault)
        assert app._titlebar_icon_job is not None
        if i % 3 == 0:
            _pump(app, 0.05)  # destroy well before the 200ms delay
        elif i % 3 == 1:
            _pump(app, 0.22)  # destroy just after the 200ms delay fired
        # i % 3 == 2: destroy immediately, no pumping at all
        app.destroy()
        assert app._titlebar_icon_job is None

    _pump(tk_root, 0.3)  # drain anything that might still be in flight
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared across 30 construct/destroy cycles; captured: {combined!r}"
        )


def test_pump_main_thread_teardown_remains_intact(app):
    """7: the existing _pump_main_thread teardown (issue #81) is untouched
    by this change -- both jobs get cancelled together in one destroy()."""
    assert app._pump_job is not None
    titlebar_job = app._titlebar_icon_job
    pump_job = app._pump_job
    assert titlebar_job is not None

    cancelled = []
    real_after_cancel = app.after_cancel

    def traced_cancel(jid):
        cancelled.append(jid)
        return real_after_cancel(jid)

    app.after_cancel = traced_cancel
    app.destroy()

    assert titlebar_job in cancelled
    assert pump_job in cancelled
    assert app._pump_job is None


def test_first_use_guide_containment_remains_intact(tk_root, vault, capfd):
    """8: CacheVaultApp also schedules _maybe_show_first_use_guide at 150ms
    (see __init__), which can construct a FirstUseGuideDialog. Destroying
    the app around that boundary must not regress its own containment
    (test_first_use_guide_titlebar_teardown.py covers that dialog directly;
    this proves the root-level fix doesn't interfere with it)."""
    capfd.readouterr()
    app = CacheVaultApp(vault=vault)
    _pump(app, 0.18)  # cross the 150ms first-use-guide boundary
    app.destroy()
    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared around the first-use-guide boundary; captured: {combined!r}"
        )


def test_repeated_destroy_is_safe(app):
    app.destroy()
    app.destroy()  # must not raise
