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
from datetime import timedelta
from pathlib import Path

from . import models
from .models import Clip


# --- Filter names (shared with the UI sidebar) -----------------------------
FILTER_ALL = "all"
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
FILTER_EXPIRED = "expired"
# Favorites are stored in the existing ``is_pinned`` column (saved clips that
# float to the top and survive pruning). FILTER_PINNED stays as a back-compat
# alias for the same underlying flag.
FILTER_FAVORITES = "favorites"
FILTER_RECENTLY_REMOVED = "recently_removed"
# Sidebar collection entries use this prefix, e.g. "col:Work".
COLLECTION_PREFIX = "col:"

_CLASS_BY_FILTER = {
    FILTER_LINKS: models.CLASS_LINK,
    FILTER_FILES: models.CLASS_PATH,
    FILTER_CODE: models.CLASS_CODE,
    FILTER_COMMANDS: models.CLASS_COMMAND,
    FILTER_EMAILS: models.CLASS_EMAIL,
    FILTER_PHONES: models.CLASS_PHONE,
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
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

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

    def close(self) -> None:
        self.conn.close()

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
        )

    # --- writes ------------------------------------------------------------
    def add_clip(self, clip: Clip) -> Clip:
        """Insert a clip. Collapses a *consecutive* identical capture by
        linking it to the previous one via ``duplicate_of`` rather than
        spamming the list with a fresh row."""
        prev = self.latest_clip()
        if prev is not None and prev.content_hash == clip.content_hash:
            clip.duplicate_of = prev.id
        self.conn.execute(
            """INSERT INTO clips (
                id, created_at, updated_at, content_hash, content_type,
                content, preview, source_app, source_window, classification,
                tags, is_pinned, is_kept, is_sensitive, expires_at,
                deleted_at, duplicate_of, collection
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                clip.id, clip.created_at, clip.updated_at, clip.content_hash,
                clip.content_type, clip.content, clip.preview, clip.source_app,
                clip.source_window, clip.classification, json.dumps(clip.tags),
                int(clip.is_pinned), int(clip.is_kept), int(clip.is_sensitive),
                clip.expires_at, clip.deleted_at, clip.duplicate_of, clip.collection,
            ),
        )
        self.conn.commit()
        return clip

    def get_clip(self, clip_id: str) -> Clip | None:
        row = self.conn.execute(
            "SELECT * FROM clips WHERE id = ?", (clip_id,)
        ).fetchone()
        return self._row_to_clip(row) if row else None

    def latest_clip(self) -> Clip | None:
        row = self.conn.execute(
            "SELECT * FROM clips WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return self._row_to_clip(row) if row else None

    def _touch(self, clip_id: str) -> None:
        self.conn.execute(
            "UPDATE clips SET updated_at = ? WHERE id = ?",
            (models.now_iso(), clip_id),
        )

    def set_pinned(self, clip_id: str, pinned: bool) -> None:
        self.conn.execute(
            "UPDATE clips SET is_pinned = ? WHERE id = ?",
            (int(pinned), clip_id),
        )
        self._touch(clip_id)
        self.conn.commit()

    def set_kept(self, clip_id: str, kept: bool) -> None:
        self.conn.execute(
            "UPDATE clips SET is_kept = ? WHERE id = ?", (int(kept), clip_id)
        )
        self._touch(clip_id)
        self.conn.commit()

    def set_expiry(self, clip_id: str, expires_at: str | None) -> None:
        self.conn.execute(
            "UPDATE clips SET expires_at = ? WHERE id = ?", (expires_at, clip_id)
        )
        self._touch(clip_id)
        self.conn.commit()

    def set_collection(self, clip_id: str, collection: str | None) -> None:
        name = (collection or "").strip() or None
        self.conn.execute(
            "UPDATE clips SET collection = ? WHERE id = ?", (name, clip_id)
        )
        self._touch(clip_id)
        self.conn.commit()

    def soft_delete(self, clip_id: str) -> None:
        self.conn.execute(
            "UPDATE clips SET deleted_at = ? WHERE id = ?",
            (models.now_iso(), clip_id),
        )
        self.conn.commit()

    def restore(self, clip_id: str) -> None:
        """Bring a soft-deleted clip back into history."""
        self.conn.execute(
            "UPDATE clips SET deleted_at = NULL WHERE id = ?", (clip_id,)
        )
        self._touch(clip_id)
        self.conn.commit()

    def hard_delete(self, clip_id: str) -> None:
        self.conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        self.conn.commit()

    def list_collections(self) -> list[dict]:
        """Distinct collection names (live clips) with their counts."""
        rows = self.conn.execute(
            "SELECT collection AS name, COUNT(*) AS n FROM clips "
            "WHERE deleted_at IS NULL AND collection IS NOT NULL "
            "AND collection <> '' GROUP BY collection ORDER BY collection COLLATE NOCASE"
        ).fetchall()
        return [{"name": r["name"], "count": r["n"]} for r in rows]

    def scrub_and_expire(self, clip_id: str) -> None:
        """Remove a clip's secret content and mark it expired.

        Used for sensitive auto-expiry: the row survives for the Expired view
        and the event log, but the secret is gone.
        """
        now = models.now_iso()
        self.conn.execute(
            "UPDATE clips SET content = '', preview = '(expired)', "
            "deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, clip_id),
        )
        self.conn.commit()

    def expire_due(self, now_iso: str | None = None) -> list[str]:
        """Scrub every clip whose ``expires_at`` has passed. Returns ids."""
        now_iso = now_iso or models.now_iso()
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
        """Immediately scrub/expire all live sensitive clips. Returns ids."""
        rows = self.conn.execute(
            "SELECT id FROM clips WHERE is_sensitive = 1 AND deleted_at IS NULL"
        ).fetchall()
        ids = [r["id"] for r in rows]
        for cid in ids:
            self.scrub_and_expire(cid)
        return ids

    # --- reads / queries ---------------------------------------------------
    def list_clips(self, query=None) -> list[Clip]:
        """Return clips matching a :class:`~cache_vault.core.search.SearchQuery`.

        ``query`` may be ``None`` (everything live), a ``SearchQuery``, or a
        filter-name string for convenience.
        """
        from .search import SearchQuery  # local import avoids a cycle

        if query is None:
            query = SearchQuery()
        elif isinstance(query, str):
            query = SearchQuery(filter_name=query)

        where: list[str] = []
        params: list = []

        fn = query.filter_name
        if fn == FILTER_EXPIRED:
            where.append("deleted_at IS NOT NULL AND expires_at IS NOT NULL")
        elif fn == FILTER_RECENTLY_REMOVED:
            # User-removed clips (restorable, content intact) — not auto-expired.
            where.append("deleted_at IS NOT NULL AND expires_at IS NULL")
        else:
            where.append("deleted_at IS NULL")

        if fn in (FILTER_PINNED, FILTER_FAVORITES):
            where.append("is_pinned = 1")
        elif fn == FILTER_SENSITIVE:
            where.append("is_sensitive = 1")
        elif fn == FILTER_DUPLICATES:
            where.append("duplicate_of IS NOT NULL")
        elif fn in _CLASS_BY_FILTER:
            where.append("classification = ?")
            params.append(_CLASS_BY_FILTER[fn])
        elif fn == FILTER_TODAY:
            where.append("created_at >= ?")
            params.append(_start_of_today_iso())
        elif fn == FILTER_WEEK:
            where.append("created_at >= ?")
            params.append(_start_of_week_iso())
        elif fn.startswith(COLLECTION_PREFIX):
            where.append("collection = ?")
            params.append(fn[len(COLLECTION_PREFIX):])

        # Structured search tokens (type:, source:, sensitive:, pinned:).
        if query.type_filter:
            where.append("classification = ?")
            params.append(query.type_filter)
        if query.source:
            where.append("LOWER(source_app) LIKE ?")
            params.append(f"%{query.source.lower()}%")
        if query.sensitive is not None:
            where.append("is_sensitive = ?")
            params.append(int(query.sensitive))
        if query.pinned is not None:
            where.append("is_pinned = ?")
            params.append(int(query.pinned))

        # Free-text search across content + preview + source.
        if query.text:
            where.append(
                "(LOWER(content) LIKE ? OR LOWER(preview) LIKE ? "
                "OR LOWER(source_window) LIKE ?)"
            )
            like = f"%{query.text.lower()}%"
            params.extend([like, like, like])

        sql = "SELECT * FROM clips WHERE " + " AND ".join(where)
        sql += " ORDER BY is_pinned DESC, created_at DESC, rowid DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_clip(r) for r in rows]

    def counts(self) -> dict[str, int]:
        """Count of live clips per sidebar filter (for the badges)."""
        out: dict[str, int] = {}
        c = self.conn
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
        out[FILTER_DUPLICATES] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
            "AND duplicate_of IS NOT NULL"
        ).fetchone()[0]
        out[FILTER_TODAY] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND created_at >= ?",
            (_start_of_today_iso(),),
        ).fetchone()[0]
        out[FILTER_WEEK] = c.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL AND created_at >= ?",
            (_start_of_week_iso(),),
        ).fetchone()[0]
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
