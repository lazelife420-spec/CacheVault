"""Vault Cleanup Suggestions -- query-count and duration measurement for the
editable-copy N+1 fix (draft PR #67 independent review finding).

Builds a realistic fixture and runs two full scans (cold + repeat),
counting every SQL statement issued via sqlite3's trace callback and timing
each run. Prints a report; makes no code changes. Run before and after a
change to compare.

Usage: python scripts/cleanup_query_count_check.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from cache_vault.core import cleanup_suggestions as cs  # noqa: E402
from cache_vault.core import image_assets, models  # noqa: E402
from cache_vault.core.models import Clip  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402

TMP_ROOT = Path(os.environ.get("TEMP", "/tmp")) / "cachevault_query_count_check"
DB_PATH = TMP_ROOT / "cache_vault.db"


class QueryCounter:
    def __init__(self, conn: sqlite3.Connection):
        self.count = 0
        self._conn = conn

    def __enter__(self):
        self.count = 0
        self._conn.set_trace_callback(self._on_sql)
        return self

    def __exit__(self, *exc):
        self._conn.set_trace_callback(None)

    def _on_sql(self, _stmt: str) -> None:
        self.count += 1


def _png(color) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (100, 100), color).save(buf, format="PNG")
    return buf.getvalue()


def build_fixture(n_text=1200, n_images=535, n_dup_groups=90):
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(TMP_ROOT)
    if DB_PATH.exists():
        DB_PATH.unlink()

    storage = VaultStorage(str(DB_PATH))
    for i in range(n_text):
        clip = Clip(
            content_hash=models.content_hash(f"text clip body number {i}"),
            content_type=models.CONTENT_TEXT,
            content=f"text clip body number {i}" * 5,
            preview=f"text clip body number {i}",
            classification=models.CLASS_PLAIN,
        )
        storage.add_clip(clip)

    for g in range(n_dup_groups):
        data = _png((10, (g * 3) % 255, (g * 7) % 255))
        for _ in range(3):
            chash = models.bytes_hash(data)
            clip = Clip(
                content_hash=chash, content_type=models.CONTENT_IMAGE,
                content="[Screenshot PNG]", preview="Screenshot",
                classification=models.CLASS_IMAGE, source_app="test.exe",
            )
            storage.add_clip(clip)
            record = image_assets.ClipAssetRecord(
                asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png",
                file_ext="png", size_bytes=len(data), sha256=chash,
                created_at=clip.created_at, original_name=None,
                storage_name=image_assets.make_storage_name(clip.id, "png"),
                width=100, height=100,
            )
            storage.save_clip_asset(record, data)
    remaining = n_images - n_dup_groups * 3
    for i in range(max(0, remaining)):
        data = _png((i % 255, 40, 80))
        chash = models.bytes_hash(data)
        clip = Clip(
            content_hash=chash, content_type=models.CONTENT_IMAGE,
            content="[Screenshot PNG]", preview="Screenshot",
            classification=models.CLASS_IMAGE, source_app="test.exe",
        )
        storage.add_clip(clip)
        record = image_assets.ClipAssetRecord(
            asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png",
            file_ext="png", size_bytes=len(data), sha256=chash,
            created_at=clip.created_at, original_name=None,
            storage_name=image_assets.make_storage_name(clip.id, "png"),
            width=100, height=100,
        )
        storage.save_clip_asset(record, data)

    storage.close()


def main():
    build_fixture()
    storage = VaultStorage(str(DB_PATH))
    total_live = len(storage.list_clips())
    print(f"Fixture: {total_live} live clips (1200 text + 535 images, 90 duplicate groups x3)")
    print("=" * 90)

    with QueryCounter(storage.conn) as qc:
        t0 = time.perf_counter()
        result1 = cs.run_scan(storage)
        elapsed1 = time.perf_counter() - t0
    print(f"Initial scan:  {elapsed1*1000:8.2f} ms   {qc.count:5d} SQL statements")
    print(f"  duplicate_screenshot_groups={len(result1.duplicate_screenshot_groups)} "
          f"total_reviewable_items={result1.total_reviewable_items}")

    with QueryCounter(storage.conn) as qc:
        t0 = time.perf_counter()
        result2 = cs.run_scan(storage)
        elapsed2 = time.perf_counter() - t0
    print(f"Repeat scan:   {elapsed2*1000:8.2f} ms   {qc.count:5d} SQL statements")
    print(f"  duplicate_screenshot_groups={len(result2.duplicate_screenshot_groups)} "
          f"total_reviewable_items={result2.total_reviewable_items}")

    assert len(result1.duplicate_screenshot_groups) == len(result2.duplicate_screenshot_groups)
    assert result1.total_reviewable_items == result2.total_reviewable_items
    storage.close()
    print("\nResult counts identical across both runs (sanity check passed).")


if __name__ == "__main__":
    main()
