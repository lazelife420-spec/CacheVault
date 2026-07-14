"""Database storage health inspector and maintenance doctor."""

from __future__ import annotations

import sqlite3
from typing import NamedTuple


class StorageHealthReport(NamedTuple):
    db_size_bytes: int
    reclaimable_bytes: int
    reclaimable_ratio: float
    recommend_vacuum: bool


def inspect_health(conn: sqlite3.Connection) -> StorageHealthReport:
    """Inspect SQLite page stats and compute health / compaction metrics."""
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]

        cursor.execute("PRAGMA freelist_count")
        freelist_count = cursor.fetchone()[0]

        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
    finally:
        cursor.close()

    db_size_bytes = page_count * page_size
    reclaimable_bytes = freelist_count * page_size
    reclaimable_ratio = (freelist_count / page_count) if page_count > 0 else 0.0

    # Compaction recommended if ratio > 20% OR reclaimable bytes > 25MB (25 * 1024 * 1024)
    recommend_vacuum = reclaimable_ratio > 0.20 or reclaimable_bytes > (25 * 1024 * 1024)

    return StorageHealthReport(
        db_size_bytes=db_size_bytes,
        reclaimable_bytes=reclaimable_bytes,
        reclaimable_ratio=reclaimable_ratio,
        recommend_vacuum=recommend_vacuum,
    )


def run_optimize(conn: sqlite3.Connection) -> None:
    """Run PRAGMA optimize to update SQLite query planner indexes."""
    conn.execute("PRAGMA optimize")


def run_vacuum(conn: sqlite3.Connection) -> None:
    """Run a heavy VACUUM command outside transaction mode to reclaim space."""
    old_isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("VACUUM")
    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"Database maintenance VACUUM failed: {exc}") from exc
    finally:
        conn.isolation_level = old_isolation
