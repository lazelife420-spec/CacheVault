"""Regression coverage for the FirstUseGuideDialog titlebar-callback teardown leak.

CacheVaultApp.__init__ unconditionally schedules self.after(150,
_maybe_show_first_use_guide), which silently constructs a
FirstUseGuideDialog(ctk.CTkToplevel) whenever
vault.settings.first_use_guide_dismissed is False (the default for fresh
settings) -- i.e. on essentially every test that builds a real app and waits
more than 150ms. That dialog's __init__ calls self.resizable(False, True),
which triggers CustomTkinter's own internal delayed chain (resizable() ->
after(10ms) -> _windows_set_titlebar_color() -> after(5ms) ->
_revert_withdraw_after_windows_set_titlebar_color(), plus a focus-restore
after(1ms)), and separately calls _bring_to_front(self), which schedules its
own after(200ms) topmost-reset lambda. None of these ids were tracked or
cancelled on teardown (unlike cache_vault.ui.clip_workflows.EditClipTextDialog,
which already contains an equivalent CustomTkinter race for a different
dialog). If the dialog is destroyed (e.g. via the owning CacheVaultApp's own
destroy()) while any of those jobs are still pending, Tk raises
"invalid command name" once each fires against the now-destroyed widget --
reproduced twice, consecutively, in full-suite runs against commit 274246ed
(see issue #78).

Since CustomTkinter doesn't expose any of these ids, FirstUseGuideDialog
tracks its own self.after(...) surface (which Python resolves via normal
instance-attribute lookup, so this transparently captures CustomTkinter's own
internal self.after(...) calls too, not just cache_vault's) and cancels
whatever's still pending at destroy() -- deterministic cancellation of the
actual jobs, not a magic-number defer-and-hope delay.
"""

from __future__ import annotations

import time

import customtkinter as ctk
import pytest

from cache_vault.ui.first_use_guide import FirstUseGuideDialog
from cache_vault.ui.shell import CacheVaultApp


