"""Regression and stress test for DEF-002: SQLite Concurrency Synchronization."""

import concurrent.futures
import sqlite3
import tempfile
from pathlib import Path

import pytest
from cache_vault.core import models
from cache_vault.core.models import Clip
from cache_vault.core.storage import VaultStorage


def create_test_clip(index: int) -> Clip:
    cid = f"clip_{index:04d}_{models.new_id()[:8]}"
    return Clip(
        id=cid,
        created_at=models.now_iso(),
        updated_at=models.now_iso(),
        content_hash=f"hash_{index}",
        content_type=models.CONTENT_TEXT,
        content=f"Concurrency payload content {index}",
        preview=f"Concurrency payload {index}",
        source_app="pytest_concurrency",
    )


def test_sqlite_concurrency_stress():
    """Execute concurrent reads and writes across multiple worker threads.

    On base un-synchronized VaultStorage, concurrent execution on self.conn
    raises sqlite3.InterfaceError or causes lost/corrupted writes.
    With proper RLock-based connection serialization, all operations succeed
    with 0 exceptions, 0 lost writes, 0 deadlocks, and clean integrity_check.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_concurrency.db"
        storage = VaultStorage(db_path)

        num_threads = 50
        writes_per_thread = 4
        total_expected_writes = num_threads * writes_per_thread

        exceptions = []
        written_ids = set()
        written_ids_lock = __import__("threading").Lock()

        def worker(thread_idx: int):
            for i in range(writes_per_thread):
                clip_idx = thread_idx * writes_per_thread + i
                clip = create_test_clip(clip_idx)
                try:
                    storage.add_clip(clip)
                    with written_ids_lock:
                        written_ids.add(clip.id)

                    # Interleave reads and updates
                    fetched = storage.get_clip(clip.id)
                    assert fetched is not None, f"Clip {clip.id} not found immediately after write"
                    storage.touch_clip(clip.id)
                    latest = storage.latest_clip()
                    assert latest is not None
                    counts = storage.counts()
                    assert counts["all"] > 0
                except Exception as exc:
                    exceptions.append((thread_idx, i, exc))

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, idx) for idx in range(num_threads)]
            concurrent.futures.wait(futures, timeout=30.0)

        # Qualification metrics
        exception_count = len(exceptions)
        assert exception_count == 0, f"Observed {exception_count} concurrent execution errors: {exceptions[:5]}"

        # Integrity check
        with getattr(storage, "_lock", __import__("contextlib").nullcontext()):
            check_res = storage.conn.execute("PRAGMA integrity_check").fetchone()
            assert check_res[0] == "ok", f"Database integrity check failed: {check_res[0]}"

            actual_count = storage.conn.execute("SELECT COUNT(*) FROM clips").fetchone()[0]

        assert len(written_ids) == total_expected_writes, f"Expected {total_expected_writes} unique clip IDs, got {len(written_ids)}"
        assert actual_count == total_expected_writes, f"Expected DB row count {total_expected_writes}, actual row count {actual_count}"

        # Clean shutdown check
        storage.close()
        assert storage._closed is True


def test_sqlite_reentrant_nested_calls():
    """Verify that nested calls (e.g. add_clip -> latest_clip, set_pinned -> _touch)
    do not self-deadlock when RLock is used.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_nested.db"
        storage = VaultStorage(db_path)

        clip = create_test_clip(1)
        storage.add_clip(clip)
        storage.set_pinned(clip.id, True)

        fetched = storage.get_clip(clip.id)
        assert fetched is not None
        assert fetched.is_pinned is True

        storage.close()
