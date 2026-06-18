"""Deterministic visual accents for clip labels and grouping headers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import models

LOCKED_ITEMS_MESSAGE = "Vault locked — unlock to view items"

FORBIDDEN_CLAIMS = (
    "cloud sync",
    "encrypted safes",
    "final release",
    "bank-grade",
    "military-grade",
)


@dataclass(frozen=True)
class AccentStyle:
    """A subtle, theme-safe accent token consumed by UI widgets."""

    key: str
    accent: tuple[str, str]
    bg: tuple[str, str]
    border: tuple[str, str]
    text: tuple[str, str]


_STYLES: dict[str, AccentStyle] = {
    "neutral": AccentStyle(
        "neutral",
        ("#64748B", "#7A848E"),
        ("#E2E7EA", "#171D23"),
        ("#B8C0C6", "#2A323C"),
        ("#2F3A45", "#D5DBDF"),
    ),
    "source": AccentStyle(
        "source",
        ("#536B82", "#8EA3B5"),
        ("#E1E8ED", "#17212A"),
        ("#B5C2CC", "#2A3844"),
        ("#263746", "#D5DEE5"),
    ),
    "link": AccentStyle(
        "link",
        ("#2C7D8F", "#3AB4C4"),
        ("#E1F0F2", "#10252B"),
        ("#AFCFD5", "#214B55"),
        ("#245765", "#C7E7EB"),
    ),
    "image": AccentStyle(
        "image",
        ("#7E6AB8", "#B79AE6"),
        ("#ECE8F5", "#211C2B"),
        ("#CABCE0", "#46365E"),
        ("#4B3C72", "#E1D6F4"),
    ),
    "mobile": AccentStyle(
        "mobile",
        ("#2F7D68", "#42B99A"),
        ("#E0F0EA", "#10251F"),
        ("#AACFC2", "#244B41"),
        ("#235A4B", "#C7EBDD"),
    ),
    "receipt": AccentStyle(
        "receipt",
        ("#A9832E", "#C9A24D"),
        ("#F2EBD9", "#292314"),
        ("#D4C18B", "#51411F"),
        ("#674F1D", "#F0E3BB"),
    ),
    "favorite": AccentStyle(
        "favorite",
        ("#A9832E", "#C9A24D"),
        ("#F2EBD9", "#292314"),
        ("#D4C18B", "#51411F"),
        ("#674F1D", "#F0E3BB"),
    ),
    "warning": AccentStyle(
        "warning",
        ("#B63B40", "#D8666A"),
        ("#F2E0E1", "#2A1618"),
        ("#D8A5A7", "#663035"),
        ("#7D2429", "#F2C7C9"),
    ),
    "duplicate": AccentStyle(
        "duplicate",
        ("#B96D2B", "#D9914D"),
        ("#F3E7DC", "#2A1D12"),
        ("#D9B98F", "#5A3A1F"),
        ("#754217", "#F2D4B5"),
    ),
    "code": AccentStyle(
        "code",
        ("#5F65B0", "#9AA2E6"),
        ("#E6E8F4", "#1A1D31"),
        ("#B8BCE0", "#363B69"),
        ("#343A78", "#D9DCF8"),
    ),
    "file": AccentStyle(
        "file",
        ("#526171", "#90A0AF"),
        ("#E3E8EC", "#171F27"),
        ("#B9C3CC", "#303B46"),
        ("#33404C", "#DCE3E8"),
    ),
    "browser": AccentStyle(
        "browser",
        ("#2F73B7", "#5AA5DF"),
        ("#E2ECF5", "#122335"),
        ("#B3C9DD", "#294A67"),
        ("#244F79", "#CEE6F8"),
    ),
}

_LABEL_TO_STYLE = {
    "text": "neutral",
    "plain": "neutral",
    "email": "neutral",
    "phone": "neutral",
    "today": "neutral",
    "yesterday": "neutral",
    "this week": "neutral",
    "older": "neutral",
    "link": "link",
    "url": "link",
    "domain": "link",
    "screenshot": "image",
    "screenshots": "image",
    "image": "image",
    "images": "image",
    "screenshots images": "image",
    "mobile": "mobile",
    "android": "mobile",
    "android share": "mobile",
    "incoming from phone": "mobile",
    "phone share": "mobile",
    "receipt": "receipt",
    "proof": "receipt",
    "has receipt": "receipt",
    "receipt stamped": "receipt",
    "exported": "receipt",
    "favorite": "favorite",
    "favorites": "favorite",
    "starred": "favorite",
    "sensitive": "warning",
    "warning": "warning",
    "duplicate": "duplicate",
    "exact duplicate": "duplicate",
    "possible duplicate": "duplicate",
    "code": "code",
    "command": "code",
    "path": "file",
    "file": "file",
    "files": "file",
    "files paths": "file",
    "browser": "browser",
    "chrome": "browser",
    "edge": "browser",
}


def _normalize(value: str | None) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[/_.:-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def neutral_accent() -> AccentStyle:
    return _STYLES["neutral"]


def label_accent(label: str | None) -> AccentStyle:
    """Return a deterministic subtle style for a user-facing label."""

    normalized = _normalize(label)
    if not normalized:
        return neutral_accent()
    style_key = _LABEL_TO_STYLE.get(normalized)
    if style_key is None:
        if any(token in normalized for token in ("chrome", "edge", "browser")):
            style_key = "browser"
        elif any(token in normalized for token in ("android", "mobile", "phone share")):
            style_key = "mobile"
        elif "receipt" in normalized or "proof" in normalized:
            style_key = "receipt"
        elif "duplicate" in normalized:
            style_key = "duplicate"
        else:
            style_key = "neutral"
    return _STYLES[style_key]


def type_accent(classification: str | None, content_type: str | None) -> AccentStyle:
    if str(content_type or "").startswith("image") or classification == models.CLASS_IMAGE:
        return label_accent("Screenshot")
    return label_accent(
        {
            models.CLASS_LINK: "Link",
            models.CLASS_PATH: "Path",
            models.CLASS_CODE: "Code",
            models.CLASS_COMMAND: "Command",
            models.CLASS_EMAIL: "Email",
            models.CLASS_PHONE: "Phone",
            models.CLASS_PLAIN: "Text",
        }.get(classification, "Text")
    )


def group_header_accent(
    group_by: str | None,
    label: str | None,
    *,
    safe_accent: str | None = None,
) -> AccentStyle:
    """Return the accent for a grouping header, keyed by grouping semantics."""

    group_key = _normalize(group_by)
    if group_key in {"date", "created", "created at"}:
        return neutral_accent()
    if group_key in {"source", "source app", "source_app"}:
        style = label_accent(label)
        return style if style.key == "browser" else _STYLES["source"]
    if group_key == "type":
        return label_accent(label)
    if group_key == "domain":
        return label_accent("Domain")
    if group_key in {"safe", "safes"}:
        if safe_accent:
            return AccentStyle(
                "safe",
                (safe_accent, safe_accent),
                _STYLES["neutral"].bg,
                _STYLES["neutral"].border,
                _STYLES["neutral"].text,
            )
        return neutral_accent()
    return neutral_accent()


def no_forbidden_accent_claims(text: str) -> bool:
    low = (text or "").lower()
    return not any(claim in low for claim in FORBIDDEN_CLAIMS)
