"""SQLite repository for clips and the event log.

The MVP stores clip ``content`` as plain text in a local database under
``%LOCALAPPDATA%\\CacheVault``. The schema keeps a dedicated ``content``
column so a future release can transparently wrap it in encryption without a
migration headache. Sensitive clips store a *masked* preview, never the secret
itself, so the list view cannot leak.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from . import models
from .models import Clip


# --- Filter names (shared with the UI sidebar) -----------------------------
FILTER_ALL = "all"
FILTER_HOME = "home"
FILTER_PINNED = "pinned"
FILTER_LINKS = "links"
FILTER_FILES = "files"
FILTER_CODE = "code"
FILTER_COMMANDS = "commands"
FILTER_EMAILS = "emails"
FILTER_PHONES = "phones"
FILTER_SENSITIVE = "sensitive"
FILTER_DUPLICATES = "duplicates"
FILTER_TODAY = "today"
FILTER_WEEK = "week"
FILTER_OLDER = "older"
FILTER_EXPIRED = "expired"
# Favorites are stored in the existing ``is_pinned`` column (saved clips that
# float to the top and survive pruning). FILTER_PINNED stays as a back-compat
# alias for the same underlying flag.
FILTER_FAVORITES = "favorites"
FILTER_RECENTLY_REMOVED = "recently_removed"
# Search box with text: live clips + Recently Removed (not Expired).
FILTER_SEARCH_ALL = "search_all"
FILTER_SCREENSHOTS = "screenshots"
# Sidebar collection entries use this prefix, e.g. "col:Work".
COLLECTION_PREFIX = "col:"
import weakref

_OPEN_STORAGES: weakref.WeakSet[VaultStorage] = weakref.WeakSet()
# Sidebar Safe entries use this prefix, e.g. "safe:default".
SAFE_PREFIX = "safe:"
# Smart folder sidebar entries, e.g. "smart:recent".
SMART_PREFIX = "smart:"

_CLASS_BY_FILTER = {
    FILTER_LINKS: models.CLASS_LINK,
    FILTER_FILES: models.CLASS_PATH,
    FILTER_CODE: models.CLASS_CODE,
    FILTER_COMMANDS: models.CLASS_COMMAND,
    FILTER_EMAILS: models.CLASS_EMAIL,
    FILTER_PHONES: models.CLASS_PHONE,
    FILTER_SCREENSHOTS: models.CLASS_IMAGE,
}


def default_db_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "cache_vault.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    content_hash  TEXT,
    content_type  TEXT,
    content       TEXT,
    preview       TEXT,
    source_app    TEXT,
    source_window TEXT,
    classification TEXT,
    tags          TEXT,
    is_pinned     INTEGER DEFAULT 0,
    is_kept       INTEGER DEFAULT 0,
    is_sensitive  INTEGER DEFAULT 0,
    expires_at    TEXT,
    deleted_at    TEXT,
    duplicate_of  TEXT,
    collection    TEXT
);
CREATE INDEX IF NOT EXISTS idx_clips_created ON clips(created_at);
CREATE INDEX IF NOT EXISTS idx_clips_hash ON clips(content_hash);

CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    clip_id     TEXT,
    details     TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_clip ON events(clip_id);

CREATE TABLE IF NOT EXISTS clip_assets (
    asset_id      TEXT PRIMARY KEY,
    clip_id       TEXT NOT NULL UNIQUE,
    mime_type     TEXT NOT NULL,
    file_ext      TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    sha256        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    original_name TEXT,
    storage_name  TEXT NOT NULL,
    width         INTEGER,
    height        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_clip_assets_clip ON clip_assets(clip_id);

CREATE TABLE IF NOT EXISTS clip_cleanup_decisions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category       TEXT NOT NULL,
    scope          TEXT NOT NULL,
    fingerprint    TEXT NOT NULL,
    clip_id        TEXT NOT NULL DEFAULT '',
    decision       TEXT NOT NULL,
    rule_version   INTEGER NOT NULL,
    decided_at     TEXT NOT NULL,
    scan_generation TEXT,
    UNIQUE(category, scope, fingerprint, clip_id)
);
CREATE INDEX IF NOT EXISTS idx_cleanup_decisions_lookup
    ON clip_cleanup_decisions(category, scope, fingerprint);
"""


