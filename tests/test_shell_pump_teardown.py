"""Regression coverage for the _pump_main_thread teardown leak.

_pump_main_thread reschedules itself every 50ms via self.after(...), so
unlike the one-shot jobs in _init_jobs, its live callback id changes on
every firing. destroy() must track and cancel whichever id is CURRENTLY
pending, not just the one originally scheduled at __init__ time -- and the
callback itself must stop doing any work, including rescheduling, once
shutdown has begun. These tests exercise that lifecycle behavior directly
rather than just inspecting attribute/method names.
"""
import time

import pytest

from cache_vault.ui.shell import CacheVaultApp


@pytest.fixture
def app(tk_root, vault):
    app = CacheVaultApp(vault=vault)
    yield app
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        pass


def _pump_until(app, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.update()
        time.sleep(0.02)


def test_pump_job_id_changes_on_reschedule(app):
    first_id = app._pump_job
    assert first_id is not None, "Pump job should be scheduled at construction"

    _pump_until(app, 0.15)  # >2x the 50ms interval
    second_id = app._pump_job
    assert second_id is not None
    assert second_id != first_id, (
        "The tracked pump job id must change as _pump_main_thread reschedules "
        "itself -- a static id would mean only the original firing is tracked"
    )

    _pump_until(app, 0.15)
    third_id = app._pump_job
    assert third_id not in (first_id, second_id), (
        "Each reschedule must produce a new tracked id, not just the first two"
    )


def test_pump_job_tracks_only_current_live_callback(app):
    _pump_until(app, 0.15)
    stale_id = app._pump_job
    _pump_until(app, 0.15)
    current_id = app._pump_job
    assert current_id != stale_id

    pending = app.tk.call("after", "info")
    assert str(current_id) in [str(p) for p in pending], (
        "The current tracked id must actually be live in Tcl's own schedule"
    )
    assert str(stale_id) not in [str(p) for p in pending], (
        "A superseded id must not still be pending -- Tcl already fired and "
        "consumed it when it rescheduled into the current id"
    )


def test_destroy_cancels_latest_pump_job_not_only_first(app):
    original_first_id = app._pump_job
    _pump_until(app, 0.15)
    latest_id_before_destroy = app._pump_job
    assert latest_id_before_destroy != original_first_id, (
        "Test setup requires at least one reschedule so 'latest' differs from 'first'"
    )

    cancelled = []
    real_after_cancel = app.after_cancel

    def traced_cancel(job_id):
        cancelled.append(job_id)
        return real_after_cancel(job_id)

    app.after_cancel = traced_cancel
    app.destroy()

    assert latest_id_before_destroy in cancelled, (
        "destroy() must cancel the CURRENT live pump job id, not merely "
        "whatever id was recorded at __init__ time"
    )
    assert app._pump_job is None, "The tracked id must be cleared after cancellation"


def test_pump_main_thread_does_not_execute_or_reschedule_after_shutdown_begins(app):
    sentinel_ran = []
    app._main_thread_calls.put(lambda: sentinel_ran.append(True))

    after_calls = []
    real_after = app.after
    app.after = lambda *a, **kw: (after_calls.append(a) or real_after(*a, **kw))

    app._shutting_down = True
    app._pump_job = "sentinel-should-be-cleared"
    app._pump_main_thread()

    assert app._pump_job is None, "Pump job tracking must be cleared once shutdown begins"
    assert not after_calls, "No new after() schedule may be made once shutdown begins"
    assert not sentinel_ran, (
        "The queued main-thread call must not run either -- the callback "
        "must be a complete no-op once _shutting_down is set, not merely "
        "skip the reschedule"
    )
    assert app._main_thread_calls.qsize() == 1, "The queue must be left untouched"


def test_repeated_destroy_is_safe(app):
    app.destroy()
    app.destroy()  # must not raise


def test_no_pump_main_thread_stale_warning_in_focused_teardown(app, tk_root, capfd):
    # Tcl's "invalid command name ... after script" error for a leaked
    # callback is written directly to the process's real stderr file
    # descriptor by the Tcl runtime, bypassing Python's sys.stderr object
    # entirely -- a plain sys.stderr reassignment cannot observe it (this
    # was confirmed against the unfixed code before writing this test: a
    # Python-level capture stayed empty even while the raw process output
    # showed the warning). capfd captures at the file-descriptor level,
    # the same level pytest's own default capture uses -- and the same
    # level that surfaced these warnings in the real full-suite runs.
    capfd.readouterr()  # discard setup noise

    _pump_until(app, 0.2)  # multiple reschedules, matching real usage
    app.destroy()

    # A still-alive interpreter (the session tk_root) pumping afterward is
    # what gave the process's shared notifier a chance to surface the
    # leaked callback in the original defect -- exercise that same window.
    deadline = time.time() + 0.3
    while time.time() < deadline:
        tk_root.update()
        time.sleep(0.02)

    out, err = capfd.readouterr()
    combined = out + err
    assert "_pump_main_thread" not in combined, (
        f"_pump_main_thread must not appear in stale-callback warnings "
        f"after a focused destroy/pump cycle; captured: {combined!r}"
    )
