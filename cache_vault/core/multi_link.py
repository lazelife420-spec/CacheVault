"""Helpers for safe multi-link clipboard pastes."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


@dataclass(frozen=True)
class MultiLinkPayload:
    raw_text: str
    urls: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.urls)

    @property
    def has_multiple(self) -> bool:
        return self.count > 1


def _trim_outer_whitespace(text: str) -> str:
    return (text or "").strip()


def _clean_url(url: str) -> str:
    return url.strip().rstrip(").,]")


def extract_urls(text: str) -> tuple[str, ...]:
    trimmed = _trim_outer_whitespace(text)
    if not trimmed:
        return ()
    urls = [_clean_url(match.group(0)) for match in _URL_RE.finditer(trimmed)]
    return tuple(url for url in urls if url)


def detect_multi_link_payload(text: str) -> MultiLinkPayload | None:
    """Detect a multi-link paste.

    ``raw_text`` keeps the paste exactly as it arrived. Trimming is only a
    detection aid; the receipt clip written from ``raw_text`` is documented as
    the original raw paste, so handing it pre-stripped text lost the blank lines
    and indentation that made the paste worth keeping a receipt of.
    """
    original = text or ""
    trimmed = _trim_outer_whitespace(original)
    if not trimmed:
        return None
    urls = extract_urls(trimmed)
    if len(urls) < 2:
        return None
    return MultiLinkPayload(raw_text=original, urls=urls)


def one_per_line(payload: MultiLinkPayload) -> str:
    return "\n".join(payload.urls)


def markdown_links(payload: MultiLinkPayload) -> str:
    out: list[str] = []
    for url in payload.urls:
        host = urlparse(url).netloc or url
        out.append(f"- [{host}]({url.replace(')', '%29')})")
    return "\n".join(out)
