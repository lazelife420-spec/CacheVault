"""Receipt and event for the Clear All Clips bulk action."""

from __future__ import annotations

from . import models
from .editable_copies import write_file_receipt


def record_clear_all_clips_receipt(
    events,
    *,
    moved_count: int,
    skipped_count: int,
    clip_ids: list[str],
) -> None:
    """Write one summary receipt/event for a successful Clear All Clips.

    The receipt states explicitly that the action is recoverable and that
    nothing was destroyed: Clear All Clips only sets ``deleted_at``, so no
    clip row, managed asset, or byte on disk is removed. Clip ids are
    bounded to the first 1000 affected ids to avoid unbounded receipt
    growth (matching the Empty Collection receipt); the counts stay exact.

    One summary receipt is written in addition to -- not instead of -- the
    per-clip ``EVENT_DELETED`` rows that ``Vault.remove_from_history_many``
    already records, so per-clip audit granularity is preserved while the
    ledger still shows the bulk action as a single reviewable entry.
    """
    bounded_ids = clip_ids[:1000]
    body = {
        "action": models.ACTION_CLEAR_ALL_CLIPS,
        "timestamp": models.now_iso(),
        "outcome": "success",
        "recoverable": True,
        "destination": "recently_removed",
        "moved_to_recently_removed": moved_count,
        "skipped_count": skipped_count,
        "clip_ids": bounded_ids,
        "clip_id_count": len(clip_ids),
        "clips_deleted": 0,
        "assets_deleted": 0,
        "disk_bytes_reclaimed": 0,
    }
    write_file_receipt(models.ACTION_CLEAR_ALL_CLIPS, body)
    events.record(models.EVENT_CLEARED_ALL_CLIPS, None, body)
