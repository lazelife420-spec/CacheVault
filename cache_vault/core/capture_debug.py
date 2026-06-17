"""Opt-in metadata-only diagnostics for clipboard capture flow."""

from __future__ import annotations

import os
from pathlib import Path

from . import models


def enabled() -> bool:
    return os.environ.get("CACHEVAULT_CAPTURE_DEBUG") == "1"


def _path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "capture_debug.log"


def payload_summary(payload: dict | None) -> str:
    if not payload:
        return "payload=none"
    if payload.get("text"):
        text = payload.get("text") or ""
        return (
            f"type=text len={len(text)} hash={models.content_hash(text)[:12]} "
            f"source={payload.get('source_app') or 'unknown'}"
        )
    if payload.get("image_png"):
        data = payload.get("image_png") or b""
        return (
            f"type=image bytes={len(data)} hash={models.bytes_hash(data)[:12]} "
            f"source={payload.get('source_app') or 'unknown'}"
        )
    return f"type=unsupported keys={sorted(payload)}"


def log(stage: str, detail: str = "") -> None:
    if not enabled():
        return
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{models.now_iso()} {stage} {detail}\n")
    except Exception:
        pass
