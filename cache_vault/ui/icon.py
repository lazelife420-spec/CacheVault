"""Resolve and load the Cache Vault brand assets at runtime.

The assets are generated from SVG by ``tools/build_assets.py`` (the source of
truth). This module only *locates* and *loads* them — the primary icon is
always the teal vault-dial version; the gold cash edition is a variant and is
never loaded here.
"""

from __future__ import annotations

import os
import sys

try:  # pragma: no cover - optional dependency
    from PIL import Image, ImageDraw
    _HAS_PIL = True
except Exception:  # noqa: BLE001
    _HAS_PIL = False

_PRIMARY_ICO = "cache-vault-icon.ico"
_PRIMARY_PNG = "cache-vault-icon-256.png"


def asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        # cache_vault/ui/icon.py -> repo root
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


def icon_ico_path() -> str:
    return asset_path(_PRIMARY_ICO)


def tray_image(size: int = 64):
    """A PIL image of the primary (teal) icon for the tray.

    Loads the generated PNG; falls back to a minimal drawn glyph only if the
    asset and Pillow are both unavailable.
    """
    if not _HAS_PIL:
        raise RuntimeError("Pillow is required for the tray icon")
    png = asset_path(_PRIMARY_PNG)
    if os.path.exists(png):
        return Image.open(png).convert("RGBA").resize((size, size), Image.LANCZOS)
    # Fallback: simple teal vault dial on a dark tile.
    img = Image.new("RGBA", (size, size), (20, 29, 40, 255))
    d = ImageDraw.Draw(img)
    teal = (45, 212, 191, 255)
    m = size * 0.16
    d.ellipse([m, m, size - m, size - m], outline=teal, width=max(2, size // 16))
    d.ellipse([size * 0.42, size * 0.42, size * 0.58, size * 0.58], fill=(94, 234, 212, 255))
    return img
