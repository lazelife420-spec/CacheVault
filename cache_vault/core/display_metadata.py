"""Unified display metadata, timezone conversion, and timestamp formatting for UI elements."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from cache_vault.core import models


def to_local_time(utc_iso: str) -> datetime:
    """Convert a UTC ISO timestamp (e.g. '2026-07-01T12:00:00Z') to local timezone."""
    if not utc_iso:
        return datetime.now().astimezone()
    # Standardize trailing Z to +00:00 for python's fromisoformat
    if utc_iso.endswith("Z"):
        utc_iso = utc_iso[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(utc_iso)
        return dt.astimezone()
    except Exception:
        return datetime.now().astimezone()


def format_display_time(utc_iso: str) -> str:
    """Format a UTC ISO timestamp as a user-friendly local date/time string.

    Examples:
        - "Today · 6:09 PM"
        - "Yesterday · 3:20 PM"
        - "Jun 30 · 8:33 PM"
    """
    if not utc_iso:
        return "Unknown time"
    try:
        local_dt = to_local_time(utc_iso)
        now = datetime.now().astimezone()

        local_date = local_dt.date()
        today_date = now.date()

        if local_date == today_date:
            time_label = "Today"
        elif local_date == today_date - timedelta(days=1):
            time_label = "Yesterday"
        else:
            time_label = local_dt.strftime("%b %d")

        # Format hour:minute AM/PM (e.g. "06:09 PM" -> "6:09 PM")
        hour_minute = local_dt.strftime("%I:%M %p")
        if hour_minute.startswith("0"):
            hour_minute = hour_minute[1:]

        return f"{time_label} · {hour_minute}"
    except Exception:
        return utc_iso


def get_origin_label(clip: Any) -> str:
    """Generate a clean origin and source application description for the clip.

    Examples:
        - "PC · Screenshot · CacheVault.exe"
        - "Android Share · From Phone"
        - "Chrome.exe · Link"
        - "Notepad.exe · Text"
    """
    capture_mode = getattr(clip, "capture_mode", None)
    classification = getattr(clip, "classification", None)
    content_type = getattr(clip, "content_type", None)
    source_app = getattr(clip, "source_app", None)
    source_window = getattr(clip, "source_window", None)

    # Mobile origins
    if capture_mode == models.CAPTURE_MOBILE_SHARE:
        return "Android Share · From Phone"
    elif capture_mode == models.CAPTURE_MOBILE:
        device = source_window or "From Phone"
        return f"Mobile Inbox · {device}"

    # Screenshot/Image
    if content_type == models.CONTENT_IMAGE or classification == models.CLASS_IMAGE:
        app_part = f" · {source_app}" if source_app else ""
        return f"PC · Screenshot{app_part}"

    # Link / Browser
    if classification == models.CLASS_LINK:
        app = source_app or "Browser"
        return f"{app} · Link"

    # Default Text / Plain / code etc.
    app = source_app or "PC"
    cls_label = classification.capitalize() if classification else "Text"
    if cls_label == "Plain":
        cls_label = "Text"
    return f"{app} · {cls_label}"


def format_full_metadata(clip: Any) -> str:
    """Format full combined display line for a clip."""
    time_part = format_display_time(clip.created_at)
    origin_part = get_origin_label(clip)
    return f"{time_part} · {origin_part}"