def _pump(widget, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        widget.update()
        time.sleep(0.02)


_DIAGNOSTIC_MARKERS = (
    "invalid command name",
    "_revert_withdraw_after_windows_set_titlebar_color",
)


def test_descendant_destruction_does_not_cancel_live_dialog_jobs(tk_root, capfd):
    """Review concern: <Destroy> bound on a Toplevel fires for every
    descendant too, as each is torn down in the same cascade -- confirmed
    empirically, a full construct-then-destroy cycle produces 67 <Destroy>
    events for this dialog's widget subtree, only 1 of which is the dialog's
    own. Without filtering to that one event, destroying so much as a single
    descendant button while the dialog is still fully alive and open would
    silently cancel every tracked pending job -- legitimate in-flight
    titlebar/focus/icon/topmost-reset work that has nothing to do with
    teardown. This proves the full required sequence: a descendant destroy
    while alive does NOT cancel live jobs or disable normal behavior, while
    the dialog's own destruction (via a genuine parent-cascade, not a direct
    .destroy() call) still cancels everything and nothing fires against the
    destroyed interpreter afterward.
    """
    capfd.readouterr()

    # An intermediate parent (not the session-scoped tk_root) so destroying
    # it to trigger a genuine Tcl-level cascade -- the same mechanism
    # CacheVaultApp's plain super().destroy() uses, which never calls a
    # Python-level destroy() on its children at all -- doesn't tear down the
    # shared session root out from under every other test.
    parent = ctk.CTkToplevel(tk_root)
    parent.withdraw()

    # 1. Create the dialog.
    dialog = FirstUseGuideDialog(parent, from_settings=False, on_action=lambda a: None)

    # 2. Schedule a tracked callback that records execution -- distinct from
    # CustomTkinter's own internal jobs, so we can prove specifically that a
    # descendant's destruction doesn't cancel this window's unrelated
    # pending work.
    recorded = []
    canary_id = dialog.after(150, lambda: recorded.append("canary-fired"))
    assert canary_id in dialog._pending_after_ids

    # 3. Destroy one descendant widget while the dialog remains alive.
    footer = dialog.winfo_children()[0]
    button = footer.winfo_children()[0]
    button.destroy()

    # 4. Pump the event loop -- not yet long enough for the 150ms canary.
    _pump(tk_root, 0.05)

    # 5. Prove: the dialog still exists; the tracked callback was not
    # prematurely cancelled; normal live-window behavior remains
    # operational (the canary firing on schedule, and CustomTkinter's own
    # titlebar/topmost chain completing normally, not suppressed).
    assert dialog.winfo_exists(), "a descendant destroy must not destroy the dialog itself"
    assert canary_id in dialog._pending_after_ids, (
        "a descendant's own <Destroy> must not cancel this window's "
        "still-pending, unrelated tracked jobs"
    )
    _pump(tk_root, 0.15)
    assert recorded == ["canary-fired"], (
        "a callback scheduled on the live dialog must still fire normally "
        "after a descendant (not the dialog itself) was destroyed"
    )
    _pump(tk_root, 0.3)  # let CustomTkinter's ~15ms chain + the 200ms
    # topmost-reset complete naturally, proving normal titlebar/focus
    # restoration executes fine while the dialog is alive
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear from normal operation after a "
            f"descendant destroy; captured: {combined!r}"
        )
    assert not dialog.attributes("-topmost"), (
        "normal topmost-reset must complete while the dialog stays alive, "
        "unaffected by the earlier descendant destroy"
    )

    # 6. Destroy the dialog through the parent-cascade path. Schedule one
    # more, long-delay canary first so there is something genuinely still
    # pending at the moment of cascade -- otherwise "everything pending got
    # cancelled" would be vacuously true if nothing was left to cancel.
    long_canary_id = dialog.after(5000, lambda: None)
    assert long_canary_id in dialog._pending_after_ids
    capfd.readouterr()
    parent.destroy()

    # 7. Prove all remaining tracked callbacks are cancelled.
    assert not dialog._pending_after_ids, (
        "the dialog's own destruction via parent-cascade must cancel every "
        "remaining tracked job, including the long-delay canary"
    )

    # 8. Prove no callback executes against the destroyed interpreter.
    _pump(tk_root, 0.4)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after parent-cascade destroy; "
            f"captured: {combined!r}"
        )


def test_quick_destroy_leaves_no_invalid_command_diagnostics(tk_root, capfd):
    """Core regression: destroying the dialog almost immediately after
    construction -- well inside CustomTkinter's own ~15ms internal chain and
    _bring_to_front's 200ms topmost-reset window -- must not leave any
    delayed callback to fire against a destroyed widget later."""
    capfd.readouterr()  # discard setup noise

    dialog = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
    # Let CustomTkinter's internal chain get partway underway before tearing
    # down -- destroying at t=0 (before any of it has started) lets Tk's own
    # winfo_exists()-style guards skip cleanly in some cases; the real defect
    # shows up once the chain is *in flight* (matching the ~150-250ms window
    # in the real CacheVaultApp sequence that actually reproduced this bug).
    _pump(tk_root, 0.03)
    dialog.destroy()

    # Give every pending job (1ms/5ms/10ms/200ms) a chance to fire if it
    # wasn't actually cancelled -- this is the same window that surfaced the
    # warnings in the real full-suite failures.
    _pump(tk_root, 0.4)

    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after a quick create/destroy cycle; "
            f"captured: {combined!r}"
        )


def test_callback_ids_are_cancelled_not_left_dangling(tk_root):
    """Every self.after(...) job this window scheduled -- CustomTkinter's own
    included -- must be tracked and cleared by destroy(), not merely
    forgotten."""
    dialog = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
    assert dialog._pending_after_ids, (
        "Construction schedules at least resizable()'s internal after() call "
        "and _bring_to_front's topmost-reset -- tracking must have captured "
        "something before we can prove destroy() clears it"
    )
    dialog.destroy()
    assert not dialog._pending_after_ids, (
        "destroy() must cancel and clear every tracked pending job id"
    )


