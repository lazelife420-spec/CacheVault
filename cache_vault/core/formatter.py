"""Shared link batch formatting logic and receipt helpers."""

from __future__ import annotations

from typing import Any
from cache_vault.core import models


def escape_markdown_title(title: str) -> str:
    """Escape brackets in Markdown title label."""
    return title.replace("[", "\\[").replace("]", "\\]")


def escape_markdown_url(url: str) -> str:
    """Escape parentheses in URL."""
    return url.replace(")", "%29")


def format_batch_links(
    clips: list[Any],
    format_type: str,
    *,
    dedupe: bool = False,
) -> str:
    """Format a list of selected links as plain, markdown, or numbered lists.

    Preserves selection order. Raises ValueError if list is empty.
    """
    if not clips:
        raise ValueError("No clips selected to format.")

    # 1. Extract URL and Title pairs
    raw_list: list[tuple[str, str | None]] = []
    for clip in clips:
        content_raw = getattr(clip, "content", None) or ""
        content = str(content_raw).strip()
        source_url_raw = getattr(clip, "source_url", None) or ""
        source_url = str(source_url_raw).strip()

        if content.startswith(("http://", "https://")):
            url = content
        elif source_url.startswith(("http://", "https://")):
            url = source_url
        else:
            url = content

        title = getattr(clip, "title", None)
        if title:
            title = str(title).strip()
        raw_list.append((url, title))

    # 2. De-duplicate if requested (preserving first occurrence order)
    if dedupe:
        seen = set()
        deduped_list = []
        for url, title in raw_list:
            if url not in seen:
                seen.add(url)
                deduped_list.append((url, title))
        formatted_source = deduped_list
    else:
        formatted_source = raw_list

    # 3. Format according to format_type
    fmt = format_type.strip().lower()
    lines = []

    for i, (url, title) in enumerate(formatted_source):
        if fmt == "plain":
            if title:
                lines.append(f"{title} - {url}")
            else:
                lines.append(url)
        elif fmt == "markdown":
            label = title if title else url
            safe_title = escape_markdown_title(label)
            safe_url = escape_markdown_url(url)
            lines.append(f"- [{safe_title}]({safe_url})")
        elif fmt == "numbered":
            label = title if title else url
            safe_title = escape_markdown_title(label)
            safe_url = escape_markdown_url(url)
            lines.append(f"{i + 1}. [{safe_title}]({safe_url})")
        else:
            # Fallback to plain
            if title:
                lines.append(f"{title} - {url}")
            else:
                lines.append(url)

    return "\n".join(lines)


def make_batch_link_receipt(
    action: str,
    source: str,
    count: int,
    format_type: str,
    *,
    capture_mode: str | None = None,
    source_page: str | None = None,
    browser: str | None = None,
    transfer_status: str = "completed",
    error: str | None = None,
) -> dict[str, Any]:
    """Helper to build stamped receipt metadata for batch link actions."""
    body: dict[str, Any] = {
        "action": action,
        "source": source,
        "count": count,
        "format": format_type,
        "transfer_status": transfer_status,
    }

    if capture_mode:
        body["capture_mode"] = capture_mode
    if source_page:
        body["source_page"] = source_page
    if browser:
        body["browser"] = browser
    if error:
        body["error"] = error

    return body
