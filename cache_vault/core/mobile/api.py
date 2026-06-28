"""Read-only mobile API — route table and clip serialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .. import models
from ..storage import VaultStorage
from .models import MobileAccessReceipt


@dataclass(frozen=True)
class BinaryResponse:
    """Binary HTTP body for image asset delivery (never logged or receipted)."""

    data: bytes
    content_type: str
    clip_id: str | None = None

# Read-only GET routes (MVP). No delete/edit/permanent-remove routes exist.
READ_ONLY_ROUTES = frozenset({
    "/mobile/v1/status",
    "/mobile/v1/clips",
    "/mobile/v1/search",
    "/mobile/v1/collections",
    "/mobile/v1/favorites",
    "/mobile/v1/recently-removed",
    "/mobile/v1/inbox",
})

CLIP_ID_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)$")
CLIP_ASSET_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)/asset$")
CLIP_COPY_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)/copy$")
CLIP_SHARE_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)/share$")
CLIP_SAVE_RE = re.compile(r"^/mobile/v1/clips/([a-f0-9]+)/save$")

# Receipt-only POST routes — log mobile copy/share/save; never mutate the vault.
RECEIPT_POST_ROUTES = frozenset({
    "/mobile/v1/clips/{id}/copy",
    "/mobile/v1/clips/{id}/share",
    "/mobile/v1/clips/{id}/save",
})

# Paired write routes — scoped mobile-to-PC inbox send only.
INBOX_POST_ROUTES = frozenset({
    "/mobile/v1/inbox/send",
})

INBOX_GET_ROUTES = frozenset({
    "/mobile/v1/inbox",
})

FORBIDDEN_ROUTE_PARTS = frozenset({
    "delete", "permanent", "remove", "edit", "restore", "capture", "export",
})


def route_family(path: str) -> str | None:
    """Return the matched route family, or None if unknown."""
    if path in READ_ONLY_ROUTES:
        return path
    if path in INBOX_POST_ROUTES:
        return path
    if CLIP_ID_RE.match(path):
        return "/mobile/v1/clips/{id}"
    if CLIP_ASSET_RE.match(path):
        return "/mobile/v1/clips/{id}/asset"
    if CLIP_COPY_RE.match(path):
        return "/mobile/v1/clips/{id}/copy"
    if CLIP_SHARE_RE.match(path):
        return "/mobile/v1/clips/{id}/share"
    if CLIP_SAVE_RE.match(path):
        return "/mobile/v1/clips/{id}/save"
    return None


def is_forbidden_route(path: str) -> bool:
    if path in READ_ONLY_ROUTES:
        return False
    low = path.lower()
    return any(part in low for part in FORBIDDEN_ROUTE_PARTS)


def clip_has_asset(clip: models.Clip, storage: VaultStorage | None = None) -> bool:
    """True when the vault stores a retrievable binary asset for this clip."""
    if storage is None:
        return False
    if clip.content_type != models.CONTENT_IMAGE:
        return False
    return storage.has_clip_asset(clip.id)


def clip_to_api(clip: models.Clip, *, full_content: bool = False,
                storage: VaultStorage | None = None) -> dict:
    """Serialize a clip for mobile clients.

    List/search endpoints omit sensitive full content (preview only).
    Clip detail returns full content for paired, authorized clients.
    """
    if full_content:
        content = clip.content or ""
    else:
        content = ""
    return {
        "id": clip.id,
        "preview": clip.preview,
        "content": content,
        "classification": clip.classification,
        "content_type": clip.content_type,
        "source_app": clip.source_app,
        "source_window": clip.source_window,
        "created_at": clip.created_at,
        "updated_at": clip.updated_at,
        "is_favorite": bool(clip.is_pinned),
        "is_sensitive": bool(clip.is_sensitive),
        "collection": clip.collection,
        "safe_id": clip.safe_id,
        "safe_name": clip.safe_name,
        "capture_mode": clip.capture_mode,
        "deleted_at": clip.deleted_at,
        "has_asset": clip_has_asset(clip, storage),
    }


def parse_query(path: str) -> tuple[str, dict[str, list[str]]]:
    parsed = urlparse(path)
    return parsed.path, parse_qs(parsed.query)


def action_for_route(route_family: str, method: str) -> str:
    mapping = {
        "/mobile/v1/status": "status",
        "/mobile/v1/clips": "list_clips",
        "/mobile/v1/clips/{id}": "get_clip",
        "/mobile/v1/clips/{id}/asset": "get_asset",
        "/mobile/v1/search": "search",
        "/mobile/v1/collections": "list_collections",
        "/mobile/v1/favorites": "list_favorites",
        "/mobile/v1/recently-removed": "list_recently_removed",
        "/mobile/v1/clips/{id}/copy": "copy",
        "/mobile/v1/clips/{id}/share": "share",
        "/mobile/v1/clips/{id}/save": "save",
        "/mobile/v1/inbox/send": "mobile_sent_to_pc",
        "/mobile/v1/inbox": "mobile_inbox_list",
    }
    return mapping.get(route_family, method.lower())


def reject_receipt(route: str, action: str, result: str, reason: str,
                   device_id: str | None = None,
                   device_name: str | None = None,
                   clip_id: str | None = None,
                   remote_ip: str | None = None) -> MobileAccessReceipt:
    return MobileAccessReceipt.make(
        action=action, route=route, result=result, reason=reason,
        device_id=device_id, device_name=device_name, clip_id=clip_id,
        remote_ip=remote_ip,
    )
