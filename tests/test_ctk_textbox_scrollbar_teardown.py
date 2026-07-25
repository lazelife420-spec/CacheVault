"""Regression coverage for the CTkTextbox scrollbar-check teardown leak.

CTkTextbox.__init__ schedules self.after(50, self._check_if_scrollbars_needed,
None, True), and _check_if_scrollbars_needed reschedules itself every 200ms
(self._scrollbar_update_time) via self.after(200, lambda: ...) for as long as
the widget is alive (see ctk_textbox.py in the installed customtkinter
package). Neither call's returned id is ever stored anywhere, and
CTkTextbox.destroy() does nothing but forward to the base class -- so
whichever poll is currently pending can never be cancelled. A textbox
destroyed -- directly, or via a parent's teardown cascade at the Tcl level,
which never calls a Python-level destroy() on children at all -- while that
poll is still pending leaves Tk to report "invalid command name" once it
fires against the now-destroyed widget (issue #79). Reproduced directly (see
scratch trace, not committed here) against the unfixed baseline: 30
construct/destroy cycles of a bare ctk.CTkTextbox under a fresh root produced
dozens of "invalid command name ..._check_if_scrollbars_needed" and
"...<lambda>" diagnostics.

CacheVaultTextbox (cache_vault/ui/textbox.py) is a CTkTextbox subclass that
takes over scheduling the recurring poll entirely -- overriding
_check_if_scrollbars_needed so the base class's own self.after(...) call
(whose id is discarded) never runs, and capturing the very first self.after(50,
...) call CTkTextbox.__init__ makes the same way CacheVaultApp captures CTk's
root titlebar-icon job (see cache_vault/ui/shell.py
_capture_titlebar_icon_job / issue #80). destroy() cancels whichever id is
currently tracked.

Sixteen CacheVault call sites across mobile_dialogs.py, macro_dialogs.py,
clip_workflows.py, preview.py, founder.py, dialogs.py, settings_hub.py, and
vault_screens.py were switched from ctk.CTkTextbox to CacheVaultTextbox so
this containment applies uniformly rather than being patched ad hoc per call
site.
"""

from __future__ import annotations

import time

import pytest

from cache_vault.ui.textbox import CacheVaultTextbox

_DIAGNOSTIC_MARKERS = (
    "_check_if_scrollbars_needed",
    "_reschedule_scrollbar_check",
    # Deliberately not the base "invalid command name" -- other CTk
    # internals (check_dpi_scaling, plain "update", etc; see the issue #79
    # audit trace) also raise it and are out of scope for this lane.
)

_OWNED_LIFECYCLE_MARKERS = (
    "_pump_main_thread",
    "_revert_withdraw_after_windows_set_titlebar_color",
    "_windows_set_titlebar_icon",
)


