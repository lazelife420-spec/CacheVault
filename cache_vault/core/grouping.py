from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from . import clip_metadata


def group_clips(clips: Iterable, by: str) -> dict[str, list]:
    """Group clips by a simple key: 'date' or 'source'.

    Returns an ordered mapping label -> list[clips].
    """
    groups = defaultdict(list)
    for clip in clips:
        if by == "date":
            key = clip_metadata._time_bucket(getattr(clip, "created_at", None))
        elif by == "source":
            key = (getattr(clip, "source_app", None) or getattr(clip, "capture_mode", None) or "Unknown")
        elif by == "type":
            key = clip_metadata.format_label(getattr(clip, "classification", None), getattr(clip, "content_type", None))
        else:
            key = "Other"
        groups[key].append(clip)
    # return as regular dict preserving insertion order of keys by sorted priority
    order = []
    if by == "date":
        order = ["Today", "Yesterday", "This Week", "Older"]
    else:
        order = sorted(groups.keys())
    ordered = {k: groups[k] for k in order if k in groups}
    # add any remaining keys
    for k in groups:
        if k not in ordered:
            ordered[k] = groups[k]
    return ordered
