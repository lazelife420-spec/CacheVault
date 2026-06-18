"""Copy Clean formatters for vault items and receipt rows.

These helpers never mutate a clip and never invent unavailable fields. They
return ``None`` when a requested clean format is not honestly available.
"""

from __future__ import annotations

import re

from . import clip_metadata, models, pathutil
from .models import Clip

COPY_TEXT = "copy_text"
COPY_PLAIN_TEXT = "copy_plain_text"
COPY_TITLE_LINK = "copy_title_link"
COPY_LINK_ONLY = "copy_link_only"
COPY_MARKDOWN = "copy_markdown"
COPY_SMS = "copy_sms"
COPY_EMAIL = "copy_email"
COPY_PHONE = "copy_phone"
COPY_EMAIL_ADDRESS = "copy_email_address"
COPY_ADDRESS = "copy_address"
COPY_FILE_PATH = "copy_file_path"
COPY_RECEIPT_SUMMARY = "copy_receipt_summary"
COPY_HASH = "copy_hash"
COPY_METADATA_SUMMARY = "copy_metadata_summary"
COPY_SOURCE_SUMMARY = "copy_source_summary"

EVENT_ITEM_COPIED_CLEAN = "item_copied_clean"
EVENT_ITEM_CONTEXT_ACTION_USED = "item_context_action_used"
EVENT_RECEIPT_SUMMARY_COPIED = "receipt_summary_copied"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}")


def url_for_clip(clip: Clip) -> str | None:
    candidates = [clip.source_url, clip.content]
    for raw in candidates:
        val = (raw or "").strip()
        if val.startswith(("http://", "https://")):
            return val
    return None


def title_for_clip(clip: Clip) -> str:
    title = (clip.title or "").strip()
    if title:
        return title
    return clip_metadata.clip_title(clip.content, clip.preview).strip() or "Untitled vault item"


def plain_text(content: str) -> str:
    lines = [" ".join(line.split()) for line in (content or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def markdown_link(title: str, url: str) -> str:
    safe_title = title.replace("[", "\\[").replace("]", "\\]")
    safe_url = url.replace(")", "%29")
    return f"[{safe_title}]({safe_url})"


def phone_for_clip(clip: Clip) -> str | None:
    if clip.classification == models.CLASS_PHONE:
        match = _PHONE_RE.search(clip.content or clip.preview or "")
        return match.group(0).strip() if match else plain_text(clip.content or clip.preview)
    return None


def email_for_clip(clip: Clip) -> str | None:
    if clip.classification == models.CLASS_EMAIL:
        match = _EMAIL_RE.search(clip.content or clip.preview or "")
        return match.group(0).strip() if match else plain_text(clip.content or clip.preview)
    return None


def file_path_for_clip(clip: Clip) -> str | None:
    text = (clip.content or "").strip()
    if clip.classification == models.CLASS_PATH and pathutil.is_local_path(text):
        return text
    return None


def source_summary(clip: Clip) -> str:
    parts = [
        f"Source app: {clip_metadata.display(clip.source_app)}",
        f"Source window: {clip_metadata.display(clip.source_window)}",
        f"Source URL: {clip_metadata.display(clip.source_url)}",
        f"Safe: {clip_metadata.display(clip.safe_name)}",
        f"Capture mode: {clip.capture_mode or models.CAPTURE_AUTO}",
    ]
    return "\n".join(parts)


def metadata_summary(clip: Clip) -> str:
    parts = [
        f"Title: {title_for_clip(clip)}",
        f"Type: {clip_metadata.format_label(clip.classification, clip.content_type)}",
        f"Safe: {clip_metadata.display(clip.safe_name)} ({clip.safe_id})",
        f"Source app: {clip_metadata.display(clip.source_app)}",
        f"Source URL: {clip_metadata.display(clip.source_url)}",
        f"Created: {clip.created_at}",
        f"Last used: {clip.date_used or clip.updated_at}",
        f"Hash: {clip.content_hash or 'unavailable'}",
    ]
    return "\n".join(parts)


def receipt_summary(row) -> str:
    """Return a metadata-only receipt summary for a ReceiptRow-like object."""
    fields = [
        ("Receipt", getattr(row, "receipt_id", "")),
        ("Action", getattr(row, "action_label", "") or getattr(row, "action_raw", "")),
        ("Result", getattr(row, "result", "")),
        ("Item", getattr(row, "item_label", "")),
        ("Clip ID", getattr(row, "clip_id", "") or "unavailable"),
        ("Hash", getattr(row, "proof_hash", "") or "unavailable"),
        ("Timestamp", getattr(row, "timestamp", "")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def format_clip(clip: Clip, action: str) -> str | None:
    content = clip.content or ""
    title = title_for_clip(clip)
    url = url_for_clip(clip)

    if action == COPY_TEXT:
        return content
    if action == COPY_PLAIN_TEXT:
        return plain_text(content)
    if action == COPY_TITLE_LINK:
        return f"{title}\n{url}" if url else None
    if action == COPY_LINK_ONLY:
        return url
    if action == COPY_MARKDOWN:
        return markdown_link(title, url) if url else None
    if action == COPY_SMS:
        if url:
            return f"{title}: {url}"
        return plain_text(content)
    if action == COPY_EMAIL:
        body = plain_text(content)
        if url:
            body = f"{title}\n{url}"
        return f"Subject: {title}\n\n{body}"
    if action == COPY_PHONE:
        return phone_for_clip(clip)
    if action == COPY_EMAIL_ADDRESS:
        return email_for_clip(clip)
    if action == COPY_ADDRESS:
        return None
    if action == COPY_FILE_PATH:
        return file_path_for_clip(clip)
    if action == COPY_HASH:
        return clip.content_hash or None
    if action == COPY_METADATA_SUMMARY:
        return metadata_summary(clip)
    if action == COPY_SOURCE_SUMMARY:
        return source_summary(clip)
    return None


def available_clip_actions(clip: Clip) -> list[str]:
    actions = [
        COPY_TEXT,
        COPY_PLAIN_TEXT,
        COPY_SMS,
        COPY_EMAIL,
        COPY_HASH,
        COPY_METADATA_SUMMARY,
    ]
    if url_for_clip(clip):
        actions.extend([COPY_TITLE_LINK, COPY_LINK_ONLY, COPY_MARKDOWN])
    if phone_for_clip(clip):
        actions.append(COPY_PHONE)
    if email_for_clip(clip):
        actions.append(COPY_EMAIL_ADDRESS)
    if file_path_for_clip(clip):
        actions.append(COPY_FILE_PATH)
    if clip.capture_mode == models.CAPTURE_MOBILE_SHARE:
        actions.append(COPY_SOURCE_SUMMARY)
    return actions


def no_forbidden_copy_clean_claims(text: str) -> bool:
    forbidden = ("cloud sync", "encrypted safes", "final release", "military-grade")
    low = text.lower()
    return not any(term in low for term in forbidden)
