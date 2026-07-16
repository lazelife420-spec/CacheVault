"""Deterministic smart folders — type/source/recency grouping without AI."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from . import models

if TYPE_CHECKING:
    from .storage import VaultStorage

SMART_PREFIX = "smart:"

# Folder definitions exposed in the sidebar SMART FOLDERS section.
SMART_FOLDER_DEFS: tuple[dict[str, str], ...] = (
    {"id": "recent", "label": "Recent", "hint": "Saved or used in the last 7 days"},
    {"id": "unused", "label": "Unused", "hint": "Never pasted from the vault"},
    {"id": "mobile_share", "label": "From Phone", "hint": "Android Share Sheet sends"},
    {"id": "text", "label": "Plain Text", "hint": "General text clips"},
    {"id": "url", "label": "URLs", "hint": "Links and web addresses"},
    {"id": "image", "label": "Images", "hint": "Screenshots and image clips"},
    {"id": "code", "label": "Code", "hint": "Code snippets"},
    {"id": "manual", "label": "Manual Saves", "hint": "Saved via Save to Vault or Save next copy"},
)


def filter_key(folder_id: str) -> str:
    return f"{SMART_PREFIX}{folder_id}"


SMART_FOLDER_NAV: list[tuple[str, str]] = [
    (filter_key(d["id"]), d["label"]) for d in SMART_FOLDER_DEFS
]


def folder_id_from_key(key: str) -> str | None:
    if not key.startswith(SMART_PREFIX):
        return None
    return key[len(SMART_PREFIX):]


def is_smart_filter(key: str) -> bool:
    return key.startswith(SMART_PREFIX)


def folder_label(folder_id: str) -> str:
    for d in SMART_FOLDER_DEFS:
        if d["id"] == folder_id:
            return d["label"]
    return folder_id.replace("_", " ").title()


def export_collection_name(filter_key_value: str) -> str | None:
    fid = folder_id_from_key(filter_key_value)
    if not fid:
        return None
    return f"Smart Folder — {folder_label(fid)}"


def _cutoff_days(days: int) -> str:
    return (models.utcnow() - timedelta(days=days)).isoformat()


def apply_smart_folder_filter(folder_id: str, where: list[str], params: list) -> None:
    """Append SQL predicates for a smart folder id."""
    if folder_id == "recent":
        cutoff = _cutoff_days(7)
        where.append(
            "(created_at >= ? OR COALESCE(last_used_at, '') >= ?)"
        )
        params.extend([cutoff, cutoff])
    elif folder_id == "unused":
        where.append("COALESCE(use_count, 0) = 0")
    elif folder_id == "mobile_share":
        where.append("capture_mode = ?")
        params.append(models.CAPTURE_MOBILE_SHARE)
    elif folder_id == "text":
        where.append(
            "(classification = ? OR (content_type = ? AND classification NOT IN (?, ?, ?, ?)))"
        )
        params.extend([
            models.CLASS_PLAIN,
            models.CONTENT_TEXT,
            models.CLASS_LINK,
            models.CLASS_CODE,
            models.CLASS_PATH,
            models.CLASS_IMAGE,
        ])
    elif folder_id == "url":
        where.append("classification = ?")
        params.append(models.CLASS_LINK)
    elif folder_id == "image":
        where.append("(classification = ? OR content_type = ?)")
        params.append(models.CLASS_IMAGE)
        params.append(models.CONTENT_IMAGE)
    elif folder_id == "code":
        where.append("classification = ?")
        params.append(models.CLASS_CODE)
    elif folder_id == "manual":
        where.append("capture_mode IN (?, ?)")
        params.extend([
            models.CAPTURE_MANUAL_SAVE_HOTKEY,
            models.CAPTURE_ARMED_NEXT_COPY,
        ])
    else:
        where.append("1 = 0")


def count_folder(storage: VaultStorage, folder_id: str, conn=None) -> int:
    where = ["deleted_at IS NULL"]
    params: list = []
    apply_smart_folder_filter(folder_id, where, params)
    sql = f"SELECT COUNT(*) FROM clips WHERE {' AND '.join(where)}"
    return int((conn or storage.conn).execute(sql, params).fetchone()[0])


def count_all(storage: VaultStorage, conn=None) -> dict[str, int]:
    return {
        filter_key(d["id"]): count_folder(storage, d["id"], conn=conn)
        for d in SMART_FOLDER_DEFS
    }


def folder_receipt(
    folder_id: str,
    count: int,
    *,
    generated_at: str | None = None,
) -> dict:
    """Snapshot receipt for a smart folder (timestamp + count)."""
    return {
        "receipt_type": "smart_folder_snapshot",
        "folder_id": folder_id,
        "filter_key": filter_key(folder_id),
        "label": folder_label(folder_id),
        "count": int(count),
        "generated_at": generated_at or models.now_iso(),
    }


def all_folder_receipts(storage: VaultStorage) -> dict:
    """Build receipt bundle for every smart folder."""
    counts = count_all(storage)
    generated_at = models.now_iso()
    folders = [
        folder_receipt(d["id"], counts.get(filter_key(d["id"]), 0), generated_at=generated_at)
        for d in SMART_FOLDER_DEFS
    ]
    return {
        "receipt_type": "smart_folder_bundle",
        "generated_at": generated_at,
        "folder_count": len(folders),
        "total_clips": sum(r["count"] for r in folders),
        "folders": folders,
    }
