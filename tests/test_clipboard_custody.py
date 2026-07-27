"""Unit tests for Slice A clipboard write custody (core, no Tk)."""

from __future__ import annotations

import threading

from cache_vault.core import models
from cache_vault.core.clipboard_custody import (
    DEFAULT_FALLBACK_TTL_S,
    MAX_RECORD_TTL_S,
    ClipboardWriteSuppressor,
    ClipboardWriter,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _writer(suppressor: ClipboardWriteSuppressor, store: dict, *, fail: bool = False) -> ClipboardWriter:
    def _set(text: str) -> bool:
        if fail:
            return False
        store["text"] = text
        store["seq"] = store.get("seq", 0) + 1
        return True

    return ClipboardWriter(
        suppressor,
        set_text=_set,
        restore_text=_set,
        get_sequence=lambda: store.get("seq"),
    )


# --- lifecycle ---------------------------------------------------------------

def test_committed_record_suppresses_exactly_once():
    s = ClipboardWriteSuppressor()
    token = s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="alpha")
    assert s.commit(token, sequence=10)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="alpha", sequence=10) is True
    # one-shot consumption + immediate removal
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="alpha", sequence=10) is False
    assert len(s) == 0


def test_pending_record_never_suppresses():
    s = ClipboardWriteSuppressor()
    s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="alpha")
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="alpha", sequence=1) is False


def test_commit_unknown_or_double_commit_rejected():
    s = ClipboardWriteSuppressor()
    assert s.commit("missing-token", sequence=1) is False
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="x")
    assert s.commit(token, sequence=1) is True
    assert s.commit(token, sequence=2) is False


def test_cancel_removes_record():
    s = ClipboardWriteSuppressor()
    token = s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="alpha")
    assert s.cancel(token) is True
    assert s.cancel(token) is False
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="alpha") is False


def test_operation_tokens_are_unique():
    s = ClipboardWriteSuppressor()
    tokens = {
        s.begin(operation="copy_clip", content_type=models.CONTENT_TEXT, fingerprint="same")
        for _ in range(200)
    }
    assert len(tokens) == 200


# --- failed writes -------------------------------------------------------------

def test_failed_write_cancels_record():
    s = ClipboardWriteSuppressor()
    store: dict = {}
    w = _writer(s, store, fail=True)
    assert w.write_text("alpha", operation="copy_clip") is False
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="alpha") is False
    assert len(s) == 0


def test_raising_write_callable_cancels_record():
    s = ClipboardWriteSuppressor()

    def _boom(_text: str) -> bool:
        raise RuntimeError("clipboard locked")

    w = ClipboardWriter(s, set_text=_boom, get_sequence=lambda: None)
    assert w.write_text("alpha", operation="copy_clip") is False
    assert len(s) == 0


# --- sequence matching -----------------------------------------------------------

def test_sequence_match_suppresses_despite_fingerprint_difference():
    clock = FakeClock()
    s = ClipboardWriteSuppressor(clock=clock)
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="recorded")
    s.commit(token, sequence=42)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="readback-differs", sequence=42) is True


def test_sequence_mismatch_does_not_consume_record():
    s = ClipboardWriteSuppressor()
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="same")
    s.commit(token, sequence=10)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="same", sequence=11) is False
    assert len(s) == 1  # record retained, not wrongly consumed
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="same", sequence=10) is True


def test_sequence_record_outlives_fallback_ttl():
    clock = FakeClock()
    s = ClipboardWriteSuppressor(clock=clock)
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="x")
    s.commit(token, sequence=7)
    clock.advance(DEFAULT_FALLBACK_TTL_S * 4)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="x", sequence=7) is True


def test_max_ttl_purges_sequence_records():
    clock = FakeClock()
    s = ClipboardWriteSuppressor(clock=clock)
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="x")
    s.commit(token, sequence=7)
    clock.advance(MAX_RECORD_TTL_S + 0.1)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="x", sequence=7) is False
    assert len(s) == 0


# --- fallback TTL (missing sequence) --------------------------------------------

def test_missing_sequence_suppresses_within_fallback_ttl():
    clock = FakeClock()
    s = ClipboardWriteSuppressor(clock=clock)
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="fb")
    s.commit(token, sequence=None)
    clock.advance(DEFAULT_FALLBACK_TTL_S / 2)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="fb", sequence=None) is True


