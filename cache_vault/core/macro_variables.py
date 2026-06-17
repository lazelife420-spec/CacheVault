"""Vault Macro variable expansion — no UI imports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .paste_delivery import snapshot_clipboard_text

_VAR_RE = re.compile(r"\{([a-z_]+)\}", re.I)


@dataclass
class MacroVariableContext:
    safe_name: str = ""
    item_id: str = ""
    clipboard_text: str | None = None


def expand_macro_variables(text: str, ctx: MacroVariableContext | None = None) -> tuple[str, list[str]]:
    """Expand ``{date}``, ``{time}``, etc. Returns (expanded, missing_vars)."""
    ctx = ctx or MacroVariableContext()
    missing: list[str] = []
    now = datetime.now(timezone.utc)

    def repl(match: re.Match) -> str:
        key = match.group(1).lower()
        if key == "date":
            return now.strftime("%Y-%m-%d")
        if key == "time":
            return now.strftime("%H:%M:%S")
        if key == "datetime":
            return now.strftime("%Y-%m-%d %H:%M:%S")
        if key == "clipboard":
            if ctx.clipboard_text is None:
                ctx.clipboard_text = snapshot_clipboard_text() or ""
            return ctx.clipboard_text
        if key == "safe_name":
            return ctx.safe_name or ""
        if key == "item_id":
            return ctx.item_id or ""
        if key == "newline":
            return "\n"
        if key == "tab":
            return "\t"
        missing.append(key)
        return match.group(0)

    return _VAR_RE.sub(repl, text or ""), missing