def test_repeated_open_close_cycles_leave_no_unresolved_callback(tk_root, capfd):
    """Many quick open/close cycles must not accumulate leaked callbacks."""
    capfd.readouterr()

    for _ in range(15):
        dialog = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
        _pump(tk_root, 0.03)  # let the chain get partway underway, see above
        dialog.destroy()

    _pump(tk_root, 0.5)

    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after 15 repeated open/close cycles; "
            f"captured: {combined!r}"
        )


def test_all_teardown_paths_are_contained(tk_root, capfd):
    """The window-manager close (X / WM_DELETE_WINDOW), a footer button
    action, and a direct programmatic destroy() call must all route through
    the same cancellation -- not just whichever path happens to be tested
    elsewhere."""
    capfd.readouterr()

    # 1. WM_DELETE_WINDOW path.
    d1 = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
    _pump(tk_root, 0.03)
    d1._close_only()
    assert not d1._pending_after_ids

    # 2. Footer button action path.
    actions = []
    d2 = FirstUseGuideDialog(tk_root, from_settings=False, on_action=actions.append)
    _pump(tk_root, 0.03)
    d2._done("dismiss")
    assert actions == ["dismiss"]
    assert not d2._pending_after_ids

    # 3. Direct programmatic destroy() (e.g. from an owning app's own destroy()).
    d3 = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
    _pump(tk_root, 0.03)
    d3.destroy()
    assert not d3._pending_after_ids

    _pump(tk_root, 0.4)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after any of the three teardown "
            f"paths; captured: {combined!r}"
        )


def test_pump_main_thread_cancellation_remains_intact_with_guide_open(vault, tk_root, capfd):
    """Integration guard: the _pump_main_thread fix (274246ed) and this
    titlebar containment must cooperate correctly when a real CacheVaultApp
    auto-opens its first-use guide and is then torn down -- the exact
    real-world sequence that produced the original full-suite failures."""
    capfd.readouterr()

    vault.settings.first_use_guide_dismissed = False
    app = CacheVaultApp(vault=vault)
    try:
        _pump(app, 0.25)  # >150ms so _maybe_show_first_use_guide has fired
        guides = [w for w in app.winfo_children() if isinstance(w, FirstUseGuideDialog)]
        assert guides, "Test setup requires the guide to have actually opened"
    finally:
        app.destroy()

    assert app._pump_job is None, "Pump job tracking must still be cleared (274246ed's fix)"

    _pump(tk_root, 0.4)
    out, err = capfd.readouterr()
    combined = out + err
    assert "_pump_main_thread" not in combined
    assert "_revert_withdraw_after_windows_set_titlebar_color" not in combined, (
        f"the titlebar-revert callback must not appear after a real app "
        f"with an open guide is destroyed; captured: {combined!r}"
    )
    # Deliberately NOT asserting the bare "invalid command name" marker here
    # (unlike the isolated tests above): a full CacheVaultApp has its own
    # pre-existing, unrelated leak in CTkTextbox._check_if_scrollbars_needed
    # (a self-rescheduling 200ms after() job on the main vault screen's clip
    # textboxes, same *class* of bug -- uncancelled, rescheduling id -- but a
    # different widget entirely, discovered while writing this test). Failing
    # this test on that would conflate a pre-existing, separately-classified
    # defect with the titlebar fix this test exists to prove; see the PR/issue
    # notes for that separate finding.


def test_titlebar_appearance_completes_normally_while_window_stays_alive(tk_root, capfd):
    """Containment must only cancel jobs that are still pending at destroy()
    -- it must not suppress or interfere with the normal titlebar-color /
    topmost transition while the window is simply left open."""
    capfd.readouterr()

    dialog = FirstUseGuideDialog(tk_root, from_settings=False, on_action=lambda a: None)
    _pump(tk_root, 0.4)  # let CustomTkinter's full ~15ms chain and the
    # 200ms _bring_to_front topmost-reset complete naturally

    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"Normal operation (no early destroy) must not itself produce "
            f"{marker!r}; captured: {combined!r}"
        )
    assert dialog.winfo_exists(), "Window must still be alive and normal"
    assert not dialog.attributes("-topmost"), (
        "_bring_to_front's own topmost-reset must have completed normally"
    )

    dialog.destroy()
