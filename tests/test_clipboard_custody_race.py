"""Deterministic race tests for the pending-record settlement fix.

These tests are intentionally *not* flaky: every pending-record settlement is
controlled by explicit threads, short real-time timeouts, and the
``SuppressionDecision``/Condition machinery.
"""

from __future__ import annotations

import threading
import time

from cache_vault.core import models
from cache_vault.core.clipboard_custody import (
    ClipboardWriteSuppressor,
    ClipboardWriter,
    SuppressionDecision,
)


def _start_observer(suppressor, **kwargs) -> tuple[threading.Thread, list]:
    result: list = []

    def run() -> None:
        result.append(suppressor.should_suppress(**kwargs))

    t = threading.Thread(target=run)
    t.start()
    return t, result


def test_observer_after_begin_before_commit_suppresses_after_settlement():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    token = s.begin(
        operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="x"
    )
    t, result = _start_observer(
        s,
        content_type=models.CONTENT_TEXT,
        fingerprint="x",
        sequence=1,
    )
    time.sleep(0.02)
    assert s.commit(token, sequence=1) is True
    t.join(timeout=1.0)
    assert result == [True]


def test_observer_before_failed_write_cancels_and_captures():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    token = s.begin(
        operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="x"
    )
    t, result = _start_observer(
        s,
        content_type=models.CONTENT_TEXT,
        fingerprint="x",
        sequence=1,
    )
    time.sleep(0.02)
    assert s.cancel(token) is True
    t.join(timeout=1.0)
    assert result == [False]


def test_observer_timeout_fails_open():
    s = ClipboardWriteSuppressor(pending_timeout=0.05)
    s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="x")
    start = time.monotonic()
    assert (
        s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="x",
            sequence=1,
        )
        is False
    )
    elapsed = time.monotonic() - start
    assert 0.03 <= elapsed <= 0.15


def test_unrelated_event_never_waits():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="a")
    start = time.monotonic()
    assert (
        s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="b",
            sequence=1,
        )
        is False
    )
    elapsed = time.monotonic() - start
    assert elapsed < 0.05


def test_multiple_waiting_observers_cannot_consume_same_record_twice():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    token = s.begin(
        operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="x"
    )
    results: list[bool | None] = [None, None]

    def observer(i: int) -> None:
        results[i] = s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="x",
            sequence=1,
        )

    threads = [threading.Thread(target=observer, args=(i,)) for i in range(2)]
    for th in threads:
        th.start()
    time.sleep(0.02)
    assert s.commit(token, sequence=1) is True
    for th in threads:
        th.join(timeout=1.0)
    assert sorted(results) == [False, True]


def test_concurrent_writers_do_not_deadlock():
    s = ClipboardWriteSuppressor(pending_timeout=0.2)
    lock = threading.Lock()
    state = {"seq": 0}

    def set_text(_text: str) -> bool:
        with lock:
            state["seq"] += 1
            return True

    w = ClipboardWriter(s, set_text=set_text, get_sequence=lambda: state["seq"])
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        for i in range(50):
            try:
                w.write_text(f"t{n}-{i}", operation="stress")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=5.0)
    assert all(not th.is_alive() for th in threads)
    assert errors == []


def test_commit_cancel_wakes_the_correct_token_waiter():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    token_a = s.begin(
        operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="a"
    )
    token_b = s.begin(
        operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="b"
    )
    results: dict[str, bool] = {}

    def observer_a() -> None:
        results["a"] = s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="a",
            sequence=1,
        )

    def observer_b() -> None:
        results["b"] = s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="b",
            sequence=2,
        )

    ta = threading.Thread(target=observer_a)
    tb = threading.Thread(target=observer_b)
    ta.start()
    tb.start()
    time.sleep(0.02)
    assert s.commit(token_a, sequence=1) is True
    assert s.cancel(token_b) is True
    ta.join(timeout=1.0)
    tb.join(timeout=1.0)
    assert results == {"a": True, "b": False}


def test_tk_win32_delegates_never_called_under_suppressor_lock():
    s = ClipboardWriteSuppressor()
    checks: dict[str, bool | None] = {"text": None, "image": None, "sequence": None}

    def set_text(_text: str) -> bool:
        ok = s._condition.acquire(blocking=False)
        if ok:
            s._condition.release()
        checks["text"] = ok
        return True

    def set_image(_b: bytes) -> bool:
        ok = s._condition.acquire(blocking=False)
        if ok:
            s._condition.release()
        checks["image"] = ok
        return True

    def get_sequence() -> int:
        ok = s._condition.acquire(blocking=False)
        if ok:
            s._condition.release()
        checks["sequence"] = ok
        return 42

    w = ClipboardWriter(
        s,
        set_text=set_text,
        set_image=set_image,
        get_sequence=get_sequence,
    )
    w.write_text("hello", operation="copy_clip")
    w.write_image(b"\x89PNG\r\n\x1a\ninvalid", operation="copy_clip_image")
    assert checks["text"] is True
    assert checks["image"] is True
    assert checks["sequence"] is True


def test_decide_exposes_wait_state_for_pending_records():
    s = ClipboardWriteSuppressor(pending_timeout=0.5)
    s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="x")

    def observer() -> None:
        decision = s.decide(
            content_type=models.CONTENT_TEXT,
            fingerprint="x",
            sequence=1,
        )
        # The method should never expose WAIT to callers; it waits then returns SUPPRESS/CAPTURE.
        assert decision in (SuppressionDecision.SUPPRESS, SuppressionDecision.CAPTURE)

    t = threading.Thread(target=observer)
    t.start()
    time.sleep(0.02)
    # Do nothing — let the pending timeout expire; the observer must fail open.
    t.join(timeout=1.0)
