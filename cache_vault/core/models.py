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
CLASS_IMAGE = "image"

CLASSIFICATIONS = (
    CLASS_LINK,
    CLASS_PATH,
    CLASS_CODE,
    CLASS_COMMAND,
    CLASS_EMAIL,
    CLASS_PHONE,
    CLASS_PLAIN,
    CLASS_IMAGE,
)

# --- Content types ---------------------------------------------------------
CONTENT_TEXT = "text"
CONTENT_IMAGE = "image"

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
EVENT_ITEM_PASTED = "item_pasted"
EVENT_EDITABLE_COPY_CREATED = "editable_copy_created"
EVENT_EDITABLE_COPY_SAVED = "editable_copy_saved"
EVENT_EDITABLE_HTML_COPY_CREATED = "editable_html_copy_created"
EVENT_EDITABLE_HTML_COPY_SAVED = "editable_html_copy_saved"
EVENT_EXPORT_ZIP_CREATED = "export_zip_created"
EVENT_ITEM_EXPORTED = "item_exported"
EVENT_REVEALED_SENSITIVE = "revealed_sensitive"
EVENT_CLEARED_SENSITIVE = "cleared_sensitive"
EVENT_ASSET_PERSISTED = "asset_persisted"
EVENT_DUPLICATE_REVIEW = "duplicate_review"
EVENT_USAGE_MERGED = "usage_merged"
EVENT_CLIPBOARD_AUTO_SAVED = "clipboard_auto_saved"
EVENT_CLIPBOARD_MANUAL_SAVED = "clipboard_manual_saved"
EVENT_CLIPBOARD_NEXT_COPY_ARMED = "clipboard_next_copy_armed"
EVENT_CLIPBOARD_NEXT_COPY_SAVED = "clipboard_next_copy_saved"
EVENT_CLIPBOARD_NEXT_COPY_IGNORED = "clipboard_next_copy_ignored"
EVENT_CLIPBOARD_SENSITIVE_BLOCKED = "clipboard_sensitive_not_auto_saved"
EVENT_ITEM_MOVED_TO_SAFE = "item_moved_to_safe"
EVENT_SAFE_CREATED = "safe_created"
EVENT_VAULT_MACROS_SETUP = "vault_macros_setup_completed"
EVENT_MACRO_SAFE_CREATED = "macro_safe_created"
EVENT_MACRO_TEMPLATE_CREATED = "macro_template_created"
EVENT_MACRO_SMART_TYPE_ASSIGNED = "macro_smart_type_assigned"
EVENT_MACRO_MOVED_BY_USER = "macro_moved_by_user"
EVENT_MACRO_CONFLICT_DETECTED = "macro_conflict_detected"
EVENT_MACRO_EXECUTED = "macro_executed"
EVENT_MACRO_FAILED = "macro_failed"
EVENT_TEXT_SHORTCUT_EXPANDED = "text_shortcut_expanded"
EVENT_MACRO_HOTKEY_EXECUTED = "macro_hotkey_executed"
EVENT_MACRO_PICKER_EXECUTED = "macro_picker_executed"
EVENT_MACRO_BLOCKED_SENSITIVE = "macro_blocked_sensitive"
EVENT_MACRO_DISABLED_SKIPPED = "macro_disabled_skipped"
EVENT_MOBILE_INBOX_RECEIVED = "mobile_inbox_received"
EVENT_ASSET_DRAG_STARTED = "asset_drag_started"
EVENT_ASSET_DRAG_EXPORT_PREPARED = "asset_drag_export_prepared"
EVENT_ASSET_DRAG_BLOCKED_LOCKED = "asset_drag_blocked_locked"
EVENT_ASSET_DRAG_MISSING_FILE = "asset_drag_missing_file"
EVENT_ASSET_DRAG_FALLBACK_USED = "asset_drag_fallback_used"
EVENT_CLEANUP_SCAN_COMPLETED = "cleanup_scan_completed"
EVENT_CLEANUP_APPLIED = "cleanup_applied"
EVENT_EMPTIED_COLLECTION = "emptied_collection"

