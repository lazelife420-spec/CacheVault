"""Editable working copies — originals stay immutable on disk."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import models
from .pathutil import clean_path, is_local_path


@dataclass
class EditableCopyRecord:
    id: str
    clip_id: str
    original_path: str
    copy_path: str
    revision: int
    original_hash: str
    copy_hash: str
    created_at: str
    updated_at: str


def editable_copies_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "CacheVault" / "EditableCopies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def receipts_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(base) / "CacheVault" / "Receipts" / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str, *, max_len: int = 80) -> str:
    stem = Path(name).name
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    if not stem or stem in {".", ".."}:
        stem = "file"
    return stem[:max_len]


def is_local_file_path(text: str) -> bool:
    if not is_local_path(text):
        return False
    return os.path.isfile(clean_path(text))


def file_sha256(path: os.PathLike | str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_dir_for_clip(clip_id: str) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = editable_copies_root() / day / clip_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _revision_name(original_path: str, revision: int) -> str:
    p = Path(clean_path(original_path))
    stem = sanitize_filename(p.stem)
    suffix = p.suffix.lower()
    return f"{stem}.copy.{revision:03d}{suffix}"


def write_file_receipt(action: str, payload: dict) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rid = payload.get("clip_id") or models.new_id()[:8]
    path = receipts_dir() / f"{action}-{rid}-{ts}.json"
    body = {"action": action, **payload}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


class EditableCopyStore:
    """SQLite-backed registry of editable copies."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS editable_copies (
                id            TEXT PRIMARY KEY,
                clip_id       TEXT NOT NULL,
                original_path TEXT NOT NULL,
                copy_path     TEXT NOT NULL,
                revision      INTEGER NOT NULL DEFAULT 1,
                original_hash TEXT,
                copy_hash     TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_editable_copies_clip "
            "ON editable_copies(clip_id)"
        )

    def latest_for_clip(self, clip_id: str) -> EditableCopyRecord | None:
        row = self.conn.execute(
            "SELECT * FROM editable_copies WHERE clip_id = ? "
            "ORDER BY revision DESC, rowid DESC LIMIT 1",
            (clip_id,),
        ).fetchone()
        return _row_to_record(row) if row else None

    def create_copy(self, clip_id: str, original_path: str) -> EditableCopyRecord:
        original_path = clean_path(original_path)
        if not os.path.isfile(original_path):
            raise FileNotFoundError(f"Original file not found: {original_path}")
        original_hash = file_sha256(original_path)
        latest = self.latest_for_clip(clip_id)
        revision = 1 if latest is None else latest.revision + 1
        copy_dir = _copy_dir_for_clip(clip_id)
        name = _revision_name(original_path, revision)
        copy_path = copy_dir / name
        if copy_path.exists():
            raise FileExistsError(str(copy_path))
        shutil.copy2(original_path, copy_path)
        copy_hash = file_sha256(copy_path)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, original_path, str(copy_path), revision,
                original_hash, copy_hash, now, now,
            ),
        )
        self.conn.commit()
        return EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=original_path,
            copy_path=str(copy_path), revision=revision,
            original_hash=original_hash, copy_hash=copy_hash,
            created_at=now, updated_at=now,
        )

    def save_revision(self, clip_id: str) -> EditableCopyRecord | None:
        """Create the next revision from the current editable file if it changed."""
        latest = self.latest_for_clip(clip_id)
        if latest is None or not os.path.isfile(latest.copy_path):
            return None
        current_hash = file_sha256(latest.copy_path)
        if current_hash == latest.copy_hash:
            return None
        revision = latest.revision + 1
        copy_dir = Path(latest.copy_path).parent
        name = _revision_name(latest.original_path, revision)
        copy_path = copy_dir / name
        shutil.copy2(latest.copy_path, copy_path)
        new_hash = file_sha256(copy_path)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, latest.original_path, str(copy_path), revision,
                latest.original_hash, new_hash, now, now,
            ),
        )
        self.conn.commit()
        rec = EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=latest.original_path,
            copy_path=str(copy_path), revision=revision,
            original_hash=latest.original_hash, copy_hash=new_hash,
            created_at=now, updated_at=now,
        )
        rec._previous_hash = latest.copy_hash  # type: ignore[attr-defined]
        return rec

    def delete_copy_record(self, copy_id: str) -> EditableCopyRecord | None:
        row = self.conn.execute(
            "SELECT * FROM editable_copies WHERE id = ?", (copy_id,),
        ).fetchone()
        if not row:
            return None
        rec = _row_to_record(row)
        copy_path = Path(rec.copy_path)
        if copy_path.is_file():
            copy_path.unlink()
        self.conn.execute("DELETE FROM editable_copies WHERE id = ?", (copy_id,))
        self.conn.commit()
        return rec


def _row_to_record(row: sqlite3.Row) -> EditableCopyRecord:
    return EditableCopyRecord(
        id=row["id"],
        clip_id=row["clip_id"],
        original_path=row["original_path"],
        copy_path=row["copy_path"],
        revision=int(row["revision"]),
        original_hash=row["original_hash"] or "",
        copy_hash=row["copy_hash"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def open_copy_path(copy_path: str) -> bool:
    path = Path(copy_path)
    if not path.is_file():
        return False
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    except OSError:
        return False
