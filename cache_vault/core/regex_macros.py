from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from cache_vault.core import models


def regex_macros_path() -> Path:
    """Resolve the default local JSON file path for regex macros."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "regex_macros.json"


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


def validate_macro(macro: RegexMacro) -> str | None:
    """Validate macro configuration and return an error message, or None if valid."""
    if not macro.macro_id or not macro.macro_id.strip():
        return "Missing macro_id"
    if not macro.name or not macro.name.strip():
        return "Missing name"
    if macro.pattern is None or not macro.pattern.strip():
        return "Missing pattern"
    if macro.replacement is None:
        return "Missing replacement"
    try:
        re.compile(macro.pattern)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    return None


def load_regex_macros() -> list[RegexMacro]:
    """Load, validate, and return the list of persisted regex macros."""
    path = regex_macros_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        out = []
        for raw in data:
            try:
                # Basic validation for required fields
                if not all(k in raw for k in ("macro_id", "name", "enabled", "pattern", "replacement")):
                    continue
                macro = RegexMacro.from_dict(raw)
                out.append(macro)
            except Exception:
                continue
        return out
    except Exception:
        return []


def save_regex_macros(macros: list[RegexMacro]) -> None:
    """Persist the list of regex macros to the local JSON file."""
    path = regex_macros_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = [m.to_dict() for m in macros]
        from . import safe_io
        safe_io.atomic_write_text(path, json.dumps(raw, indent=2), encoding="utf-8")
    except Exception:
        pass