# Capture modes stored on each clip.
CAPTURE_AUTO = "auto"
CAPTURE_MANUAL_SAVE_HOTKEY = "manual_save_hotkey"
CAPTURE_ARMED_NEXT_COPY = "armed_next_copy"
CAPTURE_MOVED_TO_SAFE = "moved_to_safe"
CAPTURE_IMPORTED = "imported"
CAPTURE_MOBILE = "mobile"
CAPTURE_MOBILE_SHARE = "mobile_share"
CAPTURE_EXTERNAL_APP = "external_app"

CAPTURE_MODES = (
    CAPTURE_AUTO,
    CAPTURE_MANUAL_SAVE_HOTKEY,
    CAPTURE_ARMED_NEXT_COPY,
    CAPTURE_MOVED_TO_SAFE,
    CAPTURE_IMPORTED,
    CAPTURE_MOBILE,
    CAPTURE_MOBILE_SHARE,
    CAPTURE_EXTERNAL_APP,
)

# Receipt action names (file receipts under Receipts/).
ACTION_CLIPBOARD_AUTO_SAVED = "clipboard_auto_saved"
ACTION_CLIPBOARD_MANUAL_SAVED = "clipboard_manual_saved"
ACTION_CLIPBOARD_NEXT_COPY_ARMED = "clipboard_next_copy_armed"
ACTION_CLIPBOARD_NEXT_COPY_SAVED = "clipboard_next_copy_saved"
ACTION_CLIPBOARD_NEXT_COPY_IGNORED = "clipboard_next_copy_ignored"
ACTION_ITEM_MOVED_TO_SAFE = "item_moved_to_safe"
ACTION_SAFE_CREATED = "safe_created"
ACTION_MOBILE_SENT_TO_PC = "mobile_sent_to_pc"
ACTION_MOBILE_INBOX_RECEIVED = "mobile_inbox_received"
ACTION_CLEANUP_APPLIED = "cleanup_applied"
ACTION_EMPTY_COLLECTION = "empty_collection"

PREVIEW_MAX_CHARS = 200

# Developer CLI constants
CLI_DEVICE_ID = "cli-device"
CLI_DEVICE_NAME = "Developer CLI"

# Sort keys for list/grid views
SORT_NEWEST_ADDED = "newest_added"
SORT_OLDEST_ADDED = "oldest_added"
SORT_RECENTLY_USED = "recently_used"
SORT_OLDEST_USED = "oldest_used"
SORT_MOST_USED = "most_used"
SORT_LEAST_USED = "least_used"
SORT_LARGEST = "largest"
SORT_SMALLEST = "smallest"
SORT_SOURCE = "source_app"
SORT_TYPE = "type"
SORT_COLLECTION = "collection"
SORT_FAVORITES_FIRST = "favorites_first"
SORT_DUPLICATES_FIRST = "duplicates_first"


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


def bytes_hash(data: bytes) -> str:
    """SHA-256 for binary assets (screenshots/images)."""
    return hashlib.sha256(data).hexdigest()


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
    title: str | None = None
    source_url: str | None = None
    normalized_hash: str | None = None
    size_bytes: int = 0
    last_used_at: str | None = None
    use_count: int = 0
    copied_count: int = 0
    safe_id: str = "default"
    safe_name: str = "Default Safe"
    capture_mode: str = CAPTURE_AUTO
    is_saved_to_phone: bool = False

    @property
    def first_saved_at(self) -> str:
        """Alias for created_at (Date Added / First Saved)."""
        return self.created_at

    @property
    def date_used(self) -> str | None:
        """Last Used timestamp; falls back to updated_at for legacy rows."""
        return self.last_used_at or self.updated_at

    def to_dict(self) -> dict:
        return asdict(self)
