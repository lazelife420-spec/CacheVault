"""Search-query parsing and date-range helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

from . import models

_TYPE_ALIASES = {
    "link": models.CLASS_LINK,
    "url": models.CLASS_LINK,
    "links": models.CLASS_LINK,
    "path": models.CLASS_PATH,
    "file": models.CLASS_PATH,
    "files": models.CLASS_PATH,
    "code": models.CLASS_CODE,
    "command": models.CLASS_COMMAND,
    "cmd": models.CLASS_COMMAND,
    "commands": models.CLASS_COMMAND,
    "email": models.CLASS_EMAIL,
    "emails": models.CLASS_EMAIL,
    "phone": models.CLASS_PHONE,
    "phones": models.CLASS_PHONE,
    "plain": models.CLASS_PLAIN,
    "text": models.CLASS_PLAIN,
    "image": models.CLASS_IMAGE,
    "screenshot": models.CLASS_IMAGE,
}

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}

_TOKEN_RE = re.compile(r"(\w+):(\S+)")


@dataclass
class SearchQuery:
    filter_name: str = "all"
    text: str = ""
    type_filter: str | None = None
    source: str | None = None
    window: str | None = None
    source_url: str | None = None
    domain: str | None = None
    collection: str | None = None
    sensitive: bool | None = None
    pinned: bool | None = None
    duplicate_only: bool | None = None
    sort: str = models.SORT_NEWEST_ADDED
    date_added_preset: str | None = None
    date_used_preset: str | None = None
    date_added_start: str | None = None
    date_added_end: str | None = None
    date_used_start: str | None = None
    date_used_end: str | None = None


def _to_bool(value: str) -> bool | None:
    v = value.lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


def parse(raw: str, filter_name: str = "all") -> SearchQuery:
    """Turn a raw search string into a :class:`SearchQuery`."""
    query = SearchQuery(filter_name=filter_name)
    if not raw:
        return query

    free_terms: list[str] = []
    pos = 0
    for m in _TOKEN_RE.finditer(raw):
        free_terms.append(raw[pos:m.start()])
        pos = m.end()
        key, value = m.group(1).lower(), m.group(2)
        if key == "type" and value.lower() in _TYPE_ALIASES:
            query.type_filter = _TYPE_ALIASES[value.lower()]
        elif key == "source":
            query.source = value
        elif key == "window":
            query.window = value
        elif key in ("url", "domain"):
            query.domain = value
        elif key == "collection":
            query.collection = value
        elif key == "sensitive":
            b = _to_bool(value)
            if b is None:
                free_terms.append(m.group(0))
            else:
                query.sensitive = b
        elif key == "pinned":
            b = _to_bool(value)
            if b is None:
                free_terms.append(m.group(0))
            else:
                query.pinned = b
        elif key == "duplicate":
            b = _to_bool(value)
            if b is None:
                free_terms.append(m.group(0))
            else:
                query.duplicate_only = b
        else:
            free_terms.append(m.group(0))
    free_terms.append(raw[pos:])

    query.text = " ".join(" ".join(free_terms).split()).strip()
    return query


def preset_bounds(preset: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) for a named date preset."""
    if not preset:
        return None, None
    now = models.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    preset = preset.lower().replace(" ", "_")
    if preset == "today":
        return today_start.isoformat(), None
    if preset == "yesterday":
        y = today_start - timedelta(days=1)
        return y.isoformat(), today_start.isoformat()
    if preset in ("this_week", "week"):
        monday = today_start - timedelta(days=today_start.weekday())
        return monday.isoformat(), None
    if preset in ("last_7_days", "last7"):
        return (today_start - timedelta(days=7)).isoformat(), None
    if preset in ("this_month", "month"):
        month_start = today_start.replace(day=1)
        return month_start.isoformat(), None
    if preset in ("last_30_days", "last30"):
        return (today_start - timedelta(days=30)).isoformat(), None
    if preset == "older":
        monday = today_start - timedelta(days=today_start.weekday())
        return None, monday.isoformat()
    return None, None


def sort_sql(sort_key: str) -> str:
    """ORDER BY clause for clip listing."""
    key = sort_key or models.SORT_NEWEST_ADDED
    mapping = {
        models.SORT_NEWEST_ADDED: "created_at DESC, rowid DESC",
        models.SORT_OLDEST_ADDED: "created_at ASC, rowid ASC",
        models.SORT_RECENTLY_USED: "COALESCE(last_used_at, updated_at) DESC, rowid DESC",
        models.SORT_OLDEST_USED: "COALESCE(last_used_at, updated_at) ASC, rowid ASC",
        models.SORT_MOST_USED: "use_count DESC, created_at DESC",
        models.SORT_LEAST_USED: "use_count ASC, created_at ASC",
        models.SORT_LARGEST: "size_bytes DESC, created_at DESC",
        models.SORT_SMALLEST: "size_bytes ASC, created_at ASC",
        models.SORT_SOURCE: "LOWER(COALESCE(source_app,'')) ASC, created_at DESC",
        models.SORT_TYPE: "classification ASC, created_at DESC",
        models.SORT_COLLECTION: "LOWER(COALESCE(collection,'')) ASC, created_at DESC",
        models.SORT_FAVORITES_FIRST: "is_pinned DESC, created_at DESC, rowid DESC",
        models.SORT_DUPLICATES_FIRST: (
            "(content_hash IN (SELECT content_hash FROM clips "
            "WHERE deleted_at IS NULL GROUP BY content_hash HAVING COUNT(*) > 1)) "
            "DESC, created_at DESC"
        ),
    }
    return mapping.get(key, mapping[models.SORT_NEWEST_ADDED])