def test_missing_sequence_expires_after_fallback_ttl():
    clock = FakeClock()
    s = ClipboardWriteSuppressor(clock=clock)
    token = s.begin(operation="op", content_type=models.CONTENT_TEXT, fingerprint="fb")
    s.commit(token, sequence=None)
    clock.advance(DEFAULT_FALLBACK_TTL_S + 0.01)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="fb", sequence=None) is False


# --- content type / fingerprint ---------------------------------------------------

def test_content_type_is_explicit():
    s = ClipboardWriteSuppressor()
    token = s.begin(operation="op", content_type=models.CONTENT_IMAGE, fingerprint="H")
    s.commit(token, sequence=3)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="H", sequence=3) is False
    assert s.should_suppress(content_type=models.CONTENT_IMAGE, fingerprint="H", sequence=3) is True


def test_image_fingerprint_matches_capture_pipeline():
    png = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    s = ClipboardWriteSuppressor()
    store: dict = {}
    w = ClipboardWriter(
        s,
        set_image=lambda b: True,
        get_sequence=lambda: 5,
    )
    assert w.write_image(png, operation="copy_clip_image") is True
    # monitor computes models.bytes_hash(png) — the record must match exactly
    assert s.should_suppress(
        content_type=models.CONTENT_IMAGE,
        fingerprint=models.bytes_hash(png),
        sequence=5,
    ) is True


# --- multi-write scenarios -----------------------------------------------------------

def test_rapid_identical_writes_are_independently_suppressed():
    s = ClipboardWriteSuppressor()
    store: dict = {}
    w = _writer(s, store)
    assert w.write_text("dup", operation="copy_clip") is True   # seq 1
    assert w.write_text("dup", operation="copy_clip") is True   # seq 2
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="dup", sequence=1) is True
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="dup", sequence=2) is True
    assert len(s) == 0
    # a third identical event has no record — it is a genuine copy
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="dup", sequence=3) is False


def test_later_genuine_identical_copy_is_capturable():
    s = ClipboardWriteSuppressor()
    store: dict = {}
    w = _writer(s, store)
    assert w.write_text("x", operation="copy_clip") is True
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="x", sequence=1) is True
    # consumed — a later genuine identical copy must not be suppressed
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="x", sequence=2) is False


def test_restore_text_uses_own_operation_record():
    s = ClipboardWriteSuppressor()
    store: dict = {}
    w = _writer(s, store)
    assert w.restore_text(None, operation="quick_paste_restore") is False
    assert len(s) == 0
    assert w.restore_text("prior", operation="quick_paste_restore") is True
    snap = s.snapshot()
    assert len(snap) == 1
    assert snap[0]["operation"] == "quick_paste_restore"
    assert snap[0]["committed"] is True
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint="prior", sequence=1) is True


# --- concurrency -----------------------------------------------------------------

def test_concurrent_writers_and_monitor_one_shot_total():
    s = ClipboardWriteSuppressor()
    lock = threading.Lock()
    state = {"seq": 0}
    results: list[bool] = []
    errors: list[BaseException] = []

    def _set(_text: str) -> bool:
        with lock:
            state["seq"] += 1
            return True

    w = ClipboardWriter(s, set_text=_set, get_sequence=lambda: state["seq"])

    def worker(n: int) -> None:
        for i in range(50):
            fp = f"clip-{n}-{i}"
            try:
                assert w.write_text(fp, operation="stress") is True
                with lock:
                    seq = state["seq"]
                results.append(
                    s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint=fp, sequence=seq)
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    # 400 writes, each record consumed exactly once, never twice
    assert results.count(True) == 400
    assert results.count(False) == 0
    assert len(s) == 0


def test_concurrent_begin_cancel_churn_is_safe():
    s = ClipboardWriteSuppressor()
    errors: list[BaseException] = []

    def churn(n: int) -> None:
        try:
            for i in range(200):
                token = s.begin(operation="churn", content_type=models.CONTENT_TEXT, fingerprint=f"{n}-{i}")
                if i % 2:
                    s.cancel(token)
                else:
                    s.commit(token, sequence=i)
                    s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint=f"{n}-{i}", sequence=i)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=churn, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    snap = s.snapshot()
    assert isinstance(snap, list)
