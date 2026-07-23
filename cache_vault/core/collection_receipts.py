"""Receipts and events for collection bulk actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import models
from .editable_copies import write_file_receipt

if TYPE_CHECKING:
    from .events import EventLog


def record_empty_collection_receipt(
    events,
    *,
    collection_name: str,
    membership_removed: int,
    skipped_count: int,
    clip_ids: list[str],
) -> None:
    """Write a file receipt and event for a successful Empty Collection.

    The receipt emphasizes that clips remain in the vault and that zero
    clips/assets/bytes were deleted, because Empty Collection only strips
    a label. Clip ids are bounded to the first 1000 affected ids to avoid
    unbounded receipt growth; the counts remain exact.
    """
    bounded_ids = clip_ids[:1000]
    body = {
        "action": models.ACTION_EMPTY_COLLECTION,
        "timestamp": models.now_iso(),
        "collection_name": collection_name,
        "membership_removed": membership_removed,
        "skipped_count": skipped_count,
        "clip_ids": bounded_ids,
        "clip_id_count": len(clip_ids),
        "clips_deleted": 0,
        "assets_deleted": 0,
        "disk_bytes_reclaimed": 0,
    }
    body = {k: v for k, v in body.items() if v is not None}
    write_file_receipt(models.ACTION_EMPTY_COLLECTION, body)
    events.record(
        models.EVENT_EMPTIED_COLLECTION,
        None,
        body,
    )
