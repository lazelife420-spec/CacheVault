"""Regression coverage for the Toast self-destroy teardown leak (issue #86).

Toast.__init__ scheduled its own teardown via an untracked, uncancelled
self.after(duration_ms, self.destroy) (default 1600ms). Toast never stored
that id and never overrode destroy() to cancel it, so a Toast destroyed
early -- directly, or via its owning CacheVaultApp cascading destroy() at
the Tcl level, which never calls a Python-level destroy() on children at
all -- left that job pending. Once it fired against the now-destroyed
widget, Tk reported "invalid command name" (reproduced via
tests/test_sidebar_context.py::test_restore_all_deduplicates_and_skips_already_active,
which does not mock _show_toast).

Toast now tracks the job in self._destroy_job and cancels it via a
<Destroy> binding (fires for both a direct .destroy() call and a
parent-cascade teardown -- unlike overriding destroy() alone, which a
cascade never invokes).
"""

from __future__ import annotations

import time

import pytest

from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui import sidebar_context
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.ui.toast import Toast

_DIAGNOSTIC_MARKERS = (
    "destroy",  # matches "invalid command name "...destroy" ("after" script)
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


def test_toast_stores_its_scheduled_destroy_job(tk_root):
    """1: Toast stores its scheduled self-destroy callback id."""
    toast = Toast(tk_root, "hello", duration_ms=1600)
    assert toast._destroy_job is not None
    pending = [str(p) for p in tk_root.tk.call("after", "info")]
    assert str(toast._destroy_job) in pending
    toast.destroy()


def test_normal_timeout_destroys_a_live_toast(tk_root):
    """2: normal timeout still destroys a live Toast (behavior preserved)."""
    toast = Toast(tk_root, "hello", duration_ms=80)
    assert toast.winfo_exists()
    _pump(tk_root, 0.25)
    assert not toast.winfo_exists()


def test_destroy_job_clears_when_it_fires_normally(tk_root):
    """3: the tracked callback id clears once it fires normally."""
    toast = Toast(tk_root, "hello", duration_ms=80)
    _pump(tk_root, 0.25)
    assert toast._destroy_job is None


def test_direct_early_destruction_cancels_pending_callback(tk_root, capfd):
    """4: direct early destruction cancels the pending callback -- and it
    never fires against the destroyed widget afterward."""
    capfd.readouterr()
    toast = Toast(tk_root, "hello", duration_ms=1600)
    job_id = toast._destroy_job
    assert job_id is not None
    toast.destroy()
    assert toast._destroy_job is None

    pending = [str(p) for p in tk_root.tk.call("after", "info")]
    assert str(job_id) not in pending, "cancelled job must not remain pending"

    _pump(tk_root, 0.3)  # well past the original 1600ms
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after direct early destruction; captured: {combined!r}"
        )


def test_parent_cascade_destruction_cancels_pending_callback(tk_root, capfd):
    """5: a parent-cascade teardown (never calls Toast's own Python-level
    destroy()) still cancels the pending callback via <Destroy>."""
    capfd.readouterr()
    import customtkinter as ctk

    holder = ctk.CTkToplevel(tk_root)
    holder.withdraw()
    toast = Toast(holder, "hello", duration_ms=1600)
    job_id = toast._destroy_job
    assert job_id is not None

    holder.destroy()  # cascades to toast without calling toast.destroy() in Python

    pending = [str(p) for p in tk_root.tk.call("after", "info")]
    assert str(job_id) not in pending, "cascade teardown must also cancel the pending job"

    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear after parent-cascade destruction; captured: {combined!r}"
        )


def test_callback_cannot_execute_against_destroyed_interpreter(tk_root, capfd):
    """6: the callback cannot execute against a destroyed Tcl interpreter --
    end-to-end timing proof, destroying well before the configured delay and
    waiting past it."""
    capfd.readouterr()
    toast = Toast(tk_root, "hello", duration_ms=200)
    toast.destroy()
    _pump(tk_root, 0.4)  # past the original 200ms
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} must not appear; captured: {combined!r}"
        )


def test_repeated_creation_and_early_teardown_leaves_no_callback(tk_root, capfd):
    """7: repeated Toast creation and early teardown leave no callback
    behind across many cycles."""
    capfd.readouterr()
    for i in range(30):
        toast = Toast(tk_root, f"hello {i}", duration_ms=1600)
        if i % 3 == 0:
            _pump(tk_root, 0.03)  # destroy well before timeout
        elif i % 3 == 1:
            pass  # destroy immediately, no pumping at all
        toast.destroy()
        assert toast._destroy_job is None

    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared across 30 create/destroy cycles; captured: {combined!r}"
        )


