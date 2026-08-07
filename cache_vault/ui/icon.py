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


def _draw_magnifier(size: int, color: str):
    """Draw a monochrome magnifier glyph on a transparent RGBA tile."""
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    ink = (r, g, b, 255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(1, size // 9)
    cx = size * 0.40
    cy = size * 0.40
    rad = size * 0.30
    d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=ink, width=lw)
    # Handle: short diagonal stroke from the lower-right of the lens ring.
    hx1 = cx + rad * 0.70
    hy1 = cy + rad * 0.70
    hx2 = size * 0.86
    hy2 = size * 0.86
    d.line([hx1, hy1, hx2, hy2], fill=ink, width=lw)
    return img


def search_icon_pil(size: int = 18):
    """A monochrome magnifier glyph as a PIL RGBA image for search affordances.

    Drawn at runtime (no asset dependency) so it stays crisp at any DPI and
    matches the Proof Foundry monochrome-symbol language (cf. the ⟳/◈ glyphs
    used elsewhere in the chrome). Pillow is already a runtime dependency
    (used for the tray icon), so this adds no packaging burden. Returns
    ``None`` when Pillow is unavailable so callers can degrade gracefully.

    The caller is responsible for wrapping this in an ``ImageTk.PhotoImage``
    bound to the correct Tk root and retaining the reference — a ``CTkImage``
    binds its internal photo to ``Tk._default_root``, which breaks across the
    many app construction/teardown cycles in the test suite.
    """
    if not _HAS_PIL:
        return None
    return _draw_magnifier(size, "#8E98A2")  # lifted muted — visible on BLACK_METAL


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
