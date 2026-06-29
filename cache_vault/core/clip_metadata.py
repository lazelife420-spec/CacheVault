"""Clip metadata helpers — title, URL, size, normalized hash."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import models
from .mobile import models as mobile_models

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
        return host.lower().removeprefix("www.") or None
    except Exception:  # noqa: BLE001
        return None


def size_bytes_for(content: str) -> int:
    return len((content or "").encode("utf-8", "replace"))


def format_label(classification: str | None, content_type: str | None) -> str:
    if str(content_type or "").startswith("image"):
        return "Screenshot"
    if isinstance(classification, str) and "screen" in classification.lower():
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


def display(value: str | None, *, fallback: str = "—") -> str:
    """Safe display for missing metadata — never show None."""
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def human_timestamp(iso: str) -> str:
    """Format ISO timestamp into a human-readable string.

    Example outputs:
    - Today · 1:24 PM
    - Yesterday · 8:13 PM
    - Jun 27 · 10:27 PM
    - Dec 12, 2023 · 9:00 AM
    """
    from datetime import datetime

    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        return iso[:16].replace("T", " ")

    # Normalize 'now' to match dt's timezone-awareness
    if dt.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(dt.tzinfo)

    time_str = dt.strftime("%I:%M %p").lstrip("0")
    if now.date() == dt.date():
        return f"Today · {time_str}"
    
    from datetime import timedelta
    if (now.date() - dt.date()) == timedelta(days=1):
        return f"Yesterday · {time_str}"
    
    if now.year == dt.year:
        return f"{dt.strftime('%b %d')} · {time_str}"
    
    return f"{dt.strftime('%b %d, %Y')} · {time_str}"


def date_group_header(iso: str) -> str:
    """Return a header label for date grouping (Today, Yesterday, Jun 27)."""
    from datetime import datetime, timedelta

    if not iso:
        return "Older"
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        return "Older"

    if dt.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(dt.tzinfo)

    if now.date() == dt.date():
        return "Today"
    if (now.date() - dt.date()) == timedelta(days=1):
        return "Yesterday"
    if now.year == dt.year:
        return dt.strftime("%b %d")
    return dt.strftime("%b %d, %Y")


def status_badges(clip, storage=None) -> list[str]:
    """Derive status badges based on real data.

    - On PC: Asset exists in local storage
    - From Phone: Captured via mobile share
    - Saved to Phone: Explicitly marked as saved to mobile device
    - Proof Recorded: Content hash exists
    - LAN paired: Device currently paired over local network (placeholder for D4)
    """
    badges = mobile_models.pc_status_labels(clip, storage=storage)
    if getattr(clip, "content_hash", None):
        badges.append("Proof Recorded")

    return badges


def _time_bucket(iso: str) -> str:
    """Bucket an ISO timestamp into Today/Yesterday/This Week/Older."""
    from datetime import datetime, timedelta

    if not iso:
        return "Older"
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
        except Exception:
            return "Older"
    # Normalize 'now' to match dt's timezone-awareness
    if dt.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(dt.tzinfo)
    delta = now - dt
    if delta < timedelta(days=1) and now.date() == dt.date():
        return "Today"
    if delta < timedelta(days=2) and (now.date() - dt.date()) == timedelta(days=1):
        return "Yesterday"
    if delta < timedelta(days=7):
        return "This Week"
    return "Older"


def labels_for_clip(clip, ctx: dict | None = None) -> list[str]:
    """Deterministically derive short labels for a clip from metadata.

    Uses only existing metadata and the optional context dict (receipt counts,
    export flags). Does not infer or guess beyond available fields.
    """
    labels: list[str] = []
    # Type label — prefer explicit image typing when available
    cls = getattr(clip, "classification", None)
    ct = getattr(clip, "content_type", None)
    # If content_type explicitly indicates an image, prefer that
    if isinstance(ct, str) and ct.startswith("image"):
        ct = models.CONTENT_IMAGE
    # Handle loose classification values like 'screenshot' or 'screen' as images
    elif isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower()):
        ct = models.CONTENT_IMAGE
    # Preserve explicit model constant mapping as well
    elif cls == models.CLASS_IMAGE and not ct:
        ct = models.CONTENT_IMAGE
    typ = format_label(cls, ct)
    labels.append(typ)

    # Source app / capture mode
    src = getattr(clip, "source_app", None) or getattr(clip, "capture_mode", None)
    if src:
        s = str(src)
        # Map common apps to friendly labels
        if "chrome" in s.lower() or "edge" in s.lower() or "browser" in s.lower():
            labels.append("Browser")
            if "chrome" in s.lower():
                labels.append("Chrome")
        elif "android" in s.lower() or "mobile" in s.lower():
            labels.append("Android Share")
        else:
            # Short source app name
            labels.append(s.split(".")[0])
    mode = getattr(clip, "capture_mode", None)
    if mode in (models.CAPTURE_MOBILE, models.CAPTURE_MOBILE_SHARE):
        mobile_label = "Android Share" if mode == models.CAPTURE_MOBILE_SHARE else "Mobile"
        if mobile_label not in labels:
            labels.append(mobile_label)

    # Time bucket label
    tb = _time_bucket(getattr(clip, "created_at", None))
    labels.append(tb)

    # Favorite
    if getattr(clip, "is_pinned", False):
        labels.append("Favorite")

    # Duplicate
    if getattr(clip, "duplicate_of", None):
        labels.append("Duplicate")

    # Receipts
    if ctx and ctx.get("receipt_count", 0):
        labels.append("Has Receipt")

    # Saved/exported state
    if ctx and ctx.get("export_ready"):
        labels.append("Exported")

    # Sensitive
    if getattr(clip, "is_sensitive", False):
        labels.append("Sensitive")

    return labels
