"""Clip metadata helpers — title, URL, size, normalized hash."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import models

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def normalized_hash(content: str) -> str:
    """Hash after safe normalization for possible-duplicate detection."""
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip().casefold()
    return models.content_hash(text)


def clip_title(content: str, preview: str, *, max_len: int = 80) -> str:
    """First-line title for cards/grid."""
    raw = (content or preview or "").strip()
    if not raw:
        return "(empty)"
    line = raw.splitlines()[0].strip()
    if len(line) > max_len:
        return line[: max_len - 1].rstrip() + "…"
    return line


def extract_source_url(content: str, classification: str) -> str | None:
    if classification == models.CLASS_LINK:
        url = content.strip()
        return url if url.startswith(("http://", "https://")) else None
    m = _URL_RE.search(content or "")
    return m.group(0).rstrip(").,]") if m else None


def source_domain(source_url: str | None) -> str | None:
    if not source_url:
        return None
    try:
        host = urlparse(source_url).netloc
        return host.lower().lstrip("www.") or None
    except Exception:  # noqa: BLE001
        return None


def size_bytes_for(content: str) -> int:
    return len((content or "").encode("utf-8", "replace"))


def format_label(classification: str, content_type: str) -> str:
    if content_type == models.CONTENT_IMAGE:
        return "Screenshot"
    return {
        models.CLASS_LINK: "Link",
        models.CLASS_PATH: "Path",
        models.CLASS_CODE: "Code",
        models.CLASS_COMMAND: "Command",
        models.CLASS_EMAIL: "Email",
        models.CLASS_PHONE: "Phone",
        models.CLASS_IMAGE: "Image",
    }.get(classification, "Text")


def shorten_hash(value: str) -> str:
    value = (value or "").strip()
    if len(value) <= 12:
        return value or "—"
    return f"{value[:4]}…{value[-5:]}"
