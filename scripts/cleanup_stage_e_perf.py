"""Vault Cleanup Suggestions v1 -- Stage E performance and correctness proof.

Builds a realistic-scale fixture and exercises the full Stage A-C pipeline
against it:

  1. Initial scan: duration, SQL statement count, rehash count.
  2. Repeat scan (no changes): duration, and proof that duplicate-screenshot
     detection reuses the stored SHA-256 and never rehashes file bytes.
  3. Decision persistence: "Ignore" a group, rescan, confirm it's suppressed;
     confirm a changed group (new duplicate added) is NOT suppressed by a
     stale fingerprint.
  4. Mutation: move a selection to Recently Removed, confirm a receipt is
     written, confirm zero permanent deletions / zero bytes reclaimed in the
     receipt body.
  5. Restore proof: restore one moved clip, confirm it reappears in a fresh
     scan's live population.

Makes real assertions (not just prints) so a failure is loud. Prints a
report at the end. Usage: python scripts/cleanup_stage_e_perf.py
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
from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection  # noqa: E402
from cache_vault.core.cleanup_store import (  # noqa: E402
    DECISION_IGNORED,
    SCOPE_GROUP,
    get_decision,
    is_suppressed,
    record_decision,
)
from cache_vault.core.events import EventLog
from cache_vault.core.models import Clip  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402

TMP_ROOT = Path(os.environ.get("TEMP", "/tmp")) / "cachevault_cleanup_stage_e"
DB_PATH = TMP_ROOT / "cache_vault.db"

N_TEXT = 1200
N_TEXT_DUP_GROUPS = 40          # each group has 3 identical-text copies
N_IMAGES_UNIQUE = 230           # unique, non-duplicated real-sized screenshots
N_DUP_GROUPS = 90               # duplicate-screenshot groups...
DUP_GROUP_SIZE = 3              # ...x3 copies each = 270 duplicate-screenshot clips
N_TINY = 25
N_MISSING = 10
N_REMOVED = 600
N_COLLECTIONS = 10
N_FAVORITES = 80


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


def _png(color, size=(1920, 1080)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _add_image_clip(storage, *, data, width, height, is_pinned=False, collection=None):
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash,
        content_type=models.CONTENT_IMAGE,
        content="[Screenshot PNG]",
        preview="Screenshot",
        classification=models.CLASS_IMAGE,
        source_app="test.exe",
        is_pinned=is_pinned,
        collection=collection,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=width, height=height,
    )
    storage.save_clip_asset(record, data)
    return clip


def build_fixture():
    print(f"Building fixture: {N_TEXT} text, "
          f"{N_IMAGES_UNIQUE + N_DUP_GROUPS * DUP_GROUP_SIZE + N_TINY + N_MISSING} images, "
          f"{N_REMOVED} pre-existing removed...")
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(TMP_ROOT)
    if DB_PATH.exists():
        DB_PATH.unlink()

    storage = VaultStorage(str(DB_PATH))
    collections = [f"Collection {i}" for i in range(N_COLLECTIONS)]

    t0 = time.perf_counter()
    for i in range(N_TEXT):
        clip = Clip(
            content_hash=models.content_hash(f"text clip body number {i}"),
            content_type=models.CONTENT_TEXT,
            content=f"text clip body number {i}" * 5,
            preview=f"text clip body number {i}",
            classification=models.CLASS_PLAIN,
            is_pinned=(i < N_FAVORITES),
            collection=collections[i % N_COLLECTIONS] if i % 3 == 0 else None,
        )
        storage.add_clip(clip)
    for g in range(N_TEXT_DUP_GROUPS):
        body = f"repeated text clip body group {g}" * 5
        for _ in range(3):
            clip = Clip(
                content_hash=models.content_hash(body),
                content_type=models.CONTENT_TEXT,
                content=body,
                preview=body[:40],
                classification=models.CLASS_PLAIN,
            )
            storage.add_clip(clip)
    print(f"  text clips (incl. {N_TEXT_DUP_GROUPS} repeated-text groups) "
          f"inserted in {time.perf_counter()-t0:.2f}s")

    t0 = time.perf_counter()
    dup_group_clip_ids = []
    for i in range(N_IMAGES_UNIQUE):
        data = _png((i % 255, 40, 80))
        _add_image_clip(storage, data=data, width=1920, height=1080)
    for g in range(N_DUP_GROUPS):
        data = _png((10, (g * 3) % 255, (g * 7) % 255))
        group_ids = []
        for copy_i in range(DUP_GROUP_SIZE):
            is_fav = copy_i == 0 and g % 5 == 0
            clip = _add_image_clip(storage, data=data, width=1920, height=1080, is_pinned=is_fav)
            group_ids.append(clip.id)
        dup_group_clip_ids.append(group_ids)
    for i in range(N_TINY):
        data = _png((200, 30, i % 255), size=(8, 8))
        _add_image_clip(storage, data=data, width=8, height=8)
    missing_clip_ids = []
    for i in range(N_MISSING):
        data = _png((5, 5, i), size=(640, 480))
        clip = _add_image_clip(storage, data=data, width=640, height=480)
        missing_clip_ids.append(clip.id)
    n_images_total = N_IMAGES_UNIQUE + N_DUP_GROUPS * DUP_GROUP_SIZE + N_TINY + N_MISSING
    print(f"  {n_images_total} image clips + assets inserted in {time.perf_counter()-t0:.2f}s "
          f"({N_DUP_GROUPS} duplicate groups x{DUP_GROUP_SIZE} = "
          f"{N_DUP_GROUPS * DUP_GROUP_SIZE} duplicate-screenshot clips)")

    # Delete the on-disk bytes for N_MISSING assets to exercise the
    # missing-asset detector without touching the DB rows.
    base = image_assets.assets_dir()
    for cid in missing_clip_ids:
        row = storage.conn.execute(
            "SELECT storage_name FROM clip_assets WHERE clip_id = ?", (cid,)
        ).fetchone()
        (base / row["storage_name"]).unlink()

    t0 = time.perf_counter()
    for i in range(N_REMOVED):
        clip = Clip(
            content_hash=models.content_hash(f"pre-existing removed clip {i}"),
            content_type=models.CONTENT_TEXT,
            content=f"pre-existing removed clip {i}",
            preview=f"pre-existing removed clip {i}",
        )
        storage.add_clip(clip)
        storage.soft_delete(clip.id)
    print(f"  {N_REMOVED} pre-existing Recently Removed clips inserted in "
          f"{time.perf_counter()-t0:.2f}s")

    storage.close()
    print("Fixture build complete.\n")
    return dup_group_clip_ids, missing_clip_ids


def timed_scan(label, storage, *, rehash_counter):
    with QueryCounter(storage.conn) as qc:
        start = time.perf_counter()
        result = cs.run_scan(storage)
        elapsed = time.perf_counter() - start
    print(f"{label:<55} {elapsed*1000:8.2f} ms   {qc.count:5d} SQL   "
          f"{rehash_counter['count']:3d} full-file rehashes")
    return result


def main():
    dup_group_clip_ids, missing_clip_ids = build_fixture()

    storage = VaultStorage(str(DB_PATH))
    events = EventLog(storage)

    # Wrap bytes_hash so we can prove the scan never rehashes file bytes --
    # only the mutation/receipt path and explicit deep_validate_asset should
    # ever call it, never the read-only detectors.
    rehash_counter = {"count": 0}
    _real_bytes_hash = models.bytes_hash

    def _counting_bytes_hash(data: bytes) -> str:
        rehash_counter["count"] += 1
        return _real_bytes_hash(data)

    models.bytes_hash = _counting_bytes_hash
    try:
        print("=" * 100)
        print("SCAN PERFORMANCE")
        print("=" * 100)

        rehash_counter["count"] = 0
        result1 = timed_scan("Initial scan (cold, no prior decisions)", storage, rehash_counter=rehash_counter)
        initial_rehashes = rehash_counter["count"]

        rehash_counter["count"] = 0
        result2 = timed_scan("Repeat scan (no changes, same vault)", storage, rehash_counter=rehash_counter)
        repeat_rehashes = rehash_counter["count"]
    finally:
        models.bytes_hash = _real_bytes_hash

    assert initial_rehashes == 0, f"initial scan rehashed {initial_rehashes} files -- expected 0"
    assert repeat_rehashes == 0, f"repeat scan rehashed {repeat_rehashes} files -- expected 0"
    print("PASS: zero full-file rehashes in either scan (duplicate detection reuses stored SHA-256).")

    assert len(result1.duplicate_screenshot_groups) == N_DUP_GROUPS, (
        f"expected {N_DUP_GROUPS} duplicate-screenshot groups, got "
        f"{len(result1.duplicate_screenshot_groups)}"
    )
    assert len(result1.repeated_text_groups) == N_TEXT_DUP_GROUPS
    assert len(result1.tiny_images) == N_TINY
    assert len(result1.missing_or_damaged) == N_MISSING
    print(f"PASS: detector counts match fixture -- "
          f"{len(result1.duplicate_screenshot_groups)} duplicate-screenshot groups, "
          f"{len(result1.repeated_text_groups)} repeated-text groups, "
          f"{len(result1.tiny_images)} tiny images, "
          f"{len(result1.missing_or_damaged)} missing/damaged assets, "
          f"{len(result1.largest_assets)} largest-assets entries shown.")
    print(f"Redundant bytes identified: {cs.format_bytes(result1.redundant_bytes_identified)}\n")

    # --- decision persistence across rescans ------------------------------------
    print("=" * 100)
    print("DECISION PERSISTENCE ACROSS RESCANS")
    print("=" * 100)
    target_group = result1.duplicate_screenshot_groups[0]
    record_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=target_group.fingerprint, decision=DECISION_IGNORED, rule_version=cs.RULE_VERSION,
    )
    suppressed = is_suppressed(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=target_group.fingerprint,
    )
    assert suppressed is True
    print(f"PASS: group {target_group.fingerprint[:12]}... suppressed after 'Ignore', as expected.")

    # Add a 4th identical copy -> membership changes -> fingerprint changes ->
    # the ignore on the OLD fingerprint must no longer apply to the new group.
    same_hash_row = storage.conn.execute(
        "SELECT sha256, storage_name FROM clip_assets WHERE clip_id = ?",
        (target_group.items[0].clip.id,),
    ).fetchone()
    data = (image_assets.assets_dir() / same_hash_row["storage_name"]).read_bytes()
    _add_image_clip(storage, data=data, width=1920, height=1080)

    result3 = cs.run_scan(storage)
    changed_group = next(
        g for g in result3.duplicate_screenshot_groups if g.evidence["sha256"] == same_hash_row["sha256"]
    )
    assert changed_group.fingerprint != target_group.fingerprint, (
        "fingerprint must change when group membership changes"
    )
    still_suppressed = is_suppressed(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=changed_group.fingerprint,
    )
    assert still_suppressed is False, "a changed group must NOT inherit the old fingerprint's suppression"
    print("PASS: adding a 4th copy changes the group fingerprint; the new group is "
          "NOT suppressed by the old 'Ignore' decision (self-invalidating fingerprint, as designed).\n")

    # --- mutation + receipt ------------------------------------------------------
    print("=" * 100)
    print("MUTATION + RECEIPT")
    print("=" * 100)
    victim_group = result1.duplicate_screenshot_groups[1]
    to_move = victim_group.preselectable_ids
    assert to_move, "fixture group must have at least one preselectable (non-keeper, non-protected) item"
    selection = CleanupSelection(
        category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=victim_group.fingerprint, clip_ids=to_move,
    )
    apply_result = apply_cleanup_selection(
        storage, events, selections=[selection], rule_version=cs.RULE_VERSION,
    )
    assert apply_result.moved_count == len(to_move)
    assert apply_result.receipt_path is not None
    receipt_path = Path(apply_result.receipt_path)
    assert receipt_path.is_file(), f"receipt file not found at {receipt_path}"
    import json
    receipt_body = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt_body["permanent_deletions"] == 0
    assert receipt_body["disk_bytes_reclaimed"] == 0
    assert receipt_body["destination"] == "recently_removed"
    assert receipt_body["restoration_possible"] is True
    print(f"PASS: moved {apply_result.moved_count} clip(s) to Recently Removed.")
    print(f"PASS: receipt written at {receipt_path.name}")
    print(f"      permanent_deletions={receipt_body['permanent_deletions']}, "
          f"disk_bytes_reclaimed={receipt_body['disk_bytes_reclaimed']}, "
          f"destination={receipt_body['destination']!r}, "
          f"restoration_possible={receipt_body['restoration_possible']}")

    moved_id = apply_result.moved_clip_ids[0]
    row = storage.conn.execute("SELECT deleted_at FROM clips WHERE id = ?", (moved_id,)).fetchone()
    assert row["deleted_at"] is not None
    asset_path = image_assets.assets_dir() / storage.conn.execute(
        "SELECT storage_name FROM clip_assets WHERE clip_id = ?", (moved_id,)
    ).fetchone()["storage_name"]
    assert asset_path.is_file(), "soft_delete must not touch the asset file on disk"
    print("PASS: soft-delete is DB-only -- the asset file is still present on disk after the move.\n")

    # --- restore proof -------------------------------------------------------
    print("=" * 100)
    print("RESTORE / UNDO PROOF")
    print("=" * 100)
    storage.restore(moved_id)
    row = storage.conn.execute("SELECT deleted_at FROM clips WHERE id = ?", (moved_id,)).fetchone()
    assert row["deleted_at"] is None
    result4 = cs.run_scan(storage)
    live_ids_after_restore = {
        it.clip.id for g in result4.duplicate_screenshot_groups for it in g.items
    }
    assert moved_id in live_ids_after_restore, "restored clip must reappear as a live scan candidate"
    print(f"PASS: restore({moved_id[:12]}...) cleared deleted_at; clip reappears in a fresh scan's "
          f"live population.\n")

    storage.close()
    print("=" * 100)
    print("ALL STAGE E ASSERTIONS PASSED")
    print("=" * 100)


if __name__ == "__main__":
    main()
