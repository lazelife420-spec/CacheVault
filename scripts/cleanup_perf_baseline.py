"""Vault Cleanup / Performance investigation -- Part C baseline.

Builds a realistic-scale fixture on disk and times the actual code paths
the GUI calls at startup and during a refresh, with real SQL query counts
via sqlite3's execute-hook. Prints a report; makes no code changes.

Usage: python scripts/cleanup_perf_baseline.py
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

from cache_vault.core import image_assets, models, smart_folders  # noqa: E402
from cache_vault.core.models import Clip  # noqa: E402
from cache_vault.core.settings import Settings  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402
from cache_vault.core import duplicates  # noqa: E402

TMP_ROOT = Path(os.environ.get("TEMP", "/tmp")) / "cachevault_perf_baseline"
DB_PATH = TMP_ROOT / "cache_vault.db"


class QueryCounter:
    """Counts SQL statements executed on a connection via set_trace_callback."""

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


def timed(label: str, fn, *, conn: sqlite3.Connection | None = None):
    if conn is not None:
        with QueryCounter(conn) as qc:
            start = time.perf_counter()
            result = fn()
            elapsed = time.perf_counter() - start
        print(f"{label:<45} {elapsed*1000:8.2f} ms   {qc.count:4d} SQL statements")
    else:
        start = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - start
        print(f"{label:<45} {elapsed*1000:8.2f} ms")
    return result


def _png(color) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1920, 1080), color).save(buf, format="PNG")
    return buf.getvalue()


def build_fixture(n_text=1000, n_images=500, n_removed=300, n_collections=8, n_favorites=60):
    print(f"Building fixture: {n_text} text, {n_images} images, {n_removed} removed...")
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(TMP_ROOT)
    if DB_PATH.exists():
        DB_PATH.unlink()

    storage = VaultStorage(str(DB_PATH))
    collections = [f"Collection {i}" for i in range(n_collections)]
    small_png = _png((10, 10, 10))

    t0 = time.perf_counter()
    for i in range(n_text):
        clip = Clip(
            content_hash=models.content_hash(f"text clip body number {i}"),
            content_type=models.CONTENT_TEXT,
            content=f"text clip body number {i}" * 5,
            preview=f"text clip body number {i}",
            classification=models.CLASS_PLAIN,
            is_pinned=(i < n_favorites),
            collection=collections[i % n_collections] if i % 3 == 0 else None,
        )
        storage.add_clip(clip)
    print(f"  {n_text} text clips inserted in {time.perf_counter()-t0:.2f}s")

    t0 = time.perf_counter()
    real_screenshot_count = 0
    for i in range(n_images):
        # Vary size: most are realistic 1920x1080 screenshots, a few tiny.
        if i % 50 == 0:
            data = _png((i % 255, 0, 0))
            w, h = 8, 8
        else:
            data = _png((i % 255, 100, 50))
            w, h = 1920, 1080
            real_screenshot_count += 1
        chash = models.bytes_hash(data)
        clip = Clip(
            content_hash=chash,
            content_type=models.CONTENT_IMAGE,
            content="[Screenshot PNG]",
            preview="Screenshot",
            classification=models.CLASS_IMAGE,
            source_app="test.exe",
        )
        storage.add_clip(clip)
        record = image_assets.ClipAssetRecord(
            asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png",
            file_ext="png", size_bytes=len(data), sha256=chash,
            created_at=clip.created_at, original_name=None,
            storage_name=image_assets.make_storage_name(clip.id, "png"),
            width=w, height=h,
        )
        storage.save_clip_asset(record, data)
    print(f"  {n_images} image clips + assets inserted in {time.perf_counter()-t0:.2f}s"
          f" ({real_screenshot_count} real-sized, rest tiny)")

    t0 = time.perf_counter()
    for i in range(n_removed):
        clip = Clip(
            content_hash=models.content_hash(f"removed clip {i}"),
            content_type=models.CONTENT_TEXT,
            content=f"removed clip {i}",
            preview=f"removed clip {i}",
        )
        storage.add_clip(clip)
        storage.soft_delete(clip.id)
    print(f"  {n_removed} recently-removed clips inserted in {time.perf_counter()-t0:.2f}s")

    storage.close()
    print("Fixture build complete.\n")


def main():
    build_fixture()

    print("=" * 90)
    print("BASELINE TIMINGS (cold, freshly-opened connection each time unless noted)")
    print("=" * 90)

    # --- 1. DB open + migration -------------------------------------------------
    def _open():
        s = VaultStorage(str(DB_PATH))
        return s
    storage = timed("VaultStorage.__init__ (open + migration)", _open)

    vault = Vault(storage=storage, settings=Settings())

    # --- 2. Home dashboard counts ------------------------------------------------
    timed("vault.counts() [sidebar badges + smart folders]", lambda: vault.counts(), conn=storage.conn)

    # --- 3. First clip-list render, paginated (matches MAX_VISIBLE_CLIPS=120) ---
    timed("storage.list_clips(limit=120) [actual GUI page size]",
          lambda: storage.list_clips(limit=120), conn=storage.conn)

    # --- 4. Unbounded list_clips (what happens if a code path forgets a limit) --
    all_clips = timed("storage.list_clips() [UNBOUNDED -- all live clips]",
                       lambda: storage.list_clips(), conn=storage.conn)
    print(f"  -> materialized {len(all_clips)} Clip objects")

    # --- 5. count_clips (lightweight total, for pagination footer) --------------
    timed("storage.count_clips() [lightweight COUNT only]",
          lambda: storage.count_clips(None), conn=storage.conn)

    # --- 6. Duplicate-group Python-side scan (what the Duplicates dialog uses) --
    timed("duplicates.find_exact_duplicate_groups() [Python-side, opens dialog]",
          lambda: duplicates.find_exact_duplicate_groups(storage), conn=storage.conn)

    # --- 7. smart_folders.count_all (already SQL aggregates, N small queries) ---
    timed("smart_folders.count_all()", lambda: smart_folders.count_all(storage), conn=storage.conn)

    # --- 8. Reader-connection open cost (used by every background refresh) -----
    def _reader_roundtrip():
        with storage.reader_connection() as reader:
            reader.execute("SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL").fetchone()
    timed("storage.reader_connection() open+query+close", _reader_roundtrip)

    # --- 9. Asset existence checks for N managed images -------------------------
    rows = storage.conn.execute("SELECT storage_name FROM clip_assets").fetchall()
    def _check_all_exist():
        base = image_assets.assets_dir()
        return sum(1 for r in rows if (base / r["storage_name"]).is_file())
    timed(f"Path.is_file() existence check x{len(rows)} managed assets", _check_all_exist)

    # --- 10. Thumbnail decode timing (PIL open+thumbnail, NOT full-res render) --
    asset_bytes = []
    base = image_assets.assets_dir()
    for r in rows[:200]:
        data = (base / r["storage_name"]).read_bytes()
        asset_bytes.append(data)

    def _decode_thumbnails():
        out = 0
        for data in asset_bytes:
            with Image.open(BytesIO(data)) as img:
                img.thumbnail((96, 96))
                out += 1
        return out
    timed(f"PIL decode+thumbnail(96x96) x{len(asset_bytes)} images", _decode_thumbnails)

    def _decode_full_res():
        out = 0
        for data in asset_bytes:
            with Image.open(BytesIO(data)) as img:
                img.load()
                out += 1
        return out
    timed(f"PIL full-resolution decode x{len(asset_bytes)} images (NOT what grid should do)",
          _decode_full_res)

    # --- 11. home dashboard's "Recent"/"Today"/collections queries -------------
    from cache_vault.core.search import SearchQuery
    from cache_vault.core.storage import (
        FILTER_TODAY, FILTER_LINKS, FILTER_FAVORITES, FILTER_SCREENSHOTS,
    )
    def _home_queries_unbounded():
        vault.list_clips(SearchQuery())[:6]
        vault.list_clips(SearchQuery(filter_name=FILTER_TODAY))[:6]
        vault.list_clips(SearchQuery(filter_name=FILTER_LINKS))[:6]
        vault.list_clips(SearchQuery(filter_name=FILTER_FAVORITES))[:6]
        vault.list_clips(SearchQuery(filter_name=FILTER_SCREENSHOTS))[:6]
    timed("Home dashboard 'recent slices' BEFORE (unbounded, old behavior)",
          _home_queries_unbounded, conn=storage.conn)

    def _home_queries_bounded():
        home_recent_window = 50  # cache_vault.ui.shell.HOME_RECENT_WINDOW
        vault.list_clips(SearchQuery(), limit=home_recent_window)
        vault.list_clips(SearchQuery(filter_name=FILTER_TODAY), limit=home_recent_window)
        vault.list_clips(SearchQuery(filter_name=FILTER_LINKS), limit=6)
        vault.list_clips(SearchQuery(filter_name=FILTER_FAVORITES), limit=6)
        vault.list_clips(SearchQuery(filter_name=FILTER_SCREENSHOTS), limit=6)
    timed("Home dashboard 'recent slices' AFTER (bounded, current code)",
          _home_queries_bounded, conn=storage.conn)

    storage.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