class VaultStorage:
    """Owns the SQLite connection and all clip persistence."""

    def __init__(self, db_path: str | os.PathLike | None = None):
        if db_path is None:
            db_path = default_db_path()
        self.db_path = Path(db_path)
        # ``:memory:`` is honoured for tests.
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._lock:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.executescript(_SCHEMA)
            self._migrate()
            self.conn.commit()
            self._closed = False
            _OPEN_STORAGES.add(self)

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        with getattr(self, "_lock", threading.RLock()):
            if getattr(self, "_closed", False):
                return
            self._closed = True
            try:
                if hasattr(self, "conn") and self.conn:
                    if str(self.db_path) != ":memory:":
                        try:
                            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        except Exception:
                            pass
                    self.conn.close()
            except Exception:
                pass

    @classmethod
    def close_all_open_storages(cls) -> int:
        count = 0
        storages = list(_OPEN_STORAGES)
        for s in storages:
            try:
                if not getattr(s, "_closed", False):
                    s.close()
                    count += 1
            except Exception:
                pass
        return count

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # Columns we expect on the clips table, with safe defaults. Used to bring
    # an older database forward without wiping or recreating it.
    _EXPECTED_CLIP_COLUMNS = {
        "content_type": "TEXT",
        "preview": "TEXT",
        "source_app": "TEXT",
        "source_window": "TEXT",
        "classification": "TEXT",
        "tags": "TEXT",
        "is_pinned": "INTEGER DEFAULT 0",
        "is_kept": "INTEGER DEFAULT 0",
        "is_sensitive": "INTEGER DEFAULT 0",
        "expires_at": "TEXT",
        "deleted_at": "TEXT",
        "duplicate_of": "TEXT",
        "collection": "TEXT",
        "title": "TEXT",
        "source_url": "TEXT",
        "normalized_hash": "TEXT",
        "size_bytes": "INTEGER DEFAULT 0",
        "last_used_at": "TEXT",
        "use_count": "INTEGER DEFAULT 0",
        "copied_count": "INTEGER DEFAULT 0",
        "safe_id": "TEXT DEFAULT 'default'",
        "safe_name": "TEXT DEFAULT 'Default Safe'",
        "capture_mode": "TEXT DEFAULT 'auto'",
        "is_saved_to_phone": "INTEGER DEFAULT 0",
    }

    def _migrate(self) -> None:
        """Add any missing columns to an existing clips table in place.

        Existing user history is never dropped or reset — we only ADD columns
        with safe defaults so older databases keep loading.
        """
        existing = {row["name"] for row in
                    self.conn.execute("PRAGMA table_info(clips)").fetchall()}
        if not existing:
            return  # table was just created by the schema script
        for col, decl in self._EXPECTED_CLIP_COLUMNS.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE clips ADD COLUMN {col} {decl}")
        # Backfill legacy rows with safe defaults.
        self.conn.execute(
            "UPDATE clips SET last_used_at = updated_at "
            "WHERE last_used_at IS NULL OR last_used_at = ''"
        )
        self.conn.execute(
            "UPDATE clips SET use_count = 1 "
            "WHERE (use_count IS NULL OR use_count = 0) AND deleted_at IS NULL"
        )
        self.conn.execute(
            "UPDATE clips SET safe_id = 'default', safe_name = 'Default Safe' "
            "WHERE safe_id IS NULL OR safe_id = ''"
        )
        self.conn.execute(
            "UPDATE clips SET capture_mode = 'auto' "
            "WHERE capture_mode IS NULL OR capture_mode = ''"
        )
        from .editable_copies import EditableCopyStore
        EditableCopyStore(self.conn).ensure_schema()

    @contextmanager
    def reader_connection(self):
        """A short-lived, read-only connection for use off the main thread.

        ``self.conn`` is shared with the UI/main thread (writes, event
        recording); handing it to a background refresh worker would mean
        two threads issuing statements on the same connection concurrently.
        WAL mode (enabled in ``__init__``) lets a second, read-only
        connection read the database concurrently with the writer without
        blocking either side, so background snapshot reads always go
        through this instead of ``self.conn``.

        ``:memory:`` databases (tests) can't be reopened by a second
        connection -- each one is a distinct, empty database -- so callers
        get the shared connection back in that case. Tests using this are
        expected to be single-threaded.
        """
        if str(self.db_path) == ":memory:":
            yield self.conn
            return
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def clip_id_snapshot(self, query=None, *, batch_size: int = 500):
        """One read-transaction snapshot pairing an authoritative count
        with deduplicated, batched id enumeration -- both computed
        against the exact same view of the table, so a concurrent
        insert/delete between count and iteration (or between batches)
        cannot change what this snapshot sees. LIMIT/OFFSET paging alone,
        across independently-executed statements, can otherwise skip or
        duplicate rows if the matching set changes mid-enumeration; a
        single BEGIN/ROLLBACK-bracketed transaction on one connection
        eliminates that rather than trying to defend against it after
        the fact.

        Yields ``(count, batches)`` where ``batches`` is a generator of
        id-list batches; both must be consumed inside the ``with`` block
        -- the transaction (and, for a real on-disk db, the dedicated
        reader connection) closes when the block exits.

        Mirrors the existing dedicated-transaction pattern in
        ``ui/shell.py``'s ``_collect_refresh_snapshot`` (pairing
        ``list_clips``+``count_clips`` the same way): the ``:memory:``
        fallback (tests) hands back the shared ``self.conn`` with no
        explicit transaction, accepting the same "tiny consistency
        window" that pattern already accepts for the same reason --
        starting a real transaction on a connection also used
        synchronously elsewhere in a single-threaded test isn't needed
        for correctness there.
        """
        with self.reader_connection() as reader:
            dedicated = reader is not self.conn
            if dedicated:
                reader.execute("BEGIN")
            try:
                count = self.count_clips(query, conn=reader)

                def _batches():
                    offset = 0
                    while True:
                        batch = self.list_clip_ids(
                            query, limit=batch_size, offset=offset, conn=reader,
                        )
                        if not batch:
                            return
                        yield batch
                        if len(batch) < batch_size:
                            return
                        offset += batch_size

                yield count, _batches()
            finally:
                if dedicated:
                    reader.execute("ROLLBACK")

    # --- row <-> Clip ------------------------------------------------------
    @staticmethod
    def _row_to_clip(row: sqlite3.Row) -> Clip:
        return Clip(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            content_hash=row["content_hash"] or "",
            content_type=row["content_type"] or models.CONTENT_TEXT,
            content=row["content"] or "",
            preview=row["preview"] or "",
            source_app=row["source_app"],
            source_window=row["source_window"],
            classification=row["classification"] or models.CLASS_PLAIN,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            is_pinned=bool(row["is_pinned"]),
            is_kept=bool(row["is_kept"]),
            is_sensitive=bool(row["is_sensitive"]),
            expires_at=row["expires_at"],
            deleted_at=row["deleted_at"],
            duplicate_of=row["duplicate_of"],
            collection=row["collection"] if "collection" in row.keys() else None,
            title=row["title"] if "title" in row.keys() else None,
            source_url=row["source_url"] if "source_url" in row.keys() else None,
            normalized_hash=row["normalized_hash"] if "normalized_hash" in row.keys() else None,
            size_bytes=int(row["size_bytes"] or 0) if "size_bytes" in row.keys() else 0,
            last_used_at=row["last_used_at"] if "last_used_at" in row.keys() else None,
            use_count=int(row["use_count"] or 0) if "use_count" in row.keys() else 0,
            copied_count=int(row["copied_count"] or 0) if "copied_count" in row.keys() else 0,
            safe_id=row["safe_id"] if "safe_id" in row.keys() and row["safe_id"] else "default",
            safe_name=row["safe_name"] if "safe_name" in row.keys() and row["safe_name"] else "Default Safe",
            capture_mode=row["capture_mode"] if "capture_mode" in row.keys() and row["capture_mode"] else models.CAPTURE_AUTO,
            is_saved_to_phone=bool(row["is_saved_to_phone"]) if "is_saved_to_phone" in row.keys() else False,
        )

    # --- writes ------------------------------------------------------------
    def add_clip(self, clip: Clip) -> Clip:
        """Insert a clip. Collapses a *consecutive* identical capture by
        linking it to the previous one via ``duplicate_of`` rather than
        spamming the list with a fresh row."""
        with self._lock:
            prev = self.latest_clip()
            if prev is not None and prev.content_hash == clip.content_hash:
                clip.duplicate_of = prev.id
            self.conn.execute(
                """INSERT INTO clips (
                    id, created_at, updated_at, content_hash, content_type,
                    content, preview, source_app, source_window, classification,
                    tags, is_pinned, is_kept, is_sensitive, expires_at,
                    deleted_at, duplicate_of, collection, title, source_url,
                    normalized_hash, size_bytes, last_used_at, use_count, copied_count,
                    safe_id, safe_name, capture_mode, is_saved_to_phone
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    clip.id, clip.created_at, clip.updated_at, clip.content_hash,
                    clip.content_type, clip.content, clip.preview, clip.source_app,
                    clip.source_window, clip.classification, json.dumps(clip.tags),
                    int(clip.is_pinned), int(clip.is_kept), int(clip.is_sensitive),
                    clip.expires_at, clip.deleted_at, clip.duplicate_of, clip.collection,
                    clip.title, clip.source_url, clip.normalized_hash, clip.size_bytes,
                    clip.last_used_at or clip.created_at,
                    max(clip.use_count, 1), clip.copied_count,
                    clip.safe_id or "default",
                    clip.safe_name or "Default Safe",
                    clip.capture_mode or models.CAPTURE_AUTO,
                    int(clip.is_saved_to_phone),
                ),
            )
            self.conn.commit()
            return clip

    def get_clip(self, clip_id: str) -> Clip | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM clips WHERE id = ?", (clip_id,)
            ).fetchone()
            return self._row_to_clip(row) if row else None

    def latest_clip(self) -> Clip | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM clips WHERE deleted_at IS NULL "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            return self._row_to_clip(row) if row else None

    def _touch(self, clip_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET updated_at = ? WHERE id = ?",
                (models.now_iso(), clip_id),
            )

    def touch_clip(self, clip_id: str) -> None:
        """Record that a clip was used (updates last_used_at and use_count)."""
        now = models.now_iso()
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET updated_at = ?, last_used_at = ?, "
                "use_count = COALESCE(use_count, 0) + 1, "
                "copied_count = COALESCE(copied_count, 0) + 1 "
                "WHERE id = ?",
                (now, now, clip_id),
            )
            self.conn.commit()

    def set_pinned(self, clip_id: str, pinned: bool) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET is_pinned = ? WHERE id = ?",
                (int(pinned), clip_id),
            )
            self._touch(clip_id)
            self.conn.commit()

    def set_kept(self, clip_id: str, kept: bool) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET is_kept = ? WHERE id = ?", (int(kept), clip_id)
            )
            self._touch(clip_id)
            self.conn.commit()

    def set_expiry(self, clip_id: str, expires_at: str | None) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET expires_at = ? WHERE id = ?", (expires_at, clip_id)
            )
            self._touch(clip_id)
            self.conn.commit()

    def set_collection(self, clip_id: str, collection: str | None) -> None:
        name = (collection or "").strip() or None
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET collection = ? WHERE id = ?", (name, clip_id)
            )
            self._touch(clip_id)
            self.conn.commit()

    def set_safe(
        self, clip_id: str, safe_id: str, safe_name: str, capture_mode: str | None = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET safe_id = ?, safe_name = ?, capture_mode = COALESCE(?, capture_mode) "
                "WHERE id = ?",
                (safe_id, safe_name, capture_mode, clip_id),
            )
            self._touch(clip_id)
            self.conn.commit()

    def list_safes(self) -> list[dict]:
        """Distinct Safe ids (live clips) with counts."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT safe_id AS id, MAX(safe_name) AS name, COUNT(*) AS n FROM clips "
                "WHERE deleted_at IS NULL AND safe_id IS NOT NULL AND safe_id <> '' "
                "AND safe_id <> 'ignore' GROUP BY safe_id ORDER BY name COLLATE NOCASE"
            ).fetchall()
            return [{"id": r["id"], "name": r["name"], "count": r["n"]} for r in rows]

    def count_by_capture_mode(self, capture_mode: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM clips "
                "WHERE deleted_at IS NULL AND capture_mode = ?",
                (capture_mode,),
            ).fetchone()
            return int(row["n"]) if row else 0

    def count_duplicate_groups(self) -> int:
        """Return the count of exact duplicate groups using SQL aggregation."""
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM ("
                "  SELECT content_hash FROM clips "
                "  WHERE deleted_at IS NULL AND content_hash IS NOT NULL AND content_hash != '' "
                "  GROUP BY content_hash HAVING COUNT(*) > 1"
                ")"
            ).fetchone()
            return int(row["n"]) if row else 0


    def list_by_capture_mode(self, capture_mode: str, *, limit: int = 200) -> list[Clip]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM clips WHERE deleted_at IS NULL AND capture_mode = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (capture_mode, limit),
            ).fetchall()
            return [self._row_to_clip(r) for r in rows]

    def soft_delete(self, clip_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET deleted_at = ? WHERE id = ?",
                (models.now_iso(), clip_id),
            )
            self.conn.commit()

    def soft_delete_many(self, clip_ids):
        """Bulk move-to-Recently-Removed."""
        from .selection import BulkMutationResult, dedupe_preserve_order

        ids = dedupe_preserve_order(clip_ids)
        if not ids:
            return BulkMutationResult()
        moved: list[str] = []
        skipped: list[str] = []
        now = models.now_iso()
        with self._lock:
            try:
                for cid in ids:
                    row = self.conn.execute(
                        "SELECT deleted_at FROM clips WHERE id = ?", (cid,)
                    ).fetchone()
                    if row is None or row[0] is not None:
                        skipped.append(cid)
                        continue
                    self.conn.execute("UPDATE clips SET deleted_at = ? WHERE id = ?", (now, cid))
                    moved.append(cid)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            return BulkMutationResult(succeeded=tuple(moved), skipped=tuple(skipped))

    def restore(self, clip_id: str) -> None:
        """Bring a soft-deleted clip back into history."""
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET deleted_at = NULL WHERE id = ?", (clip_id,)
            )
            self._touch(clip_id)
            self.conn.commit()

    def restore_many(self, clip_ids):
        """Bulk restore."""
        from .selection import BulkMutationResult, dedupe_preserve_order

        ids = dedupe_preserve_order(clip_ids)
        if not ids:
            return BulkMutationResult()
        restored: list[str] = []
        skipped: list[str] = []
        with self._lock:
            try:
                for cid in ids:
                    row = self.conn.execute(
                        "SELECT deleted_at FROM clips WHERE id = ?", (cid,)
                    ).fetchone()
                    if row is None or row[0] is None:
                        skipped.append(cid)
                        continue
                    self.conn.execute("UPDATE clips SET deleted_at = NULL WHERE id = ?", (cid,))
                    self._touch(cid)
                    restored.append(cid)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            return BulkMutationResult(succeeded=tuple(restored), skipped=tuple(skipped))

    def clear_collection(self, collection: str, clip_ids: list[str] | None = None):
        """Atomically clear the collection label from every clip currently
        assigned to ``collection``.

        If ``clip_ids`` is provided, the method still validates that each
        id is currently a live member of ``collection`` before clearing it;
        ids that no longer exist or no longer belong to the collection are
        reported in ``.skipped``. This lets callers pass an execution-time
        snapshot of ids while still getting the atomic contract: every
        eligible update is committed together in one transaction, or none
        of them are.

        Only touches ``clips.collection`` -- never ``clip_assets``, external
        files, ``deleted_at``, ``is_pinned``, ``is_kept``, or content fields.
        """
        from .selection import BulkMutationResult, dedupe_preserve_order

        collection = (collection or "").strip()
        if not collection:
            return BulkMutationResult()

        with self._lock:
            if clip_ids is None:
                rows = self.conn.execute(
                    "SELECT id FROM clips WHERE deleted_at IS NULL AND collection = ?",
                    (collection,),
                ).fetchall()
                clip_ids = [r[0] for r in rows]

            ids = dedupe_preserve_order(clip_ids)
            if not ids:
                return BulkMutationResult()

            cleared: list[str] = []
            skipped: list[str] = []
            try:
                for cid in ids:
                    row = self.conn.execute(
                        "SELECT collection, deleted_at FROM clips WHERE id = ?",
                        (cid,),
                    ).fetchone()
                    if row is None or row["deleted_at"] is not None or row["collection"] != collection:
                        skipped.append(cid)
                        continue
                    self.conn.execute(
                        "UPDATE clips SET collection = NULL WHERE id = ?",
                        (cid,),
                    )
                    cleared.append(cid)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            return BulkMutationResult(succeeded=tuple(cleared), skipped=tuple(skipped))

    def hard_delete(self, clip_id: str) -> None:
        from . import image_assets
        with self._lock:
            row = self.get_asset_record(clip_id)
            asset_storage_name = row.storage_name if row is not None else None
            try:
                if row is not None:
                    self.conn.execute("DELETE FROM clip_assets WHERE clip_id = ?", (clip_id,))
                self.conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

            if asset_storage_name is not None:
                try:
                    image_assets.delete_asset_file(asset_storage_name)
                except Exception:
                    pass


    def hard_delete_many(self, clip_ids: list[str]):
        from .selection import BulkMutationResult, dedupe_preserve_order

        ids = dedupe_preserve_order(clip_ids)
        if not ids:
            return BulkMutationResult()

        deleted: list[str] = []
        skipped: list[str] = []
        with self._lock:
            try:
                for cid in ids:
                    row = self.conn.execute(
                        "SELECT deleted_at FROM clips WHERE id = ?", (cid,)
                    ).fetchone()
                    if row is None or row["deleted_at"] is None:
                        skipped.append(cid)
                        continue
                    self.conn.execute("DELETE FROM clip_assets WHERE clip_id = ?", (cid,))
                    self.conn.execute("DELETE FROM clips WHERE id = ?", (cid,))
                    deleted.append(cid)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            return BulkMutationResult(succeeded=tuple(deleted), skipped=tuple(skipped))

    # --- image assets --------------------------------------------------------
    def has_clip_asset(self, clip_id: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM clip_assets WHERE clip_id = ?", (clip_id,)
            ).fetchone()
            return row is not None

    def get_asset_record(self, clip_id: str):
        from .image_assets import ClipAssetRecord
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM clip_assets WHERE clip_id = ?", (clip_id,)
            ).fetchone()
            if row is None:
                return None
            return ClipAssetRecord(
                asset_id=row["asset_id"],
                clip_id=row["clip_id"],
                mime_type=row["mime_type"],
                file_ext=row["file_ext"],
                size_bytes=row["size_bytes"],
                sha256=row["sha256"],
                created_at=row["created_at"],
                original_name=row["original_name"],
                storage_name=row["storage_name"],
                width=row["width"],
                height=row["height"],
            )

    def save_clip_asset(self, record, data: bytes) -> None:
        from . import image_assets
        image_assets.write_asset_file(record.storage_name, data)
        with self._lock:
            self.conn.execute(
                """INSERT INTO clip_assets (
                    asset_id, clip_id, mime_type, file_ext, size_bytes, sha256,
                    created_at, original_name, storage_name, width, height
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.asset_id, record.clip_id, record.mime_type, record.file_ext,
                    record.size_bytes, record.sha256, record.created_at,
                    record.original_name, record.storage_name, record.width, record.height,
                ),
            )
            self.conn.commit()

    def load_clip_asset_bytes(self, clip_id: str) -> tuple[bytes, str] | None:
        from . import image_assets
        with self._lock:
            rec = self.get_asset_record(clip_id)
            if rec is None:
                return None
            data = image_assets.read_asset_file(rec.storage_name)
            if data is None:
                return None
            return data, rec.mime_type

    def list_collections(self) -> list[dict]:
        """Distinct collection names (live clips) with their counts."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT collection AS name, COUNT(*) AS n FROM clips "
                "WHERE deleted_at IS NULL AND collection IS NOT NULL "
                "AND collection <> '' GROUP BY collection ORDER BY collection COLLATE NOCASE"
            ).fetchall()
            return [{"name": r["name"], "count": r["n"]} for r in rows]

    def scrub_and_expire(self, clip_id: str) -> None:
        now = models.now_iso()
        with self._lock:
            self.conn.execute(
                "UPDATE clips SET content = '', preview = '(expired)', "
                "deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, clip_id),
            )
            self.conn.commit()

    def expire_due(self, now_iso: str | None = None) -> list[str]:
        now_iso = now_iso or models.now_iso()
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM clips WHERE expires_at IS NOT NULL "
                "AND expires_at <= ? AND deleted_at IS NULL",
                (now_iso,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            for cid in ids:
                self.scrub_and_expire(cid)
            return ids

    def clear_sensitive(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM clips WHERE is_sensitive = 1 AND deleted_at IS NULL"
            ).fetchall()
            ids = [r["id"] for r in rows]
            for cid in ids:
                self.scrub_and_expire(cid)
            return ids

    def prune_history(self, max_clips: int) -> list[str]:
        if max_clips <= 0:
            return []
        with self._lock:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL"
            ).fetchone()[0]
            overflow = count - max_clips
            if overflow <= 0:
                return []
            rows = self.conn.execute(
                "SELECT id FROM clips WHERE deleted_at IS NULL AND is_pinned = 0 "
                "ORDER BY created_at ASC, rowid ASC LIMIT ?",
                (overflow,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            now = models.now_iso()
            for cid in ids:
                self.conn.execute(
                    "UPDATE clips SET deleted_at = ? WHERE id = ?", (now, cid)
                )
            if ids:
                self.conn.commit()
            return ids

    # --- reads / queries ---------------------------------------------------
    @staticmethod
    def _normalize_query(query):
        from .search import SearchQuery  # local import avoids a cycle

        if query is None:
            return SearchQuery()
        if isinstance(query, str):
            return SearchQuery(filter_name=query)
        return query

    def _build_where(self, query) -> tuple[list[str], list]:
        """Shared WHERE-clause construction for ``list_clips``/``count_clips``.

        Kept as one place so the row query and the count query can never
        drift out of sync with each other.
        """
        where: list[str] = []
        params: list = []

        fn = query.filter_name
        if fn == FILTER_EXPIRED:
            where.append("deleted_at IS NOT NULL AND expires_at IS NOT NULL")
        elif fn == FILTER_RECENTLY_REMOVED:
            # User-removed clips (restorable, content intact) — not auto-expired.
            where.append("deleted_at IS NOT NULL AND expires_at IS NULL")
        elif fn == FILTER_SEARCH_ALL:
            # Global search: live history + Recently Removed (not Expired).
            where.append(
                "(deleted_at IS NULL OR "
                "(deleted_at IS NOT NULL AND expires_at IS NULL))"
            )
        else:
            where.append("deleted_at IS NULL")

        if fn in (FILTER_PINNED, FILTER_FAVORITES):
            where.append("is_pinned = 1")
        elif fn == FILTER_SENSITIVE:
            where.append("is_sensitive = 1")
        elif fn == FILTER_DUPLICATES:
            where.append(
                "content_hash IN (SELECT content_hash FROM clips "
                "WHERE deleted_at IS NULL GROUP BY content_hash HAVING COUNT(*) > 1)"
            )
        elif fn in _CLASS_BY_FILTER:
            where.append("classification = ?")
            params.append(_CLASS_BY_FILTER[fn])
        elif fn == FILTER_TODAY:
            where.append("created_at >= ?")
            params.append(_start_of_today_iso())
        elif fn == FILTER_WEEK:
            where.append("created_at >= ?")
            params.append(_start_of_week_iso())
        elif fn == FILTER_OLDER:
            where.append("created_at < ?")
            params.append(_start_of_week_iso())
        elif fn.startswith(COLLECTION_PREFIX):
            where.append("collection = ?")
            params.append(fn[len(COLLECTION_PREFIX):])
        elif fn.startswith(SAFE_PREFIX):
            where.append("safe_id = ?")
            params.append(fn[len(SAFE_PREFIX):])
        elif fn.startswith(SMART_PREFIX):
            from .smart_folders import apply_smart_folder_filter, folder_id_from_key

            fid = folder_id_from_key(fn)
            if fid:
                apply_smart_folder_filter(fid, where, params)
            else:
                where.append("1 = 0")

        # Structured search tokens (type:, source:, sensitive:, pinned:).
        if query.type_filter:
            where.append("classification = ?")
            params.append(query.type_filter)
        if query.source:
            where.append("LOWER(COALESCE(source_app,'')) LIKE ?")
            params.append(f"%{query.source.lower()}%")
        if query.window:
            where.append("LOWER(COALESCE(source_window,'')) LIKE ?")
            params.append(f"%{query.window.lower()}%")
        if query.source_url:
            where.append("LOWER(COALESCE(source_url,'')) LIKE ?")
            params.append(f"%{query.source_url.lower()}%")
        if query.domain:
            where.append(
                "(LOWER(COALESCE(source_url,'')) LIKE ? "
                "OR LOWER(COALESCE(source_url,'')) LIKE ?)"
            )
            d = query.domain.lower().lstrip("www.")
            params.extend([f"%://{d}%", f"%://www.{d}%"])
        if query.collection:
            where.append("LOWER(COALESCE(collection,'')) LIKE ?")
            params.append(f"%{query.collection.lower()}%")
        if query.sensitive is not None:
            where.append("is_sensitive = ?")
            params.append(int(query.sensitive))
        if query.pinned is not None:
            where.append("is_pinned = ?")
            params.append(int(query.pinned))
        if query.duplicate_only:
            where.append(
                "content_hash IN (SELECT content_hash FROM clips "
                "WHERE deleted_at IS NULL GROUP BY content_hash HAVING COUNT(*) > 1)"
            )

        # Date Added / First Saved
        from .search import preset_bounds  # noqa: PLC0415

        added_start = query.date_added_start
        added_end = query.date_added_end
        if query.date_added_preset:
            ps, pe = preset_bounds(query.date_added_preset)
            added_start = added_start or ps
            added_end = added_end or pe
        if added_start:
            where.append("created_at >= ?")
            params.append(added_start)
        if added_end:
            where.append("created_at < ?")
            params.append(added_end)

        # Date Used / Last Used
        used_start = query.date_used_start
        used_end = query.date_used_end
        if query.date_used_preset:
            ps, pe = preset_bounds(query.date_used_preset)
            used_start = used_start or ps
            used_end = used_end or pe
        if used_start:
            where.append("COALESCE(last_used_at, updated_at) >= ?")
            params.append(used_start)
        if used_end:
            where.append("COALESCE(last_used_at, updated_at) < ?")
            params.append(used_end)

        # Free-text search across content + preview + metadata.
        if query.text:
            where.append(
                "(LOWER(content) LIKE ? OR LOWER(preview) LIKE ? "
                "OR LOWER(COALESCE(source_window,'')) LIKE ? "
                "OR LOWER(COALESCE(title,'')) LIKE ? "
                "OR LOWER(COALESCE(source_url,'')) LIKE ? "
                "OR LOWER(COALESCE(collection,'')) LIKE ? "
                "OR LOWER(COALESCE(source_app,'')) LIKE ? "
                "OR LOWER(classification) LIKE ? "
                "OR content_hash LIKE ?)"
            )
            like = f"%{query.text.lower()}%"
            short = f"{query.text.lower()}%"
            params.extend([like, like, like, like, like, like, like, like, short])

        return where, params

    def list_clips(
        self, query=None, *, limit: int | None = None, offset: int = 0, conn=None,
    ) -> list[Clip]:
        """Return clips matching a :class:`~cache_vault.core.search.SearchQuery`.

        ``query`` may be ``None`` (everything live), a ``SearchQuery``, or a
        filter-name string for convenience.

        ``limit``/``offset`` apply paging in SQL rather than fetching every
        matching row and slicing in Python -- with ~1,700 clips, the old
        fetch-everything behavior meant every refresh materialized the full
        vault into ``Clip`` objects just to keep the first 120. ``limit=None``
        (the default) preserves the original everything-at-once behavior for
        existing callers that rely on it (dashboard widgets, exports, etc.).

        ``conn`` lets a caller supply a different connection (e.g. a
        background-thread read-only connection from ``reader_connection()``)
        instead of the shared ``self.conn``.
        """
        from .search import sort_sql  # noqa: PLC0415

        query = self._normalize_query(query)
        where, params = self._build_where(query)

        sql = "SELECT * FROM clips WHERE " + " AND ".join(where)
        sql += " ORDER BY " + sort_sql(query.sort)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = [*params, limit, offset]
        target_conn = conn or self.conn
        if target_conn is self.conn:
            with self._lock:
                rows = target_conn.execute(sql, params).fetchall()
        else:
            rows = target_conn.execute(sql, params).fetchall()
        return [self._row_to_clip(r) for r in rows]

    def count_clips(self, query=None, conn=None) -> int:
        """Total rows matching ``query``, ignoring any paging -- the pair to
        ``list_clips(..., limit=...)`` for "N clips" / "show M more" UI."""
        query = self._normalize_query(query)
        where, params = self._build_where(query)
        sql = "SELECT COUNT(*) FROM clips WHERE " + " AND ".join(where)
        target_conn = conn or self.conn
        if target_conn is self.conn:
            with self._lock:
                row = target_conn.execute(sql, params).fetchone()
        else:
            row = target_conn.execute(sql, params).fetchone()
        return int(row[0]) if row else 0

    def list_clip_ids(
        self, query=None, *, limit: int | None = None, offset: int = 0, conn=None,
    ) -> list[str]:
        from .search import sort_sql  # noqa: PLC0415

        query = self._normalize_query(query)
        where, params = self._build_where(query)

        sql = "SELECT id FROM clips WHERE " + " AND ".join(where)
        sql += " ORDER BY " + sort_sql(query.sort)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = [*params, limit, offset]
        target_conn = conn or self.conn
        if target_conn is self.conn:
            with self._lock:
                rows = target_conn.execute(sql, params).fetchall()
        else:
            rows = target_conn.execute(sql, params).fetchall()
        return [r[0] for r in rows]

    def iter_clip_ids(self, query=None, *, batch_size: int = 500, conn=None):
        offset = 0
        while True:
            batch = self.list_clip_ids(query, limit=batch_size, offset=offset, conn=conn)
            if not batch:
                return
            yield batch
            if len(batch) < batch_size:
                return
            offset += batch_size

    def count_images(self, conn=None) -> int:
        target_conn = conn or self.conn
        if target_conn is self.conn:
            with self._lock:
                return target_conn.execute(
                    "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
                    "AND (classification = ? OR content_type = ?)",
                    (models.CLASS_IMAGE, models.CONTENT_IMAGE),
                ).fetchone()[0]
        else:
            return target_conn.execute(
                "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
                "AND (classification = ? OR content_type = ?)",
                (models.CLASS_IMAGE, models.CONTENT_IMAGE),
            ).fetchone()[0]

    def asset_storage_ready(self) -> bool:
        """True when the clip_assets table exists (screenshot storage is available)."""
        with self._lock:
            try:
                self.conn.execute("SELECT 1 FROM clip_assets LIMIT 1")
                return True
            except sqlite3.OperationalError:
                return False

    def count_duplicate_groups(self, conn=None) -> int:
        target_conn = conn or self.conn
        sql = (
            "SELECT COUNT(*) FROM ("
            "SELECT content_hash FROM clips WHERE deleted_at IS NULL "
            "GROUP BY content_hash HAVING COUNT(*) > 1)"
        )
        if target_conn is self.conn:
            with self._lock:
                row = target_conn.execute(sql).fetchone()
        else:
            row = target_conn.execute(sql).fetchone()
        return int(row[0]) if row else 0

    def events_for_clip(self, clip_id: str, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE clip_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (clip_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def counts(self, conn=None) -> dict[str, int]:
        """Count of live clips per sidebar filter (for the badges)."""
        target_conn = conn or self.conn
        if target_conn is self.conn:
            with self._lock:
                return self._counts_impl(target_conn)
        else:
            return self._counts_impl(target_conn)

    def _counts_impl(self, c) -> dict[str, int]:
        out: dict[str, int] = {}
        out[FILTER_ALL] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL"
        ).fetchone()[0]
        out[FILTER_PINNED] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND is_pinned = 1"
        ).fetchone()[0]
        out[FILTER_FAVORITES] = out[FILTER_PINNED]
        for fname, cls in _CLASS_BY_FILTER.items():
            out[fname] = c.execute(
                "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
                "AND classification = ?",
                (cls,),
            ).fetchone()[0]
        out[FILTER_SENSITIVE] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND is_sensitive = 1"
        ).fetchone()[0]
        out[FILTER_DUPLICATES] = self.count_duplicate_groups(conn=c)
        out[FILTER_TODAY] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND created_at >= ?",
            (_start_of_today_iso(),),
        ).fetchone()[0]
        out[FILTER_WEEK] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND created_at >= ?",
            (_start_of_week_iso(),),
        ).fetchone()[0]
        out[FILTER_OLDER] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND created_at < ?",
            (_start_of_week_iso(),),
        ).fetchone()[0]
        out[FILTER_SCREENSHOTS] = self.count_images(conn=c)
        out[FILTER_EXPIRED] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NOT NULL "
            "AND expires_at IS NOT NULL"
        ).fetchone()[0]
        out[FILTER_RECENTLY_REMOVED] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NOT NULL "
            "AND expires_at IS NULL"
        ).fetchone()[0]
        return out


def _start_of_today_iso() -> str:
    now = models.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _start_of_week_iso() -> str:
    now = models.utcnow()
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
