"""The local event log — the seed of a future receipt/proof layer.

Events record *that* something happened (captured, pinned, expired, …), never
the secret payload. ``details`` is restricted to safe metadata.
"""

from __future__ import annotations

import json

from . import models


# Keys that must never appear in an event's details blob.
_FORBIDDEN_DETAIL_KEYS = {"content", "secret", "password", "token", "value"}


class EventLog:
    def __init__(self, storage):
        self._storage = storage

    def record(self, event_type: str, clip_id: str | None = None,
               details: dict | None = None) -> str:
        safe = self._sanitize(details or {})
        event_id = models.new_id()
        self._storage.conn.execute(
            "INSERT INTO events (id, created_at, event_type, clip_id, details) "
            "VALUES (?,?,?,?,?)",
            (event_id, models.now_iso(), event_type, clip_id, json.dumps(safe)),
        )
        self._storage.conn.commit()
        return event_id

    @staticmethod
    def _sanitize(details: dict) -> dict:
        return {
            k: v for k, v in details.items()
            if k.lower() not in _FORBIDDEN_DETAIL_KEYS
        }

    def recent(self, limit: int = 200) -> list[dict]:
        rows = self._storage.conn.execute(
            "SELECT id, created_at, event_type, clip_id, details FROM events "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "created_at": r["created_at"],
                "event_type": r["event_type"],
                "clip_id": r["clip_id"],
                "details": json.loads(r["details"]) if r["details"] else {},
            })
        return out