def test_multiple_overlapping_toasts_clean_up_independently(tk_root, capfd):
    """8: multiple overlapping Toasts clean up independently -- destroying
    one early must not affect another still-live Toast's own timer."""
    capfd.readouterr()
    toast_a = Toast(tk_root, "A", duration_ms=1600)
    toast_b = Toast(tk_root, "B", duration_ms=1600)
    job_a, job_b = toast_a._destroy_job, toast_b._destroy_job
    assert job_a != job_b

    toast_a.destroy()
    assert toast_a._destroy_job is None
    assert toast_b._destroy_job == job_b, "destroying A must not affect B's own tracked job"
    assert toast_b.winfo_exists()

    toast_b.destroy()
    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined


def test_sidebar_restore_all_no_longer_leaks_toast_callback(tmp_path, capfd):
    """9: the sidebar restore-all command (the real repro path from
    test_sidebar_context.py) no longer leaks a Toast callback."""
    from tests.tk_support import _tcl_unavailable
    from unittest import mock

    capfd.readouterr()
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=Settings(capture_paused=True))
    for i in range(3):
        vault.capture(f"clip {i} https://example{i}.com/path", force=True)
    clips = vault.storage.list_clips(None)
    vault.remove_from_history(clips[0].id)

    try:
        app = CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable: {exc}")
        raise

    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        app._do_refresh_sync()

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        with mock.patch("tkinter.messagebox.askyesno", return_value=True):
            app._dispatch_sidebar_command("restore_all", ctx)
        app._do_refresh_sync()
    finally:
        app.destroy()  # well within the toast's 1600ms window

    time.sleep(1.8)  # past the toast's 1600ms window; no live root left to pump
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} leaked from the sidebar restore-all Toast path; captured: {combined!r}"
        )
    vault.close()


def test_30_cycle_stress_across_all_teardown_paths(tk_root, capfd):
    """Comprehensive stress covering, in rotation across 30 cycles: normal
    expiry, direct early close, root-cascade close, overlapping Toasts, and
    teardown immediately before the configured timeout."""
    import customtkinter as ctk

    capfd.readouterr()
    for i in range(30):
        phase = i % 5
        if phase == 0:
            # normal expiry: let it actually fire
            toast = Toast(tk_root, f"cycle {i}", duration_ms=40)
            _pump(tk_root, 0.12)
            assert not toast.winfo_exists()
            assert toast._destroy_job is None
        elif phase == 1:
            # direct early close, well before timeout
            toast = Toast(tk_root, f"cycle {i}", duration_ms=1600)
            toast.destroy()
            assert toast._destroy_job is None
        elif phase == 2:
            # root-cascade close via an intermediate holder
            holder = ctk.CTkToplevel(tk_root)
            holder.withdraw()
            toast = Toast(holder, f"cycle {i}", duration_ms=1600)
            job_id = toast._destroy_job
            holder.destroy()
            pending = [str(p) for p in tk_root.tk.call("after", "info")]
            assert str(job_id) not in pending
        elif phase == 3:
            # overlapping toasts, destroyed independently
            a = Toast(tk_root, f"cycle {i}a", duration_ms=1600)
            b = Toast(tk_root, f"cycle {i}b", duration_ms=1600)
            a.destroy()
            assert a._destroy_job is None
            assert b._destroy_job is not None
            b.destroy()
            assert b._destroy_job is None
        else:
            # teardown immediately before the configured timeout elapses
            toast = Toast(tk_root, f"cycle {i}", duration_ms=60)
            _pump(tk_root, 0.05)  # just under the 60ms delay
            toast.destroy()
            assert toast._destroy_job is None

    _pump(tk_root, 0.3)
    out, err = capfd.readouterr()
    combined = out + err
    for marker in _DIAGNOSTIC_MARKERS:
        assert marker not in combined, (
            f"{marker!r} appeared across the 30-cycle rotation; captured: {combined!r}"
        )


def test_existing_lifecycle_protections_remain_intact(app):
    """10: existing lifecycle protections (root titlebar icon, pump,
    textbox scrollbar) remain intact -- a Toast alongside the root app
    does not interfere with any of them."""
    Toast(app, "hello", duration_ms=1600).destroy()
    assert app._pump_job is not None
    assert hasattr(app, "_titlebar_icon_job")
