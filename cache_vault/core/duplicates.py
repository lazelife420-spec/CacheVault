"""Duplicate detection and review actions."""

from __future__ import annotations

from dataclasses import dataclass

from . import clip_metadata, models
from .events import EventLog
from .models import Clip
from .storage import VaultStorage


@dataclass
class DuplicateGroup:
    """Clips sharing the same content hash (exact duplicates)."""

    group_id: str
    kind: str  # "exact" or "possible"
    content_hash: str
    normalized_hash: str | None
    clips: list[Clip]

    @property
    def count(self) -> int:
        return len(self.clips)


def _live_clips(storage: VaultStorage) -> list[Clip]:
    return storage.list_clips()


def find_exact_duplicate_groups(storage: VaultStorage) -> list[DuplicateGroup]:
    """Group live clips by exact content_hash when count > 1."""
    by_hash: dict[str, list[Clip]] = {}
    for clip in _live_clips(storage):
        if not clip.content_hash:
            continue
        by_hash.setdefault(clip.content_hash, []).append(clip)
    groups: list[DuplicateGroup] = []
    for chash, clips in by_hash.items():
        if len(clips) < 2:
            continue
        clips.sort(key=lambda c: c.created_at, reverse=True)
        groups.append(
            DuplicateGroup(
                group_id=chash,
                kind="exact",
                content_hash=chash,
                normalized_hash=clips[0].normalized_hash,
                clips=clips,
            )
        )
    groups.sort(key=lambda g: g.clips[0].created_at, reverse=True)
    return groups


def find_possible_duplicate_groups(storage: VaultStorage) -> list[DuplicateGroup]:
    """Group live text clips by normalized_hash when hashes differ but normalize same."""
    by_norm: dict[str, list[Clip]] = {}
    for clip in _live_clips(storage):
        if clip.content_type == models.CONTENT_IMAGE:
            continue
        norm = clip.normalized_hash or clip_metadata.normalized_hash(clip.content)
        if not norm:
            continue
        by_norm.setdefault(norm, []).append(clip)
    groups: list[DuplicateGroup] = []
    for norm, clips in by_norm.items():
        if len(clips) < 2:
            continue
        exact_hashes = {c.content_hash for c in clips}
        if len(exact_hashes) < 2:
            continue
        clips.sort(key=lambda c: c.created_at, reverse=True)
        groups.append(
            DuplicateGroup(
                group_id=norm,
                kind="possible",
                content_hash=clips[0].content_hash,
                normalized_hash=norm,
                clips=clips,
            )
        )
    return groups


def count_duplicate_groups(storage: VaultStorage) -> int:
    return storage.count_duplicate_groups()



def duplicate_label(group: DuplicateGroup) -> str:
    return "Exact Duplicate" if group.kind == "exact" else "Possible Duplicate"


def _pick_keep_newest(clips: list[Clip]) -> Clip:
    return max(clips, key=lambda c: c.created_at)


def _pick_keep_oldest(clips: list[Clip]) -> Clip:
    return min(clips, key=lambda c: c.created_at)


def _pick_keep_most_used(clips: list[Clip]) -> Clip:
    return max(clips, key=lambda c: (c.use_count, c.created_at))


def _pick_keep_favorite(clips: list[Clip]) -> Clip:
    favs = [c for c in clips if c.is_pinned]
    if favs:
        return max(favs, key=lambda c: c.created_at)
    return _pick_keep_newest(clips)


def _merge_usage_into(storage: VaultStorage, keeper: Clip, others: list[Clip]) -> None:
    """Sum use counts and widen date range on the kept clip."""
    total_use = keeper.use_count + sum(c.use_count for c in others)
    total_copied = keeper.copied_count + sum(c.copied_count for c in others)
    first_saved = min([keeper.created_at] + [c.created_at for c in others])
    last_used_vals = [keeper.date_used or keeper.created_at]
    last_used_vals.extend(c.date_used or c.created_at for c in others)
    last_used = max(last_used_vals)
    storage.conn.execute(
        "UPDATE clips SET use_count = ?, copied_count = ?, "
        "created_at = ?, last_used_at = ?, updated_at = ? WHERE id = ?",
        (total_use, total_copied, first_saved, last_used, models.now_iso(), keeper.id),
    )
    storage.conn.commit()


def apply_duplicate_review(
    storage: VaultStorage,
    events: EventLog,
    group: DuplicateGroup,
    action: str,
    *,
    merge_history: bool = False,
) -> str:
    """Resolve a duplicate group. Returns id of kept clip (or '' for keep_all)."""
    clips = list(group.clips)
    if action == "keep_all":
        events.record(
            models.EVENT_DUPLICATE_REVIEW,
            None,
            {
                "action": action,
                "group_id": group.group_id,
                "kind": group.kind,
                "count": len(clips),
                "hash": clip_metadata.shorten_hash(group.content_hash),
            },
        )
        return ""

    pickers = {
        "keep_newest": _pick_keep_newest,
        "keep_oldest": _pick_keep_oldest,
        "keep_most_used": _pick_keep_most_used,
        "keep_favorite": _pick_keep_favorite,
    }
    picker = pickers.get(action, _pick_keep_newest)
    keeper = picker(clips)
    extras = [c for c in clips if c.id != keeper.id]

    if merge_history:
        _merge_usage_into(storage, keeper, extras)
        events.record(
            models.EVENT_USAGE_MERGED,
            keeper.id,
            {"from_ids": [c.id for c in extras], "group_id": group.group_id},
        )

    for extra in extras:
        if extra.is_pinned and keeper.id != extra.id:
            # Never auto-unfavorite; if favorite is extra, keep it pinned on keeper.
            storage.set_pinned(keeper.id, True)
        storage.soft_delete(extra.id)

    events.record(
        models.EVENT_DUPLICATE_REVIEW,
        keeper.id,
        {
            "action": action,
            "group_id": group.group_id,
            "kind": group.kind,
            "kept": keeper.id,
            "removed": [c.id for c in extras],
            "merge_history": merge_history,
            "hash": clip_metadata.shorten_hash(group.content_hash),
        },
    )
    return keeper.id


def move_extras_to_recently_removed(
    storage: VaultStorage,
    events: EventLog,
    group: DuplicateGroup,
    keeper_id: str,
) -> None:
    """Soft-delete all clips in the group except keeper."""
    for clip in group.clips:
        if clip.id != keeper_id:
            storage.soft_delete(clip.id)
    events.record(
        models.EVENT_DUPLICATE_REVIEW,
        keeper_id,
        {
            "action": "move_extras_removed",
            "group_id": group.group_id,
            "kind": group.kind,
            "hash": clip_metadata.shorten_hash(group.content_hash),
        },
    )
