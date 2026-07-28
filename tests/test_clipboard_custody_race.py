"""Deterministic race tests for the pending-record settlement fix.

These tests are intentionally *not* flaky: every pending-record settlement is
controlled by explicit threads, short real-time timeouts, and the
``SuppressionDecision``/Condition machinery.
"""

from __future__ import annotations

import threading
import time

import cache_vault.core.clipboard as clipmod
from cache_vault.core import models
from cache_vault.core.clipboard import ClipboardMonitor
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


def test_timed_out_pending_token_is_abandoned_and_cannot_be_revived():
    s = ClipboardWriteSuppressor(pending_timeout=0.03)
    token = s.begin(
        operation="copy_clip",
        content_type=models.CONTENT_TEXT,
        fingerprint="identical",
    )
    results: list[bool] = []

    def observer() -> None:
        results.append(
            s.should_suppress(
                content_type=models.CONTENT_TEXT,
                fingerprint="identical",
                sequence=9,
            )
        )

    waiters = [threading.Thread(target=observer) for _ in range(3)]
    for waiter in waiters:
        waiter.start()
    for waiter in waiters:
        waiter.join(timeout=1.0)

    assert results == [False, False, False]
    assert len(s) == 0
    assert s.commit(token, sequence_before=8, sequence_after=9) is False
    assert len(s) == 0
    # A later genuine identical user copy has no live custody record.
    assert (
        s.should_suppress(
            content_type=models.CONTENT_TEXT,
            fingerprint="identical",
            sequence=10,
        )
        is False
    )


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


def _monitor(monkeypatch, *, sequence, read_text, read_image=lambda: None):
    captures: list[dict] = []
    monkeypatch.setattr(clipmod, "_read_clipboard_text", read_text)
    monkeypatch.setattr(clipmod, "_read_clipboard_image", read_image)
    monkeypatch.setattr(
        clipmod,
        "_foreground_source",
        lambda: {"source_app": "external.exe", "source_window": "External"},
    )
    monitor = ClipboardMonitor(captures.append, get_sequence=sequence)
    monitor._running = True
    return monitor, captures


def test_text_snapshot_retries_when_sequence_changes_during_read(monkeypatch):
    state = {"sequence": 1, "reads": 0}

    def read_text():
        state["reads"] += 1
        if state["reads"] == 1:
            state["sequence"] = 2
            return "stale"
        return "stable"

    monitor, captures = _monitor(
        monkeypatch,
        sequence=lambda: state["sequence"],
        read_text=read_text,
    )
    monitor._emit()

    assert state["reads"] == 2
    assert captures == [
        {
            "text": "stable",
            "clipboard_sequence": 2,
            "source_app": "external.exe",
            "source_window": "External",
        }
    ]


def test_image_snapshot_retries_when_sequence_changes_during_read(monkeypatch):
    from cache_vault.core import image_assets

    state = {"sequence": 4, "reads": 0}

    def read_image():
        state["reads"] += 1
        if state["reads"] == 1:
            state["sequence"] = 5
            return b"stale-image", 1, 1
        return b"stable-image", 2, 3

    monkeypatch.setattr(
        image_assets,
        "canonical_image_fingerprint",
        lambda payload: payload.decode(),
    )
    monitor, captures = _monitor(
        monkeypatch,
        sequence=lambda: state["sequence"],
        read_text=lambda: None,
        read_image=read_image,
    )
    monitor._emit()

    assert state["reads"] == 2
    assert len(captures) == 1
    assert captures[0]["image_png"] == b"stable-image"
    assert captures[0]["width"] == 2
    assert captures[0]["height"] == 3
    assert captures[0]["clipboard_sequence"] == 5


def test_repeated_snapshot_instability_defers_without_wrong_payload(
    monkeypatch,
    caplog,
):
    state = {"sequence": 20, "unstable": True}

    def read_text():
        if state["unstable"]:
            state["sequence"] += 1
        return f"value-{state['sequence']}"

    monitor, captures = _monitor(
        monkeypatch,
        sequence=lambda: state["sequence"],
        read_text=read_text,
    )
    with caplog.at_level("INFO", logger="cache_vault.core.clipboard"):
        monitor._emit()

    assert captures == []
    assert monitor._last_seq is None
    assert "remained unstable after 3 attempts" in caplog.text

    state["unstable"] = False
    monitor._emit()
    assert len(captures) == 1
    assert captures[0]["text"] == f"value-{state['sequence']}"
    assert captures[0]["clipboard_sequence"] == state["sequence"]


def test_stable_payload_retains_bracketing_sequence(monkeypatch):
    monitor, captures = _monitor(
        monkeypatch,
        sequence=lambda: 77,
        read_text=lambda: "stable payload",
    )
    monitor._emit()
    assert captures[0]["text"] == "stable payload"
    assert captures[0]["clipboard_sequence"] == 77


def test_sequence_hijack_external_payload_is_captured(monkeypatch):
    state = {"sequence": 10, "text": "prior"}
    suppressor = ClipboardWriteSuppressor()
    captures: list[dict] = []
    monkeypatch.setattr(clipmod, "_read_clipboard_image", lambda: None)
    monkeypatch.setattr(clipmod, "_read_clipboard_text", lambda: state["text"])
    monkeypatch.setattr(
        clipmod,
        "_foreground_source",
        lambda: {"source_app": "other.exe", "source_window": "Other"},
    )

    def hijacked_write(_text: str) -> bool:
        state["text"] = "internal"
        state["sequence"] = 11
        # Another owner wins before the writer reads its post-write sequence.
        state["text"] = "external"
        state["sequence"] = 12
        return True

    writer = ClipboardWriter(
        suppressor,
        set_text=hijacked_write,
        get_sequence=lambda: state["sequence"],
    )
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=lambda: state["sequence"],
    )
    monitor._running = True

    assert writer.write_text("internal", operation="copy_clip") is True
    [record] = suppressor.snapshot()
    assert record["sequence_before"] == 10
    assert record["sequence_after"] == 12

    monitor._emit()
    assert captures == [
        {
            "text": "external",
            "clipboard_sequence": 12,
            "source_app": "other.exe",
            "source_window": "Other",
        }
    ]
