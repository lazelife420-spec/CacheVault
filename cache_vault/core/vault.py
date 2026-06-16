"""The Vault service — the orchestration layer the UI and tray talk to.

It wires storage + classifiers + sensitive detection + the event log + settings
together so the UI stays thin and the capture pipeline lives in one place.
"""

from __future__ import annotations

from . import classify, models, sensitive
from . import clip_metadata
from .duplicates import (
    DuplicateGroup,
    apply_duplicate_review,
    find_exact_duplicate_groups,
    find_possible_duplicate_groups,
)
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

        clip.title = clip_metadata.clip_title(content, clip.preview)
        clip.source_url = clip_metadata.extract_source_url(content, clip.classification)
        clip.normalized_hash = clip_metadata.normalized_hash(content)
        clip.size_bytes = clip_metadata.size_bytes_for(content)
        clip.use_count = 1
        clip.last_used_at = clip.created_at

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

    def capture_image(self, png_bytes: bytes, *, width: int, height: int,
                      source_app: str | None = None,
                      source_window: str | None = None,
                      original_name: str | None = None) -> Clip | None:
        """Persist a screenshot/image from the clipboard as a vault clip + asset."""
        from . import image_assets

        if self.settings.capture_paused:
            return None
        if not png_bytes:
            return None
        if self.settings.is_app_excluded(source_app):
            return None

        chash = models.bytes_hash(png_bytes)
        prev = self.storage.latest_clip()
        if prev is not None and prev.content_hash == chash:
            return None

        preview = image_assets.image_preview_label(width, height)
        content = image_assets.image_content_label(width, height)
        clip = Clip(
            content_hash=chash,
            content_type=models.CONTENT_IMAGE,
            content=content,
            preview=preview,
            source_app=source_app,
            source_window=source_window,
            classification=models.CLASS_IMAGE,
            tags=["image", "screenshot"],
            title=original_name or "Screenshot",
            size_bytes=len(png_bytes),
            use_count=1,
        )
        clip.last_used_at = clip.created_at
        self.storage.add_clip(clip)

        record = image_assets.ClipAssetRecord(
            asset_id=models.new_id(),
            clip_id=clip.id,
            mime_type="image/png",
            file_ext="png",
            size_bytes=len(png_bytes),
            sha256=chash,
            created_at=models.now_iso(),
            original_name=original_name,
            storage_name=image_assets.make_storage_name(clip.id, "png"),
            width=width or None,
            height=height or None,
        )
        self.storage.save_clip_asset(record, png_bytes)

        self.events.record(
            models.EVENT_CAPTURED, clip.id,
            {
                "classification": clip.classification,
                "content_type": clip.content_type,
                "asset_sha256": chash,
                "size_bytes": len(png_bytes),
                "width": width,
                "height": height,
                "source_app": source_app,
            },
        )
        self.events.record(
            models.EVENT_ASSET_PERSISTED, clip.id,
            {"mime_type": "image/png", "size_bytes": len(png_bytes)},
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
        if clip.content_type == models.CONTENT_IMAGE:
            return None
        return clip.content

    def copied_again_image(self, clip_id: str) -> bytes | None:
        """Return PNG bytes for image clips after logging copied_again."""
        clip = self.storage.get_clip(clip_id)
        if clip is None or clip.content_type != models.CONTENT_IMAGE:
            return None
        self.storage.touch_clip(clip_id)
        self.events.record(models.EVENT_COPIED_AGAIN, clip_id)
        loaded = self.storage.load_clip_asset_bytes(clip_id)
        return loaded[0] if loaded else None

    def log_item_pasted(
        self,
        clip_id: str,
        *,
        success: bool,
        item_type: str,
        target_title: str = "",
        clipboard_restored: bool = False,
        reason: str = "",
    ) -> None:
        self.events.record(
            models.EVENT_ITEM_PASTED,
            clip_id,
            {
                "success": success,
                "item_type": item_type,
                "target_title": target_title[:120] if target_title else "",
                "clipboard_restored": clipboard_restored,
                "reason": reason[:80] if reason else "",
            },
        )

    # --- editable copies (originals immutable) -----------------------------
    def _editable_store(self):
        from .editable_copies import EditableCopyStore
        return EditableCopyStore(self.storage.conn)

    def latest_editable_copy(self, clip_id: str):
        return self._editable_store().latest_for_clip(clip_id)

    def create_editable_copy(self, clip_id: str):
        import os

        from .editable_copies import (
            EditableCopyRecord,
            file_sha256,
            is_local_file_path,
            write_file_receipt,
        )
        from .pathutil import clean_path

        clip = self.storage.get_clip(clip_id)
        if clip is None or not is_local_file_path(clip.content):
            return None
        original = clean_path(clip.content)
        before_hash = file_sha256(original)
        try:
            rec: EditableCopyRecord = self._editable_store().create_copy(clip_id, original)
        except (FileNotFoundError, FileExistsError, OSError):
            return None
        after_orig = file_sha256(original)
        if after_orig != before_hash:
            return None
        details = {
            "original_path": original,
            "copy_path": rec.copy_path,
            "revision": rec.revision,
            "size_bytes": os.path.getsize(rec.copy_path),
            "hash_before": before_hash,
            "hash_after": rec.copy_hash,
        }
        self.events.record(models.EVENT_EDITABLE_COPY_CREATED, clip_id, details)
        write_file_receipt(
            "editable_copy_created",
            {"clip_id": clip_id, "timestamp": rec.created_at, **details},
        )
        return rec

    def save_editable_revision(self, clip_id: str):
        from .editable_copies import write_file_receipt

        rec = self._editable_store().save_revision(clip_id)
        if rec is None:
            return None
        previous_hash = getattr(rec, "_previous_hash", "")
        details = {
            "revision": rec.revision,
            "copy_path": rec.copy_path,
            "previous_hash": previous_hash,
            "new_hash": rec.copy_hash,
        }
        self.events.record(models.EVENT_EDITABLE_COPY_SAVED, clip_id, details)
        write_file_receipt(
            "editable_copy_saved",
            {"clip_id": clip_id, "timestamp": rec.updated_at, **details},
        )
        return rec

    def open_editable_copy(self, clip_id: str) -> bool:
        from .editable_copies import open_copy_path

        rec = self.latest_editable_copy(clip_id)
        if rec is None:
            rec = self.create_editable_copy(clip_id)
        if rec is None:
            return False
        return open_copy_path(rec.copy_path)

    def delete_editable_copy(self, clip_id: str) -> bool:
        rec = self.latest_editable_copy(clip_id)
        if rec is None:
            return False
        deleted = self._editable_store().delete_copy_record(rec.id)
        return deleted is not None

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

    def dashboard_summary(self) -> dict:
        counts = self.storage.counts()
        recent = self.events.recent(1)
        last_action = recent[0]["event_type"] if recent else "—"
        return {
            "all": counts.get("all", 0),
            "favorites": counts.get("favorites", 0),
            "screenshots": counts.get("screenshots", 0),
            "duplicates": self.storage.count_duplicate_groups(),
            "recently_removed": counts.get("recently_removed", 0),
            "receipts": len(self.events.recent(500)),
            "sensitive": counts.get("sensitive", 0),
            "expired": counts.get("expired", 0),
            "last_receipt_action": last_action,
            "mobile_enabled": bool(self.settings.mobile_access_enabled),
            "mobile_port": self.settings.mobile_access_port,
            "paired_count": len(self.settings.paired_devices),
            "capture_paused": bool(self.settings.capture_paused),
        }

    def duplicate_groups(self, *, include_possible: bool = True) -> list[DuplicateGroup]:
        groups = find_exact_duplicate_groups(self.storage)
        if include_possible:
            groups = groups + find_possible_duplicate_groups(self.storage)
        return groups

    def review_duplicates(self, group: DuplicateGroup, action: str,
                          *, merge_history: bool = False) -> str:
        return apply_duplicate_review(
            self.storage, self.events, group, action, merge_history=merge_history
        )

    def clip_usage_events(self, clip_id: str) -> list[dict]:
        return self.storage.events_for_clip(clip_id)

    def close(self) -> None:
        self.storage.close()
