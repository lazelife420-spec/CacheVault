"""Staged permanent deletion from Recently Removed.

A real filesystem move and a SQLite commit cannot be made a single atomic
operation, so this module never pretends they are. It runs the mutation in
three explicit stages instead:

1. **Preflight** (`build_deletion_plan`) -- a read-only pass that decides,
   per requested id, whether it's eligible (still soft-deleted) and what
   managed asset file (if any) belongs to it, resolved to a canonical path
   that is verified to sit inside the managed assets root. Nothing is
   mutated here.
2. **Stage** (`stage_managed_files`) -- managed asset files are moved by
   atomic rename (``os.replace``, same-volume) into an app-owned
   quarantine directory. Files are not deleted yet. If any single file
   fails to stage, every file already staged in this batch is moved back
   and the whole batch aborts before the database is touched.
3. **Commit** (``storage.hard_delete_many``, called by the caller) --
   one transaction removes the ``clips``/``clip_assets`` rows. If it
   raises, every staged file is restored and the exception propagates
   (matching the rest of this codebase's bulk-mutation contract: the call
   raises and nothing changed -- see ``clear_collection``,
   ``soft_delete_many``). If a specific id in the plan turns out to have
   been restored between staging and commit (a race, not a crash),
   ``storage.hard_delete_many`` reports it in ``.skipped`` rather than
   deleting it, and its file must be un-staged back to its original
   location -- see ``unstage_files``.
4. **Purge** (`purge_staged_files`) -- only after the database commit
   succeeds are the now-orphaned quarantine files actually unlinked.
   Bytes are only counted as reclaimed for files that were actually
   removed; a file that fails to purge is left in quarantine for retry
   and reported as deferred, not silently dropped and not rolled back
   (the database change already committed and stays committed).

External/path-only files (``classification == CLASS_PATH``, no
``clip_assets`` row) never enter a plan at all -- this module only ever
looks at ``clip_assets`` rows resolved through
``image_assets.resolve_managed_path``, so there is no code path here that
can read, open, or touch a file the vault doesn't manage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import models
from .editable_copies import write_file_receipt
from .selection import dedupe_preserve_order


@dataclass(frozen=True)
class DeletionPlan:
    requested_ids: tuple[str, ...]
    eligible_ids: tuple[str, ...]
    skipped: dict[str, str]
    asset_rows: dict[str, object]       # clip_id -> image_assets.ClipAssetRecord
    managed_paths: dict[str, Path]      # clip_id -> canonical path inside the managed root
    planned_bytes: int

    @property
    def asset_count(self) -> int:
        return len(self.asset_rows)


@dataclass
class StagingResult:
    ok: bool
    staged: dict[str, Path] = field(default_factory=dict)     # clip_id -> quarantine path
    originals: dict[str, Path] = field(default_factory=dict)  # clip_id -> original path
    failed: dict[str, str] = field(default_factory=dict)      # clip_id -> reason (only when not ok)


@dataclass
class PurgeResult:
    purged: dict[str, int] = field(default_factory=dict)      # clip_id -> bytes reclaimed
    deferred: dict[str, str] = field(default_factory=dict)    # clip_id -> reason, left in quarantine


@dataclass(frozen=True)
class PermanentDeleteResult:
    requested_ids: tuple[str, ...]
    eligible_ids: tuple[str, ...]
    deleted_ids: tuple[str, ...]
    skipped: dict[str, str]
    failed: dict[str, str]
    managed_assets_deleted: int
    managed_files_deferred: int
    disk_bytes_reclaimed: int
    complete: bool

    @property
    def requested_count(self) -> int:
        return len(self.requested_ids)

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_ids)


class _StagingFailure(Exception):
    def __init__(self, clip_id: str, reason: str):
        super().__init__(reason)
        self.clip_id = clip_id
        self.reason = reason


def build_deletion_plan(storage, clip_ids: list[str]) -> DeletionPlan:
    """Read-only preflight: dedupe, validate eligibility, and resolve each
    eligible clip's managed-asset path -- never mutates anything.

    A clip is eligible only when it still exists and ``deleted_at IS NOT
    NULL`` (i.e. it's genuinely in Recently Removed right now). A clip
    whose asset row resolves to a path outside the managed assets root
    (rejected by ``image_assets.resolve_managed_path``) is excluded
    entirely rather than deleting its database row while leaving an
    asset we refuse to touch dangling -- see the module docstring.
    """
    from . import image_assets

    requested = dedupe_preserve_order(clip_ids)
    eligible: list[str] = []
    skipped: dict[str, str] = {}
    asset_rows: dict[str, object] = {}
    managed_paths: dict[str, Path] = {}
    planned_bytes = 0

    for cid in requested:
        clip = storage.get_clip(cid)
        if clip is None:
            skipped[cid] = "missing"
            continue
        if clip.deleted_at is None:
            skipped[cid] = "not_in_recently_removed"
            continue

        asset = storage.get_asset_record(cid)
        if asset is not None:
            path = image_assets.resolve_managed_path(asset.storage_name)
            if path is None:
                skipped[cid] = "unsafe_asset_path"
                continue
            asset_rows[cid] = asset
            managed_paths[cid] = path
            planned_bytes += asset.size_bytes

        eligible.append(cid)

    return DeletionPlan(
        requested_ids=tuple(requested),
        eligible_ids=tuple(eligible),
        skipped=skipped,
        asset_rows=asset_rows,
        managed_paths=managed_paths,
        planned_bytes=planned_bytes,
    )


def stage_managed_files(plan: DeletionPlan) -> StagingResult:
    """Atomically move every managed asset file in the plan into a fresh
    quarantine subdirectory. All-or-nothing: if any file can't be staged,
    every file already staged in this call is moved back before
    returning, and the database is never touched.
    """
    from . import image_assets

    if not plan.managed_paths:
        return StagingResult(ok=True)

    run_dir = image_assets.deletion_quarantine_dir() / models.new_id()
    run_dir.mkdir(parents=True, exist_ok=True)

    staged: dict[str, Path] = {}
    originals: dict[str, Path] = {}
    try:
        for cid, original in plan.managed_paths.items():
            if not original.is_file():
                raise _StagingFailure(cid, "asset_file_missing")
            dest = run_dir / original.name
            os.replace(original, dest)
            staged[cid] = dest
            originals[cid] = original
    except _StagingFailure as exc:
        _restore_pairs(staged, originals)
        return StagingResult(ok=False, failed={exc.clip_id: exc.reason})
    except OSError as exc:
        failing_id = next(
            (c for c in plan.managed_paths if c not in staged), "unknown",
        )
        _restore_pairs(staged, originals)
        return StagingResult(ok=False, failed={failing_id: str(exc)})

    return StagingResult(ok=True, staged=staged, originals=originals)


def _restore_pairs(staged: dict[str, Path], originals: dict[str, Path]) -> None:
    for cid in reversed(list(staged)):
        dest = staged[cid]
        original = originals[cid]
        if dest.is_file():
            os.replace(dest, original)


def unstage_files(staging: StagingResult, clip_ids) -> None:
    """Move specific already-staged files back to their original
    location -- used both for a full database-failure rollback and for
    un-staging just the ids that a partial commit skipped (e.g. a clip
    that was restored by another window between staging and commit)."""
    for cid in clip_ids:
        if cid not in staging.staged:
            continue
        dest = staging.staged[cid]
        original = staging.originals[cid]
        if dest.is_file():
            os.replace(dest, original)


def purge_staged_files(staging: StagingResult, clip_ids) -> PurgeResult:
    """Permanently remove staged files whose database rows are actually
    gone. Only called after a successful commit. A file that fails to
    unlink is left in quarantine (for retry) and reported as deferred --
    never counted toward bytes reclaimed, and the already-committed
    database change is never rolled back for this.
    """
    purged: dict[str, int] = {}
    deferred: dict[str, str] = {}
    run_dirs: set[Path] = set()
    for cid in clip_ids:
        if cid not in staging.staged:
            continue
        dest = staging.staged[cid]
        run_dirs.add(dest.parent)
        try:
            size = dest.stat().st_size
            dest.unlink()
            purged[cid] = size
        except OSError as exc:
            deferred[cid] = str(exc)

    # Best-effort housekeeping only -- a run directory that fails to
    # remove (e.g. a deferred file still inside it) is left in place for
    # the next retry; this never affects purged/deferred accounting.
    for run_dir in run_dirs:
        try:
            run_dir.rmdir()
        except OSError:
            pass

    return PurgeResult(purged=purged, deferred=deferred)


def record_permanent_delete_receipt(
    events,
    *,
    plan: DeletionPlan,
    result: PermanentDeleteResult,
    confirmation_mode: str,
) -> None:
    """Write a file receipt and event for a completed permanent-deletion
    batch. Only ever called after the database transaction has actually
    committed at least one row -- a staging failure or a full database
    rollback never reaches this function, so there is no receipt for a
    batch that didn't really happen (see ``Vault.permanently_delete_many``).
    """
    bounded_ids = list(result.deleted_ids)[:1000]
    bounded_hashes = [
        plan.asset_rows[cid].sha256
        for cid in result.deleted_ids
        if cid in plan.asset_rows
    ][:1000]
    body = {
        "action": models.ACTION_PERMANENT_DELETE_BATCH,
        "source_context": "recently_removed",
        "timestamp": models.now_iso(),
        "confirmation_mode": confirmation_mode,
        "requested_count": result.requested_count,
        "eligible_count": len(result.eligible_ids),
        "deleted_count": result.deleted_count,
        "skipped_count": len(result.skipped),
        "failed_count": len(result.failed),
        "managed_assets_deleted": result.managed_assets_deleted,
        "managed_files_deferred": result.managed_files_deferred,
        "disk_bytes_reclaimed": result.disk_bytes_reclaimed,
        "clip_ids": bounded_ids,
        "clip_id_count": result.deleted_count,
        "asset_hashes": bounded_hashes,
        "result": "complete" if result.complete else "partial",
    }
    write_file_receipt(models.ACTION_PERMANENT_DELETE_BATCH, body)
    events.record(models.EVENT_PERMANENT_DELETE_BATCH, None, body)
