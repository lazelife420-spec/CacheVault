"""The Vault service — the orchestration layer the UI and tray talk to.

It wires storage + classifiers + sensitive detection + the event log + settings
together so the UI stays thin and the capture pipeline lives in one place.
"""

from __future__ import annotations

from . import classify, models, sensitive
from .events import EventLog
from .models import Clip
from .settings import Settings
from .storage import VaultStorage


class Vault:
    def __init__(self, storage: VaultStorage | None = None,
                 settings: Settings | None = None):
        self.storage = storage or VaultStorage()
        self.settings = settings or Settings.load()
        self.events = EventLog(self.storage)

    # --- capture -----------------------------------------------------------
    def capture(self, content: str, *, source_app: str | None = None,
                source_window: str | None = None) -> Clip | None:
        """Classify and store a new clip. Returns ``None`` when the clip is
        ignored (capture paused, empty, excluded app, or a consecutive dup)."""
        if self.settings.capture_paused:
            return None
        if content is None or not content.strip():
            return None
        if self.settings.is_app_excluded(source_app):
            return None

        chash = models.content_hash(content)
        prev = self.storage.latest_clip()
        if prev is not None and prev.content_hash == chash:
            # Consecutive identical copy — don't spam the list.
            return None

        result = classify.classify(content)
        sens = sensitive.detect(content)

        clip = Clip(
            content_hash=chash,
            content=content,
            source_app=source_app,
            source_window=source_window,
            classification=result.classification,
            tags=result.tags,
            is_sensitive=sens.is_sensitive,
        )

        if sens.is_sensitive:
            clip.preview = sensitive.masked_preview(content)
            if self.settings.sensitive_expiry_enabled:
                clip.expires_at = sensitive.compute_expiry(
                    self.settings.sensitive_expiry_minutes
                )
        else:
            clip.preview = models.make_preview(content)

        self.storage.add_clip(clip)
        self.events.record(
            models.EVENT_CAPTURED, clip.id,
            {
                "classification": clip.classification,
                "is_sensitive": clip.is_sensitive,
                "reason": sens.reason or None,
                "source_app": source_app,
            },
        )
        if self.settings.history_max_clips > 0:
            pruned = self.storage.prune_history(self.settings.history_max_clips)
            for cid in pruned:
                self.events.record(models.EVENT_DELETED, cid,
                                   {"action": "history_prune"})
        return clip

    # --- per-clip actions --------------------------------------------------
    def set_pinned(self, clip_id: str, pinned: bool) -> None:
        self.storage.set_pinned(clip_id, pinned)
        self.events.record(
            models.EVENT_PINNED if pinned else models.EVENT_UNPINNED, clip_id
        )

    def set_favorite(self, clip_id: str, favorite: bool) -> None:
        """Add/remove a clip from Favorites (stored in the is_pinned flag).

        Favorites are saved clips: they float to the top and survive pruning.
        """
        self.storage.set_pinned(clip_id, favorite)
        self.events.record(
            models.EVENT_FAVORITED if favorite else models.EVENT_UNFAVORITED, clip_id
        )

    def is_favorite(self, clip_id: str) -> bool:
        clip = self.storage.get_clip(clip_id)
        return bool(clip and clip.is_pinned)

    def remove_from_history(self, clip_id: str) -> None:
        """Remove a clip from Cache Vault history (soft delete → Recently Removed).

        This only hides the clip from history; it never deletes any real file
        or folder from disk. The clip can be restored from Recently Removed.
        """
        self.storage.soft_delete(clip_id)
        self.events.record(models.EVENT_DELETED, clip_id, {"action": "remove_from_history"})

    def restore(self, clip_id: str) -> None:
        """Restore a clip from Recently Removed back into history."""
        self.storage.restore(clip_id)
        self.events.record(models.EVENT_RESTORED, clip_id)

    def permanently_remove(self, clip_id: str) -> None:
        """Hard-delete a clip's Cache Vault entry. Never touches real files."""
        self.events.record(models.EVENT_PERMANENTLY_REMOVED, clip_id)
        self.storage.hard_delete(clip_id)

    def set_collection(self, clip_id: str, collection: str | None) -> None:
        """Move a clip into a named collection (or None to remove it)."""
        self.storage.set_collection(clip_id, collection)
        self.events.record(models.EVENT_MOVED_COLLECTION, clip_id,
                           {"collection": (collection or "").strip() or None})

    def list_collections(self) -> list[dict]:
        return self.storage.list_collections()

    def mark_keep(self, clip_id: str) -> None:
        self.storage.set_kept(clip_id, True)
        self.events.record(models.EVENT_KEPT, clip_id)

    def expire_now(self, clip_id: str) -> None:
        self.storage.scrub_and_expire(clip_id)
        self.events.record(models.EVENT_EXPIRED, clip_id, {"trigger": "manual"})

    def delete(self, clip_id: str) -> None:
        self.storage.soft_delete(clip_id)
        self.events.record(models.EVENT_DELETED, clip_id)

    def reveal_sensitive(self, clip_id: str) -> str | None:
        """Return the full content of a sensitive clip and log the reveal."""
        clip = self.storage.get_clip(clip_id)
        if clip is None:
            return None
        self.events.record(models.EVENT_REVEALED_SENSITIVE, clip_id)
        return clip.content

    def copied_again(self, clip_id: str) -> str | None:
        clip = self.storage.get_clip(clip_id)
        if clip is None:
            return None
        self.storage.touch_clip(clip_id)
        self.events.record(models.EVENT_COPIED_AGAIN, clip_id)
        return clip.content

    def clear_sensitive(self) -> int:
        ids = self.storage.clear_sensitive()
        for cid in ids:
            self.events.record(models.EVENT_EXPIRED, cid, {"trigger": "clear_sensitive"})
        if ids:
            self.events.record(models.EVENT_CLEARED_SENSITIVE, None, {"count": len(ids)})
        return len(ids)

    # --- maintenance -------------------------------------------------------
    def run_expiry_sweep(self) -> int:
        """Scrub clips past their expiry. Call periodically from the UI."""
        ids = self.storage.expire_due()
        for cid in ids:
            self.events.record(models.EVENT_EXPIRED, cid, {"trigger": "auto"})
        return len(ids)

    # --- queries -----------------------------------------------------------
    def list_clips(self, query=None):
        return self.storage.list_clips(query)

    def counts(self):
        return self.storage.counts()

    def close(self) -> None:
        self.storage.close()
