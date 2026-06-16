"""Read-only mobile API — route table and clip serialization."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .. import models, search
from ..storage import (
    FILTER_ALL,
    FILTER_FAVORITES,
    FILTER_RECENTLY_REMOVED,
    FILTER_SEARCH_ALL,
)
from .models import MobileAccessReceipt

# Read-only GET routes (MVP). No delete/edit/permanent-remove routes exist.
READ_ONLY_ROUTES = frozenset({
    "/mobile/v1/status",
    "/mobile/v1/clips",
    "/mobile/v1/search",
    "/mobile/v1/collections",
    "/mobile/v1/favorites",
    "/mobile/v1/recently-removed",
})

CLIP_ID_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)$")

FORBIDDEN_ROUTE_PARTS = frozenset({
    "delete", "permanent", "remove", "edit", "restore", "capture", "export",
})


def route_family(path: str) -> str | None:
    """Return the matched route family, or None if unknown."""
    if path in READ_ONLY_ROUTES:
        return path
    if CLIP_ID_RE.match(path):
        return "/mobile/v1/clips/{id}"
    return None


def is_forbidden_route(path: str) -> bool:
    low = path.lower()
    return any(part in low for part in FORBIDDEN_ROUTE_PARTS)


def clip_to_api(clip: models.Clip) -> dict:
    """Serialize a clip for mobile clients. Sensitive content is never exposed."""
    return {
        "id": clip.id,
        "preview": clip.preview,
        "content": "" if clip.is_sensitive else (clip.content or ""),
        "classification": clip.classification,
        "content_type": clip.content_type,
        "source_app": clip.source_app,
        "source_window": clip.source_window,
        "created_at": clip.created_at,
        "updated_at": clip.updated_at,
        "is_favorite": bool(clip.is_pinned),
        "is_sensitive": bool(clip.is_sensitive),
        "collection": clip.collection,
        "deleted_at": clip.deleted_at,
    }


def parse_query(path: str) -> tuple[str, dict[str, list[str]]]:
    parsed = urlparse(path)
    return parsed.path, parse_qs(parsed.query)


def action_for_route(route_family: str, method: str) -> str:
    mapping = {
        "/mobile/v1/status": "status",
        "/mobile/v1/clips": "list_clips",
        "/mobile/v1/clips/{id}": "get_clip",
        "/mobile/v1/search": "search",
        "/mobile/v1/collections": "list_collections",
        "/mobile/v1/favorites": "list_favorites",
        "/mobile/v1/recently-removed": "list_recently_removed",
    }
    return mapping.get(route_family, method.lower())


def reject_receipt(route: str, action: str, result: str, reason: str,
                   device_id: str | None = None,
                   device_name: str | None = None,
                   clip_id: str | None = None) -> MobileAccessReceipt:
    return MobileAccessReceipt.make(
        action=action, route=route, result=result, reason=reason,
        device_id=device_id, device_name=device_name, clip_id=clip_id,
    )