def _pump(widget, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        widget.update()
        time.sleep(0.01)


@pytest.fixture
def box(tk_root):
    box = CacheVaultTextbox(tk_root)
    yield box
    try:
        box.destroy()
    except Exception:  # noqa: BLE001
        pass


def test_initial_scrollbar_check_job_captured_at_construction(box):
    """1 & 2: CTkTextbox.__init__ schedules the first check, and it's
    tracked under CacheVaultTextbox's own attribute immediately."""
    job_id = box._scrollbar_check_job
    assert job_id is not None
    pending = [str(p) for p in box.tk.call("after", "info")]
    assert str(job_id) in pending


def test_tracked_id_changes_on_reschedule(tk_root, box):
    """3: the stored id changes as the poll reschedules itself."""
    first_id = box._scrollbar_check_job
    _pump(tk_root, 0.08)  # past the initial 50ms -> reschedules to a 200ms job
    second_id = box._scrollbar_check_job
    assert second_id is not None
    assert second_id != first_id

    _pump(tk_root, 0.22)  # past the 200ms reschedule -> reschedules again
    third_id = box._scrollbar_check_job
    assert third_id is not None
    assert third_id not in (first_id, second_id)


def test_on_demand_check_does_not_clobber_pending_recurring_job(tk_root, box):
    """Regression for a real design bug caught during development: an
    on-demand call (mirroring edit_redo()/edit_undo(), which pass no
    continue_loop) must not discard the tracked id of an already-pending
    recurring job -- only the recurring job's own firing may replace it."""
    _pump(tk_root, 0.08)
    pending_job = box._scrollbar_check_job
    assert pending_job is not None

    box._check_if_scrollbars_needed()  # on-demand call, continue_loop=False

    assert box._scrollbar_check_job == pending_job, (
        "an on-demand check must not clear or replace the still-pending "
        "recurring job's tracked id"
    )
    pending = [str(p) for p in box.tk.call("after", "info")]
    assert str(pending_job) in pending, "the recurring job itself must remain live"


def test_normal_scrollbar_behavior_executes_while_alive(tk_root, box, capfd):
    """4: normal scrollbar checking (show/hide) keeps running normally while
    the widget is alive -- taking over scheduling must not break it."""
    capfd.readouterr()
    box.insert("1.0", "\n".join(str(i) for i in range(200)))  # force a y-scrollbar
    _pump(tk_root, 0.35)  # let at least one full check cycle run
    # tk_root is withdrawn (see the shared fixture), so winfo_ismapped() on a
    # descendant is unreliable regardless of the fix -- check the internal
    # flag CTkTextbox's own show/hide logic actually drives instead.
    assert box._hide_y_scrollbar is False, "scrollbar must be shown when content overflows"
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS + _OWNED_LIFECYCLE_MARKERS:
        assert marker not in combined


def test_direct_destroy_cancels_active_job(tk_root, box):
    """5: direct destruction cancels whichever job is currently pending."""
    _pump(tk_root, 0.08)
    job_id = box._scrollbar_check_job
    assert job_id is not None

    cancelled = []
    real_cancel = box.after_cancel

    def traced_cancel(jid):
        cancelled.append(jid)
        return real_cancel(jid)

    box.after_cancel = traced_cancel
    box.destroy()

    assert job_id in cancelled
    assert box._scrollbar_check_job is None


def test_parent_cascade_destroy_cancels_active_job(tk_root, capfd):
    """6: a parent-cascade teardown (Tcl-level, no Python destroy() call on
    the textbox itself) must also leave no live job pending."""
    import customtkinter as ctk

    capfd.readouterr()
    parent = ctk.CTkToplevel(tk_root)
    parent.withdraw()
    box = CacheVaultTextbox(parent)
    _pump(tk_root, 0.08)
    job_id = box._scrollbar_check_job
    assert job_id is not None

    parent.destroy()  # cascades at the Tcl level; box.destroy() is never called directly

    _pump(tk_root, 0.35)  # past the original window, in case anything leaked
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} leaked after parent-cascade destruction; captured: {combined!r}"
        )


def test_no_reschedule_once_destroyed(tk_root):
    """7: the callback cannot reschedule after teardown begins -- destroying
    mid-cycle must not leave a fresh job appear afterward."""
    import customtkinter as ctk

    box = CacheVaultTextbox(tk_root)
    _pump(tk_root, 0.08)
    box.destroy()
    assert box._scrollbar_check_job is None

    # If a reschedule slipped through, some *new* job would be live on
    # tk_root shortly after; there's no way to inspect a destroyed widget's
    # own state, so this is a structural assertion on the tracked attribute
    # plus the diagnostic-free stress test below, which is the real proof.


def test_repeated_construct_destroy_cycles_leave_no_unresolved_job(tk_root, capfd):
    """8 & 9: repeated construct/destroy cycles around the 50ms and 200ms
    boundaries, direct and parent-cascade, must leave zero diagnostics."""
    import customtkinter as ctk

    capfd.readouterr()
    for i in range(30):
        direct = (i % 2 == 0)
        if direct:
            owner = tk_root
        else:
            owner = ctk.CTkToplevel(tk_root)
            owner.withdraw()
        box = CacheVaultTextbox(owner)
        assert box._scrollbar_check_job is not None

        phase = i % 4
        if phase == 0:
            pass  # destroy immediately, before the 50ms job fires
        elif phase == 1:
            _pump(tk_root, 0.03)  # destroy mid-way through the 50ms window
        elif phase == 2:
            _pump(tk_root, 0.08)  # destroy just after one reschedule
        else:
            _pump(tk_root, 0.26)  # destroy just after a second reschedule

        if direct:
            box.destroy()
            assert box._scrollbar_check_job is None
        else:
            owner.destroy()  # parent-cascade; box.destroy() never called directly

    _pump(tk_root, 0.3)  # drain anything still in flight
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared across 30 construct/destroy cycles; captured: {combined!r}"
        )


def test_existing_lifecycle_protections_remain_intact(tk_root, capfd):
    """10: the already-merged root/pump/first-use-dialog protections are
    unaffected by this change."""
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.settings import Settings
    from cache_vault.ui.shell import CacheVaultApp

    capfd.readouterr()
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    app = CacheVaultApp(vault=vault)
    assert app._titlebar_icon_job is not None
    assert app._pump_job is not None
    _pump(app, 0.05)
    app.destroy()
    vault.close()

    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _OWNED_LIFECYCLE_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared; existing lifecycle protection regressed. captured: {combined!r}"
        )
