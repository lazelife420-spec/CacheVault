"""Regex Macro Preview and Transformation Engine.

Enables safe, opt-in regex-based transformations and preview before execution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from cache_vault.core import models


@dataclass
class RegexMacro:
    macro_id: str
    name: str
    enabled: bool
    pattern: str
    replacement: str
    content_types: list[str] = field(default_factory=list)  # e.g., ["plain", "link"]
    safe_scope: list[str] = field(default_factory=list)     # e.g., ["Dev"]
    source_scope: list[str] = field(default_factory=list)   # e.g., ["CLI", "Browser"]
    created_at: str = field(default_factory=models.now_iso)
    updated_at: str = field(default_factory=models.now_iso)

    def to_dict(self) -> dict:
        return {
            "macro_id": self.macro_id,
            "name": self.name,
            "enabled": self.enabled,
            "pattern": self.pattern,
            "replacement": self.replacement,
            "content_types": list(self.content_types),
            "safe_scope": list(self.safe_scope),
            "source_scope": list(self.source_scope),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RegexMacro:
        return cls(
            macro_id=data["macro_id"],
            name=data["name"],
            enabled=bool(data["enabled"]),
            pattern=data["pattern"],
            replacement=data["replacement"],
            content_types=list(data.get("content_types") or []),
            safe_scope=list(data.get("safe_scope") or []),
            source_scope=list(data.get("source_scope") or []),
            created_at=data.get("created_at") or models.now_iso(),
            updated_at=data.get("updated_at") or models.now_iso(),
        )


def preview_macro(macro: RegexMacro, input_text: str) -> dict:
    """Preview macro transformation on input_text without enforcing scopes or status."""
    try:
        rx = re.compile(macro.pattern)
        matched = bool(rx.search(input_text))
        after_text = rx.sub(macro.replacement, input_text)
        return {
            "before": input_text,
            "after": after_text,
            "matched": matched,
            "error": None,
        }
    except re.error as e:
        return {
            "before": input_text,
            "after": input_text,
            "matched": False,
            "error": f"Invalid regex pattern: {e}",
        }


def apply_macro(
    macro: RegexMacro,
    input_text: str,
    content_type: str | None = None,
    safe_id: str | None = None,
    source: str | None = None,
) -> tuple[str, bool]:
    """Apply macro transformation if enabled and matching scopes. Return (result, transformed)."""
    if not macro.enabled:
        return input_text, False

    # Check content type scope
    if macro.content_types and content_type not in macro.content_types:
        return input_text, False

    # Check safe scope
    if macro.safe_scope and safe_id not in macro.safe_scope:
        return input_text, False

    # Check source scope
    if macro.source_scope and source not in macro.source_scope:
        return input_text, False

    try:
        rx = re.compile(macro.pattern)
        matched = bool(rx.search(input_text))
        if matched:
            return rx.sub(macro.replacement, input_text), True
    except re.error:
        pass

    return input_text, False


def build_macro_receipt_payload(
    macro: RegexMacro,
    input_text: str,
    output_text: str,
    matched: bool,
    transformed: bool,
    source: str = "desktop_capture",
) -> dict:
    """Build the receipt event metadata representing a macro transformation outcome."""
    original_sha256 = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    output_sha256 = hashlib.sha256(output_text.encode("utf-8")).hexdigest()

    return {
        "action": "macro_transform",
        "timestamp": models.now_iso(),
        "source": source,
        "macro_id": macro.macro_id,
        "macro_version": macro.updated_at,
        "matched": matched,
        "transformed": transformed,
        "original_sha256": original_sha256,
        "output_sha256": output_sha256,
        "transfer_status": "completed",
    }
