"""Programmatic Cache Vault icon — the SVG mark rendered with Pillow.

One source of truth for the tray icon, the window icon, and the packaged exe
icon (via tools/make_icon.py). Rendered supersampled then downscaled for clean
anti-aliasing. Mirrors assets/icon.svg.
"""

from __future__ import annotations

import os
import sys

try:  # pragma: no cover - optional dependency
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except Exception:  # noqa: BLE001
    _HAS_PIL = False


# Palette (matches assets/icon.svg).
_TILE_TOP = (16, 23, 31)
_TILE_BOT = (29, 41, 55)
_ACCENT = (45, 212, 191, 255)        # teal-400
_HUB = (153, 246, 228, 255)          # teal-200
_DARK = (12, 18, 24, 255)
_INNER_RING = (52, 211, 153, 130)    # emerald @ ~0.45 alpha
_GOLD = (245, 173, 40, 255)          # cash-edition coin
_GOLD_EDGE = (180, 83, 9, 255)
_COIN_TEXT = (124, 45, 18, 255)


def _load_font(size: int):
    for name in ("georgiab.ttf", "arialbd.ttf", "seguisb.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def render_icon(size: int = 256, cash: bool = False):
    """Return an ``RGBA`` :class:`PIL.Image` of the icon at ``size`` px.

    ``cash=True`` renders the cash edition: a gold ``$`` coin at the hub.
    """
    if not _HAS_PIL:
        raise RuntimeError("Pillow is required to render the icon")
    ss = size * 4  # supersample
    sc = ss / 256.0

    def s(v: float) -> float:
        return v * sc

    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    grad = ImageDraw.Draw(img)
    for y in range(ss):
        t = y / (ss - 1)
        grad.line([(0, y), (ss, y)],
                  fill=(_lerp(_TILE_TOP[0], _TILE_BOT[0], t),
                        _lerp(_TILE_TOP[1], _TILE_BOT[1], t),
                        _lerp(_TILE_TOP[2], _TILE_BOT[2], t), 255))
    # Clip the gradient to a rounded square.
    mask = Image.new("L", (ss, ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, ss - 1, ss - 1],
                                           radius=int(s(58)), fill=255)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)
    cx = cy = s(128)

    def line(x1, y1, x2, y2, color, width):
        d.line([(s(x1), s(y1)), (s(x2), s(y2))], fill=color, width=int(width))

    def disc(x, y, r, color):
        d.ellipse([s(x) - s(r), s(y) - s(r), s(x) + s(r), s(y) + s(r)], fill=color)

    # Clipboard clip on top.
    d.rounded_rectangle([s(100), s(8), s(156), s(36)], radius=int(s(9)), fill=_ACCENT)
    d.rounded_rectangle([s(114), s(2), s(142), s(16)], radius=int(s(5)), fill=_DARK)

    # Wheel handle spokes + knobs.
    for ex, ey in [(201, 55), (55, 55), (201, 201), (55, 201)]:
        line(128, 128, ex, ey, _ACCENT, s(9))
    for ex, ey in [(201, 55), (55, 55), (201, 201), (55, 201)]:
        disc(ex, ey, 7, _HUB)

    # Vault door: dark fill + accent ring.
    d.ellipse([cx - s(80), cy - s(80), cx + s(80), cy + s(80)], fill=(12, 18, 24, 150))
    d.ellipse([cx - s(80), cy - s(80), cx + s(80), cy + s(80)],
              outline=_ACCENT, width=int(s(11)))
    d.ellipse([cx - s(51), cy - s(51), cx + s(51), cy + s(51)],
              outline=_INNER_RING, width=max(1, int(s(2.5))))

    # Dial notches.
    for x1, y1, x2, y2 in [
        (128, 92, 128, 108), (128, 148, 128, 164),
        (92, 128, 108, 128), (148, 128, 164, 128),
        (103, 103, 114, 114), (142, 142, 153, 153),
        (153, 103, 142, 114), (114, 142, 103, 153),
    ]:
        line(x1, y1, x2, y2, _HUB, s(4))

    # Hub — teal dial, or gold $ coin for the cash edition.
    if cash:
        cr = s(31)
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=_GOLD,
                  outline=_GOLD_EDGE, width=max(1, int(s(2))))
        ir = s(25)
        d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir],
                  outline=(255, 251, 235, 120), width=max(1, int(s(1.5))))
        font = _load_font(int(s(46)))
        glyph = "$"
        bb = d.textbbox((0, 0), glyph, font=font)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        d.text((cx - gw / 2 - bb[0], cy - gh / 2 - bb[1]), glyph,
               font=font, fill=_COIN_TEXT)
    else:
        disc(128, 128, 17, _HUB)
        disc(128, 128, 7, _DARK)

    return img.resize((size, size), Image.LANCZOS)


# --- asset resolution (dev + frozen) ----------------------------------------
def asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        # cache_vault/ui/icon.py -> repo root
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


def icon_ico_path() -> str:
    return asset_path("icon.ico")
