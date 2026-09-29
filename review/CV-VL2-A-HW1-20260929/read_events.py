"""Read the event log out of a (possibly still-held) Cache Vault profile.

The running app keeps its WAL open, and a read-only connection cannot always
see uncheckpointed rows, so this copies the database set to a temporary
directory first and then opens the copy read-only-by-convention.

Usage: python read_events.py <profile_dir_or_db_path> [--tables-only]
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def locate_db(target: Path) -> Path:
    if target.is_file():
        return target
    hits = sorted(target.rglob("cache_vault.db"))
    if not hits:
        raise SystemExit(f"no cache_vault.db under {target}")
    return hits[0]


def snapshot(db: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cv-events-"))
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db) + suffix)
        if candidate.exists():
            shutil.copy2(candidate, tmp / candidate.name)
    return tmp / db.name


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    target = Path(sys.argv[1])
    db = locate_db(target)
    copy = snapshot(db)
    con = sqlite3.connect(str(copy))
    con.row_factory = sqlite3.Row

    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("DB=", db)
    print("TABLES=", tables)
    if "--tables-only" in sys.argv:
        return 0

    if "events" not in tables:
        print("NO_EVENTS_TABLE")
        return 0

    rows = con.execute(
        "SELECT created_at, event_type, clip_id, details FROM events "
        "ORDER BY created_at ASC, rowid ASC"
    ).fetchall()
    print("EVENT_COUNT=", len(rows))
    for r in rows:
        try:
            details = json.loads(r["details"]) if r["details"] else {}
        except (TypeError, ValueError):
            details = {"unparsed": r["details"]}
        print(json.dumps({
            "at": r["created_at"],
            "type": r["event_type"],
            "clip_id": r["clip_id"],
            "details": details,
        }, sort_keys=True))

    clips = con.execute("SELECT COUNT(*) FROM clips").fetchone()[0]
    print("CLIP_COUNT=", clips)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
