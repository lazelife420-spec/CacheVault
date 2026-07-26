from __future__ import annotations

import queue
import threading
import time

import pytest

from tests.tk_support import wait_for_refresh


class _FakeRefreshApp:
    def __init__(self, updates=None):
        self._refresh_generation = 1
        self._refresh_job = None
        self._refresh_workers_in_flight = 1
        self._refresh_request_queue = queue.SimpleQueue()
        self._main_thread_calls = queue.SimpleQueue()
        self._updates = iter(updates or ())
        self.applied = []

    def update(self):
        try:
            action = next(self._updates)
        except StopIteration:
            return
        action(self)

    def _apply_refresh_snapshot(self, generation, *_args, **_kwargs):
        self.applied.append(("snapshot", generation))
        self._refresh_workers_in_flight = max(
            0, self._refresh_workers_in_flight - 1
        )

    def _apply_refresh_failure(self, generation, *_args, **_kwargs):
        self.applied.append(("failure", generation))
        self._refresh_workers_in_flight = max(
            0, self._refresh_workers_in_flight - 1
        )


class _FakeGlobalApp:
    def __init__(self, updates):
        self._refresh_generation = None
        self._refresh_job = "job-1"
        self._refresh_workers_in_flight = 1
        self._refresh_request_queue = queue.SimpleQueue()
        self._main_thread_calls = queue.SimpleQueue()
        self._updates = iter(updates)

    def update(self):
        try:
            action = next(self._updates)
        except StopIteration:
            return
        action(self)


def _apply_target(app):
    app._apply_refresh_snapshot(app._refresh_generation)


def test_immediate_settlement_returns_promptly():
    app = _FakeRefreshApp()
    app._refresh_workers_in_flight = 0
    started = time.monotonic()

    wait_for_refresh(app, timeout=0.05)

    assert time.monotonic() - started < 0.03


def test_known_refresh_generation_completes_successfully():
    app = _FakeRefreshApp([_apply_target])

    wait_for_refresh(app, timeout=0.05)

    assert app.applied == [("snapshot", 1)]


def test_known_generation_may_be_silent_until_bounded_completion():
    def delayed_apply(app):
        time.sleep(0.025)
        _apply_target(app)

    app = _FakeRefreshApp([delayed_apply])
    started = time.monotonic()

    wait_for_refresh(
        app, timeout=0.01, max_timeout=0.06, poll_interval=0.001
    )

    elapsed = time.monotonic() - started
    assert elapsed > 0.01
    assert elapsed < 0.06
    assert app.applied == [("snapshot", 1)]


def test_continuing_progress_extends_wait_within_bounded_limit():
    def progress(job_id):
        def update(app):
            app._refresh_job = job_id
            time.sleep(0.008)
        return update

    def settle(app):
        app._refresh_job = None
        app._refresh_workers_in_flight = 0

    app = _FakeGlobalApp(
        [progress("job-2"), progress("job-3"), progress("job-4"), settle]
    )
    started = time.monotonic()

    wait_for_refresh(
        app, timeout=0.012, max_timeout=0.09, poll_interval=0.001
    )

    elapsed = time.monotonic() - started
    assert elapsed > 0.012
    assert elapsed < 0.09


def test_no_progress_deadlock_still_fails():
    app = _FakeRefreshApp()

    with pytest.raises(AssertionError, match="refresh did not settle"):
        wait_for_refresh(
            app, timeout=0.015, max_timeout=0.04, poll_interval=0.001
        )


def test_failure_message_includes_pending_state_diagnostics():
    app = _FakeRefreshApp()
    app._refresh_job = "after#87"
    app._refresh_request_queue.put((1, "all", None))
    app._main_thread_calls.put(object())

    with pytest.raises(AssertionError) as raised:
        wait_for_refresh(
            app, timeout=0.015, max_timeout=0.04, poll_interval=0.001
        )

    message = str(raised.value)
    for detail in (
        "target_generation=1",
        "target_completed=False",
        "after#87",
        "progress_changes=",
        "stalled_for=",
        "thread_count=",
    ):
        assert detail in message


def test_unrelated_later_refresh_does_not_invalidate_completed_target():
    def complete_then_schedule_later(app):
        app._apply_refresh_snapshot(1)
        app._refresh_generation = 2
        app._refresh_workers_in_flight = 1
        app._refresh_job = "later-job"

    app = _FakeRefreshApp([complete_then_schedule_later])

    wait_for_refresh(app, timeout=0.03)

    assert app.applied == [("snapshot", 1)]
    assert app._refresh_generation == 2
    assert app._refresh_workers_in_flight == 1


def test_repeated_waits_restore_observers_without_leaks():
    app = _FakeRefreshApp()
    snapshot_function = app._apply_refresh_snapshot.__func__
    failure_function = app._apply_refresh_failure.__func__
    baseline_threads = threading.active_count()

    for generation in range(1, 9):
        app._refresh_generation = generation
        app._refresh_workers_in_flight = 1
        app._refresh_job = None
        app._updates = iter([_apply_target])
        wait_for_refresh(app, timeout=0.03)
        assert "_apply_refresh_snapshot" not in app.__dict__
        assert "_apply_refresh_failure" not in app.__dict__
        assert app._apply_refresh_snapshot.__func__ is snapshot_function
        assert app._apply_refresh_failure.__func__ is failure_function

    assert threading.active_count() == baseline_threads
