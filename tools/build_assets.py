"""Build all Cache Vault raster assets from the SVG sources.

SVG is the source of truth. Each PNG is rendered from its SVG with svglib
(supersampled 4x then downscaled with LANCZOS), with a rounded-rectangle alpha
mask so the tile/banner corners are transparent. The ICO is assembled from the
clean PNG sizes.

    python tools/build_assets.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
VARIANTS = ASSETS / "variants"
ICON_SIZES = [16, 24, 32, 48, 128, 256]
SS = 4  # supersample factor


def rasterize(svg_path: Path, out_w: int, out_h: int, radius_units: float) -> Image.Image:
    """Render ``svg_path`` to an RGBA image of (out_w, out_h) with rounded corners."""
    drawing = svg2rlg(str(svg_path))
    big_w, big_h = out_w * SS, out_h * SS
    scale = big_w / drawing.width
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    renderPM.drawToFile(drawing, tmp_path, fmt="PNG", dpi=72 * scale)
    img = Image.open(tmp_path).convert("RGBA")
    if img.size != (big_w, big_h):
        img = img.resize((big_w, big_h), Image.LANCZOS)
    Path(tmp_path).unlink(missing_ok=True)

    # Rounded-rect alpha mask (units -> supersampled px).
    r_px = int(radius_units * scale)
    mask = Image.new("L", (big_w, big_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big_w - 1, big_h - 1],
                                           radius=r_px, fill=255)
    img.putalpha(mask)
    return img.resize((out_w, out_h), Image.LANCZOS)


def build_icon() -> None:
    src = ASSETS / "cache-vault-icon.svg"
    master = rasterize(src, 256, 256, radius_units=56)
    per_size = {}
    for s in ICON_SIZES:
        # Render each size from the SVG directly for maximum small-size clarity.
        img = rasterize(src, s, s, radius_units=56)
        img.save(ASSETS / f"cache-vault-icon-{s}.png")
        per_size[s] = img
        print(f"wrote cache-vault-icon-{s}.png")
    # ICO assembled from the clean per-size renders.
    ico_imgs = [per_size[s] for s in ICON_SIZES]
    ico_imgs[-1].save(ASSETS / "cache-vault-icon.ico", format="ICO",
                      sizes=[(s, s) for s in ICON_SIZES], append_images=ico_imgs[:-1])
    print("wrote cache-vault-icon.ico")


def build_lockup() -> None:
    img = rasterize(ASSETS / "cache-vault-lockup.svg", 540, 180, radius_units=26)
    img.save(ASSETS / "cache-vault-lockup.png")
    print("wrote cache-vault-lockup.png")


def build_cash_variant() -> None:
    VARIANTS.mkdir(parents=True, exist_ok=True)
    img = rasterize(VARIANTS / "cache-vault-cash-edition.svg", 256, 256, radius_units=56)
    img.save(VARIANTS / "cache-vault-cash-edition.png")
    print("wrote variants/cache-vault-cash-edition.png")


def main() -> int:
    build_icon()
    build_lockup()
    build_cash_variant()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
