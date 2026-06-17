"""The Vault service — the orchestration layer the UI and tray talk to.

It wires storage + classifiers + sensitive detection + the event log + settings
together so the UI stays thin and the capture pipeline lives in one place.
"""

from __future__ import annotations

from . import classify, models, sensitive
from . import clip_metadata
from .capture_receipts import record_capture_receipt, record_sensitive_blocked
from .safes import SafeRegistry
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
        self.safes = SafeRegistry(self.settings)

    # --- capture -----------------------------------------------------------
    def _capture_blocked(
        self,
        *,
        capture_mode: str,
        source_app: str | None,
        content_hash: str,
        size_bytes: int,
        sens,
        force: bool,
    ) -> str | None:
        """Return a block reason string, or None if capture may proceed."""
        if self.settings.capture_paused and not force:
            return "capture_paused"
        if self.settings.is_app_excluded(source_app):
            return "excluded_app"
        if (
            capture_mode == models.CAPTURE_AUTO
            and self.settings.max_auto_capture_bytes > 0
            and size_bytes > self.settings.max_auto_capture_bytes
        ):
            return "max_size_exceeded"
        if (
            capture_mode == models.CAPTURE_AUTO
            and self.settings.block_sensitive_auto_capture
            and sens.is_sensitive
            and not force
        ):
            record_sensitive_blocked(
                self.events,
                source_app=source_app,
                content_hash=content_hash,
                reason=sens.reason,
            )
            return "sensitive_blocked"
        return None

    def _resolve_safe(self, safe_id: str | None) -> tuple[str, str] | None:
        safe = self.safes.resolve(safe_id)
        if safe is None:
            safe = self.safes.default_safe()
        if self.safes.is_ignore(safe.id):
            return None
        return safe.id, safe.name

    def _capture_event_for_mode(self, capture_mode: str) -> tuple[str, str]:
        if capture_mode == models.CAPTURE_MANUAL_SAVE_HOTKEY:
            return (
                models.ACTION_CLIPBOARD_MANUAL_SAVED,
                models.EVENT_CLIPBOARD_MANUAL_SAVED,
            )
        if capture_mode == models.CAPTURE_ARMED_NEXT_COPY:
            return (
                models.ACTION_CLIPBOARD_NEXT_COPY_SAVED,
                models.EVENT_CLIPBOARD_NEXT_COPY_SAVED,
            )
        return (
            models.ACTION_CLIPBOARD_AUTO_SAVED,
            models.EVENT_CLIPBOARD_AUTO_SAVED,
        )

    def capture(
        self,
        content: str,
        *,
        source_app: str | None = None,
        source_window: str | None = None,
        capture_mode: str = models.CAPTURE_AUTO,
        safe_id: str | None = None,
        force: bool = False,
    ) -> Clip | None:
        """Classify and store a new clip. Returns ``None`` when ignored."""
        if content is None or not content.strip():
            return None

        resolved = self._resolve_safe(safe_id)
        if resolved is None:
            return None
        sid, sname = resolved

        if capture_mode == models.CAPTURE_AUTO and not force:
            if not self.settings.auto_capture_enabled:
                return None

        chash = models.content_hash(content)
        prev = self.storage.latest_clip()
        if prev is not None and prev.content_hash == chash:
            return None

        result = classify.classify(content)
        sens = sensitive.detect(content)
        size_bytes = clip_metadata.size_bytes_for(content)

        blocked = self._capture_blocked(
            capture_mode=capture_mode,
            source_app=source_app,
            content_hash=chash,
            size_bytes=size_bytes,
            sens=sens,
            force=force,
        )
        if blocked:
            return None

        clip = Clip(
            content_hash=chash,
            content=content,
            source_app=source_app,
            source_window=source_window,
            classification=result.classification,
            tags=result.tags,
            is_sensitive=sens.is_sensitive,
            safe_id=sid,
            safe_name=sname,
            capture_mode=capture_mode,
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
        clip.size_bytes = size_bytes
        clip.use_count = 1
        clip.last_used_at = clip.created_at

        self.storage.add_clip(clip)
        action, event_type = self._capture_event_for_mode(capture_mode)
        record_capture_receipt(
            self.events,
            action=action,
            event_type=event_type,
            success=True,
            clip_id=clip.id,
            safe_id=sid,
            safe_name=sname,
            capture_mode=capture_mode,
            source_app=source_app,
            content_hash=chash,
            item_type=clip.classification,
        )
        self.events.record(
            models.EVENT_CAPTURED, clip.id,
            {
                "classification": clip.classification,
                "is_sensitive": clip.is_sensitive,
                "reason": sens.reason or None,
                "source_app": source_app,
                "safe_id": sid,
                "safe_name": sname,
                "capture_mode": capture_mode,
            },
        )
        if self.settings.history_max_clips > 0:
            pruned = self.storage.prune_history(self.settings.history_max_clips)
            for cid in pruned:
                self.events.record(models.EVENT_DELETED, cid,
                                   {"action": "history_prune"})
        return clip

    def capture_manual(
        self,
        content: str,
        *,
        safe_id: str | None = None,
        source_app: str | None = None,
        source_window: str | None = None,
    ) -> Clip | None:
        return self.capture(
            content,
            source_app=source_app,
            source_window=source_window,
            capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY,
            safe_id=safe_id,
            force=True,
        )

    def capture_mobile_share(
        self,
        content: str,
        *,
        source_app: str | None = None,
        source_window: str | None = None,
        source_url: str | None = None,
        safe_id: str | None = None,
        device_name: str | None = None,
        device_id: str | None = None,
        item_type: str = "text",
    ) -> Clip | None:
        """Intentional paired mobile send — always creates a vault item."""
        if content is None or not content.strip():
            return None

        resolved = self._resolve_safe(safe_id)
        if resolved is None:
            return None
        sid, sname = resolved

        if item_type == "url" and not content.startswith(("http://", "https://")):
            content = content.strip()

        chash = models.content_hash(content)
        result = classify.classify(content)
        sens = sensitive.detect(content)
        size_bytes = clip_metadata.size_bytes_for(content)

        if self.settings.capture_paused:
            return None

        clip = Clip(
            content_hash=chash,
            content=content,
            source_app=source_app,
            source_window=source_window,
            classification=result.classification,
            tags=result.tags,
            is_sensitive=sens.is_sensitive,
            safe_id=sid,
            safe_name=sname,
            capture_mode=models.CAPTURE_MOBILE_SHARE,
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
        clip.source_url = source_url or clip_metadata.extract_source_url(
            content, clip.classification,
        )
        clip.normalized_hash = clip_metadata.normalized_hash(content)
        clip.size_bytes = size_bytes
        clip.use_count = 1
        clip.last_used_at = clip.created_at

        self.storage.add_clip(clip)
        record_capture_receipt(
            self.events,
            action=models.ACTION_MOBILE_SENT_TO_PC,
            event_type=models.EVENT_MOBILE_INBOX_RECEIVED,
            success=True,
            clip_id=clip.id,
            safe_id=sid,
            safe_name=sname,
            capture_mode=models.CAPTURE_MOBILE_SHARE,
            source_app=source_app,
            content_hash=chash,
            item_type=clip.classification,
        )
        self.events.record(
            models.EVENT_CAPTURED, clip.id,
            {
                "classification": clip.classification,
                "is_sensitive": clip.is_sensitive,
                "source_app": source_app,
                "source_window": source_window,
                "source_url": clip.source_url,
                "safe_id": sid,
                "safe_name": sname,
                "capture_mode": models.CAPTURE_MOBILE_SHARE,
                "mobile_device_id": device_id,
                "mobile_device_name": device_name,
            },
        )
        if self.settings.history_max_clips > 0:
            pruned = self.storage.prune_history(self.settings.history_max_clips)
            for cid in pruned:
                self.events.record(models.EVENT_DELETED, cid,
                                   {"action": "history_prune"})
        return clip

    def list_mobile_inbox(self, *, limit: int = 200) -> list[Clip]:
        return self.storage.list_by_capture_mode(
            models.CAPTURE_MOBILE_SHARE, limit=limit,
        )

    def capture_image(
        self,
        png_bytes: bytes,
        *,
        width: int,
        height: int,
        source_app: str | None = None,
        source_window: str | None = None,
        original_name: str | None = None,
        capture_mode: str = models.CAPTURE_AUTO,
        safe_id: str | None = None,
        force: bool = False,
    ) -> Clip | None:
        """Persist a screenshot/image from the clipboard as a vault clip + asset."""
        from . import image_assets

        if not png_bytes:
            return None

        resolved = self._resolve_safe(safe_id)
        if resolved is None:
            return None
        sid, sname = resolved

        if capture_mode == models.CAPTURE_AUTO and not force:
            if not self.settings.auto_capture_enabled:
                return None

        chash = models.bytes_hash(png_bytes)
        prev = self.storage.latest_clip()
        if prev is not None and prev.content_hash == chash:
            return None

        blocked = self._capture_blocked(
            capture_mode=capture_mode,
            source_app=source_app,
            content_hash=chash,
            size_bytes=len(png_bytes),
            sens=sensitive.SensitiveResult(),
            force=force,
        )
        if blocked:
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
            safe_id=sid,
            safe_name=sname,
            capture_mode=capture_mode,
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

        action, event_type = self._capture_event_for_mode(capture_mode)
        record_capture_receipt(
            self.events,
            action=action,
            event_type=event_type,
            success=True,
            clip_id=clip.id,
            safe_id=sid,
            safe_name=sname,
            capture_mode=capture_mode,
            source_app=source_app,
            content_hash=chash,
            item_type=models.CLASS_IMAGE,
        )
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
                "safe_id": sid,
                "safe_name": sname,
                "capture_mode": capture_mode,
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

    def move_to_safe(self, clip_id: str, safe_id: str) -> Clip | None:
        safe = self.safes.resolve(safe_id)
        if safe is None or self.safes.is_ignore(safe.id):
            return None
        clip = self.storage.get_clip(clip_id)
        if clip is None:
            return None
        self.storage.set_safe(
            clip_id, safe.id, safe.name, models.CAPTURE_MOVED_TO_SAFE,
        )
        record_capture_receipt(
            self.events,
            action=models.ACTION_ITEM_MOVED_TO_SAFE,
            event_type=models.EVENT_ITEM_MOVED_TO_SAFE,
            success=True,
            clip_id=clip_id,
            safe_id=safe.id,
            safe_name=safe.name,
            capture_mode=models.CAPTURE_MOVED_TO_SAFE,
            content_hash=clip.content_hash,
            item_type=clip.classification,
        )
        return self.storage.get_clip(clip_id)

    def create_safe(self, name: str):
        safe = self.safes.create(name)
        record_capture_receipt(
            self.events,
            action=models.ACTION_SAFE_CREATED,
            event_type=models.EVENT_SAFE_CREATED,
            success=True,
            safe_id=safe.id,
            safe_name=safe.name,
        )
        return safe

    def list_safes(self) -> list[dict]:
        counts = {s["id"]: s for s in self.storage.list_safes()}
        out = []
        for safe in self.safes.list_destinations():
            row = counts.get(safe.id, {})
            out.append({
                "id": safe.id,
                "name": safe.name,
                "count": row.get("count", 0),
                "builtin": safe.builtin,
                "icon": safe.icon,
                "accent": safe.accent,
                "description": safe.description,
                "default_capture": safe.default_capture,
                "show_in_sidebar": safe.show_in_sidebar,
                "favorite": safe.favorite,
                "receipt_label": safe.receipt_label,
                "visual_style": safe.visual_style,
            })
        return out

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
        from pathlib import Path

        from .editable_copies import (
            EditableCopyRecord,
            KIND_HTML_BUNDLE,
            file_sha256,
            is_html_path,
            is_local_file_path,
            scan_html_assets,
            write_file_receipt,
        )
        from .pathutil import clean_path

        clip = self.storage.get_clip(clip_id)
        if clip is None or not is_local_file_path(clip.content):
            return None
        original = clean_path(clip.content)
        before_hash = file_sha256(original)
        asset_hashes_before: dict[str, str] = {}
        if is_html_path(original):
            html_root = Path(original).parent.resolve()
            scan = scan_html_assets(Path(original))
            for rel in scan.copied_assets:
                src = html_root / rel
                if src.is_file():
                    asset_hashes_before[rel] = file_sha256(src)
        try:
            rec: EditableCopyRecord = self._editable_store().create_copy(clip_id, original)
        except (FileNotFoundError, FileExistsError, OSError):
            return None
        after_orig = file_sha256(original)
        if after_orig != before_hash:
            return None
        if asset_hashes_before:
            html_root = Path(original).parent.resolve()
            for rel, digest in asset_hashes_before.items():
                src = html_root / rel
                if src.is_file() and file_sha256(src) != digest:
                    return None

        if rec.kind == KIND_HTML_BUNDLE:
            meta = getattr(rec, "_bundle_meta", None)
            if meta is None:
                from .editable_copies import load_bundle_meta
                meta = load_bundle_meta(rec.bundle_dir)
            receipt = {
                "clip_id": clip_id,
                "timestamp": rec.created_at,
                "success": True,
                "original_path": original,
                "copy_path": rec.copy_path,
                "bundle_dir": rec.bundle_dir,
                "revision": rec.revision,
                "copied_asset_count": len(meta.copied_assets) if meta else 0,
                "missing_asset_count": len(meta.missing_assets) if meta else 0,
                "skipped_remote_asset_count": len(meta.remote_assets) if meta else 0,
                "hash_before": before_hash,
                "hash_after": rec.copy_hash,
                "warnings": (meta.warnings if meta else [])[:8],
            }
            self.events.record(models.EVENT_EDITABLE_HTML_COPY_CREATED, clip_id, receipt)
            write_file_receipt("editable_html_copy_created", receipt)
            return rec

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
        from .editable_copies import KIND_HTML_BUNDLE, write_file_receipt

        rec = self._editable_store().save_revision(clip_id)
        if rec is None:
            return None
        previous_hash = getattr(rec, "_previous_hash", "")
        if rec.kind == KIND_HTML_BUNDLE:
            changed = getattr(rec, "_changed_files", [])
            receipt = {
                "clip_id": clip_id,
                "timestamp": rec.updated_at,
                "revision": rec.revision,
                "copy_path": rec.copy_path,
                "bundle_dir": rec.bundle_dir,
                "previous_hash": previous_hash,
                "new_hash": rec.copy_hash,
                "changed_files": changed[:50],
            }
            self.events.record(models.EVENT_EDITABLE_HTML_COPY_SAVED, clip_id, receipt)
            write_file_receipt("editable_html_copy_saved", receipt)
            return rec
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

    def preview_html_copy(self, clip_id: str) -> bool:
        return self.open_editable_copy(clip_id)

    def edit_html_source(self, clip_id: str) -> bool:
        from .editable_copies import edit_copy_source

        rec = self.latest_editable_copy(clip_id)
        if rec is None:
            rec = self.create_editable_copy(clip_id)
        if rec is None:
            return False
        return edit_copy_source(rec.copy_path)

    def html_bundle_summary(self, clip_id: str) -> dict | None:
        from .editable_copies import html_bundle_summary

        return html_bundle_summary(clip_id, self._editable_store())

    def export_html_bundle(self, clip_id: str, dest_zip: str) -> bool:
        result = self.export_proof_zip(
            [clip_id], dest_zip, mode="html_bundle",
        )
        return result.success

    def delete_editable_copy(self, clip_id: str) -> bool:
        rec = self.latest_editable_copy(clip_id)
        if rec is None:
            return False
        deleted = self._editable_store().delete_copy_record(rec.id)
        return deleted is not None

    def _events_for_clips(self, clip_ids: list[str], limit: int = 200) -> list[dict]:
        if not clip_ids:
            return self.events.recent(limit)
        placeholders = ",".join("?" * len(clip_ids))
        rows = self.storage.conn.execute(
            f"SELECT id, created_at, event_type, clip_id, details FROM events "
            f"WHERE clip_id IN ({placeholders}) "
            f"ORDER BY created_at DESC LIMIT ?",
            (*clip_ids, limit),
        ).fetchall()
        out = []
        for r in rows:
            import json
            out.append({
                "id": r["id"],
                "created_at": r["created_at"],
                "event_type": r["event_type"],
                "clip_id": r["clip_id"],
                "details": json.loads(r["details"] or "{}"),
            })
        return out

    def export_proof_zip(
        self,
        clip_ids: list[str],
        dest_zip: str,
        *,
        mode: str = "auto",
        include_original_files: bool = False,
        collection_name: str | None = None,
    ):
        from .exports import ProofExportResult, create_proof_zip

        clips = [self.storage.get_clip(cid) for cid in clip_ids]
        clips = [c for c in clips if c is not None]
        if not clips:
            return ProofExportResult(export_id=models.new_id(), success=False,
                                     error="no clips")

        def load_asset(clip_id: str) -> bytes | None:
            loaded = self.storage.load_clip_asset_bytes(clip_id)
            return loaded[0] if loaded else None

        result = create_proof_zip(
            clips,
            dest_zip,
            mode=mode,
            include_original_files=include_original_files,
            get_editable_copy=self.latest_editable_copy,
            events_for_clips=self._events_for_clips,
            load_asset_bytes=load_asset,
            collection_name=collection_name,
        )
        if result.success:
            details = {
                "export_id": result.export_id,
                "path": str(result.zip_path),
                "file_count": result.file_count,
                "receipt_count": result.receipt_count,
                "sha256sums_included": True,
                "manifest_included": True,
                "receipts_included": True,
                "mode": mode,
                "safes": result.manifest.get("safes", []),
                "warnings": result.warnings[:20],
            }
            self.events.record(
                models.EVENT_EXPORT_ZIP_CREATED,
                clip_ids[0] if len(clip_ids) == 1 else None,
                details,
            )
            for cid in clip_ids:
                self.events.record(
                    models.EVENT_ITEM_EXPORTED, cid,
                    {"export_id": result.export_id, "path": str(result.zip_path)},
                )
            self.events.record(models.EVENT_EXPORTED, None, {
                "export_id": result.export_id,
                "target": "proof_zip",
                "count": len(clips),
                "path": str(result.zip_path),
            })
        return result

    def list_editable_copies(self):
        from .editable_copies import KIND_FILE
        return self._editable_store().list_latest_records(kind=KIND_FILE)

    def list_html_bundles(self):
        from .editable_copies import KIND_HTML_BUNDLE
        return self._editable_store().list_latest_records(kind=KIND_HTML_BUNDLE)

    def editable_copy_counts(self) -> dict:
        from .editable_copies import KIND_FILE, KIND_HTML_BUNDLE
        store = self._editable_store()
        return {
            "editable_copies": store.count_distinct_clips(kind=KIND_FILE),
            "html_bundles": store.count_distinct_clips(kind=KIND_HTML_BUNDLE),
        }

    def list_export_events(self, limit: int = 50) -> list[dict]:
        rows = self.storage.conn.execute(
            "SELECT id, created_at, event_type, clip_id, details FROM events "
            "WHERE event_type IN (?, ?, ?) "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (models.EVENT_EXPORTED, models.EVENT_EXPORT_ZIP_CREATED, models.EVENT_ITEM_EXPORTED, limit),
        ).fetchall()
        out = []
        for r in rows:
            import json
            details = json.loads(r["details"] or "{}")
            out.append({
                "id": r["id"],
                "created_at": r["created_at"],
                "clip_id": r["clip_id"],
                "details": details,
            })
        return out

    def clip_inspector_context(self, clip_id: str) -> dict:
        rows = self.storage.conn.execute(
            "SELECT event_type, created_at FROM events WHERE clip_id = ? "
            "ORDER BY created_at DESC",
            (clip_id,),
        ).fetchall()
        last_pasted = last_exported = None
        for r in rows:
            if r["event_type"] == models.EVENT_ITEM_PASTED and last_pasted is None:
                last_pasted = r["created_at"]
            if r["event_type"] == models.EVENT_EXPORTED and last_exported is None:
                last_exported = r["created_at"]
        rec = self.latest_editable_copy(clip_id)
        html = self.html_bundle_summary(clip_id) if rec else None
        from .editable_copies import is_html_path
        from .pathutil import clean_path, is_local_file
        clip = self.storage.get_clip(clip_id)
        original_protected = bool(
            clip and clip.classification == models.CLASS_PATH
            and is_local_file(clip.content)
        )
        return {
            "receipt_count": len(rows),
            "last_pasted": last_pasted,
            "last_exported": last_exported,
            "editable_copy": rec,
            "html_bundle": html,
            "original_protected": original_protected,
            "is_html": bool(
                clip and is_html_path(clean_path(clip.content))
            ) if clip else False,
        }

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
        copy_counts = self.editable_copy_counts()
        pasted = [
            e for e in self.events.recent(200)
            if e.get("event_type") == models.EVENT_ITEM_PASTED
        ]
        safes = self.safes.list_all()
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
            "default_safe": self.settings.default_safe_id,
            "editable_copies": copy_counts.get("editable_copies", 0),
            "html_bundles": copy_counts.get("html_bundles", 0),
            "recent_pasted_count": len(pasted),
            "safe_count": len(safes),
            "exports": len(self.list_export_events(500)),
            "mobile_inbox": self.storage.count_by_capture_mode(
                models.CAPTURE_MOBILE_SHARE,
            ),
            "vault_macros": 0,
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
