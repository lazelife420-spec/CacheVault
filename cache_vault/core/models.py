"""Shared constants, the :class:`Clip` record, and small helpers.

This module is deliberately dependency-free so every other core module and
the test-suite can import it cheaply.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


# --- Classifications -------------------------------------------------------
# A clip has exactly ONE primary classification (its content type). Whether a
# clip is *sensitive* is tracked separately on ``Clip.is_sensitive`` so a
# "code" clip can also be flagged sensitive without losing its type.
CLASS_LINK = "link"
CLASS_PATH = "path"
CLASS_CODE = "code"
CLASS_COMMAND = "command"
CLASS_EMAIL = "email"
CLASS_PHONE = "phone"
CLASS_PLAIN = "plain"

CLASSIFICATIONS = (
    CLASS_LINK,
    CLASS_PATH,
    CLASS_CODE,
    CLASS_COMMAND,
    CLASS_EMAIL,
    CLASS_PHONE,
    CLASS_PLAIN,
)

# --- Content types ---------------------------------------------------------
CONTENT_TEXT = "text"  # only text is supported in the MVP

# --- Event types -----------------------------------------------------------
EVENT_CAPTURED = "captured"
EVENT_PINNED = "pinned"
EVENT_UNPINNED = "unpinned"
EVENT_FAVORITED = "favorited"
EVENT_UNFAVORITED = "unfavorited"
EVENT_MOVED_COLLECTION = "moved_to_collection"
EVENT_RESTORED = "restored"
EVENT_PERMANENTLY_REMOVED = "permanently_removed"
EVENT_EXPORTED = "exported"
EVENT_KEPT = "kept"
EVENT_EXPIRED = "expired"
EVENT_DELETED = "deleted"
EVENT_COPIED_AGAIN = "copied_again"
EVENT_REVEALED_SENSITIVE = "revealed_sensitive"
EVENT_CLEARED_SENSITIVE = "cleared_sensitive"

PREVIEW_MAX_CHARS = 200


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (the on-disk timestamp format)."""
    return utcnow().isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def content_hash(content: str) -> str:
    """Stable hash used for duplicate detection."""
    return hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()


def make_preview(content: str, max_chars: int = PREVIEW_MAX_CHARS) -> str:
    """Collapse a clip to a single-line preview suitable for the list view.

    This is *not* used for sensitive clips — see
    :func:`cache_vault.core.sensitive.masked_preview`.
    """
    flat = " ".join(content.split())
    if len(flat) > max_chars:
        return flat[: max_chars - 1].rstrip() + "…"
    return flat


@dataclass
class Clip:
    """A single stored clipboard item.

    Mirrors the ``clips`` SQLite table. ``content`` holds the full original
    text; ``preview`` is what the list view shows (already masked for
    sensitive clips so secrets are not exposed casually).
    """

    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    content_hash: str = ""
    content_type: str = CONTENT_TEXT
    content: str = ""
    preview: str = ""
    source_app: str | None = None
    source_window: str | None = None
    classification: str = CLASS_PLAIN
    tags: list[str] = field(default_factory=list)
    is_pinned: bool = False
    is_kept: bool = False
    is_sensitive: bool = False
    expires_at: str | None = None
    deleted_at: str | None = None
    duplicate_of: str | None = None
    collection: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
