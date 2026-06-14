"""Quality gate for Cache Vault brand assets.

Checks:
  1. every required asset file exists
  2. the ICO contains multiple sizes
  3. no PRIMARY asset contains gold-coin pixels (cash edition is variant-only)
  4. renders a contact sheet at 16/24/32/48/128/256 px (dark + light backgrounds)

Exits non-zero on any failure. Run after tools/build_assets.py.
    python tools/verify_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON_SIZES = [16, 24, 32, 48, 128, 256]
RESAMPLING_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS",
                             Image.LANCZOS)

REQUIRED = [
    "cache-vault-icon.svg",
    *[f"cache-vault-icon-{s}.png" for s in ICON_SIZES],
    "cache-vault-icon.ico",
    "cache-vault-lockup.svg",
    "cache-vault-lockup.png",
    "variants/cache-vault-cash-edition.svg",
    "variants/cache-vault-cash-edition.png",
]

# Primary (non-variant) raster assets that must NOT show the gold coin.
PRIMARY_RASTERS = [f"cache-vault-icon-{s}.png" for s in ICON_SIZES] + [
    "cache-vault-lockup.png"]


def _font(size: int):
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _is_gold(px) -> bool:
    r, g, b = px[0], px[1], px[2]
    a = px[3] if len(px) > 3 else 255
    return a > 40 and r >= 200 and 110 <= g <= 195 and b <= 100


def count_gold(img: Image.Image) -> int:
    img = img.convert("RGBA")
    px = img.load()
    assert px is not None
    return sum(1 for y in range(img.height) for x in range(img.width)
               if _is_gold(px[x, y]))


def check_files() -> list[str]:
    return [f for f in REQUIRED if not (ASSETS / f).exists()]


def check_ico() -> tuple[bool, set]:
    with Image.open(ASSETS / "cache-vault-icon.ico") as im:
        sizes = set(im.info.get("sizes", set()))
    return len(sizes) > 1, sizes


def check_no_gold() -> list[tuple[str, int]]:
    bad = []
    for name in PRIMARY_RASTERS:
        n = count_gold(Image.open(ASSETS / name))
        if n > 40:
            bad.append((name, n))
    return bad


def build_contact_sheet() -> Path:
    pad, gap = 28, 26
    label_h = 26
    band_h = 256 + label_h + pad
    total_w = pad * 2 + sum(ICON_SIZES) + gap * (len(ICON_SIZES) - 1)
    sheet = Image.new("RGBA", (total_w, band_h * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    font = _font(16)

    for row, bg in enumerate([(13, 17, 23, 255), (255, 255, 255, 255)]):
        top = row * band_h
        draw.rectangle([0, top, total_w, top + band_h], fill=bg)
        fg = (230, 235, 240, 255) if row == 0 else (40, 50, 60, 255)
        x = pad
        for s in ICON_SIZES:
            icon = Image.open(ASSETS / f"cache-vault-icon-{s}.png").convert("RGBA")
            y = top + pad + (256 - s) // 2
            if icon.size != (s, s):
                icon = icon.resize((s, s), RESAMPLING_LANCZOS)
            sheet.alpha_composite(icon, (x, y))
            label = f"{s}px"
            tb = draw.textbbox((0, 0), label, font=font)
            draw.text((x + (s - (tb[2] - tb[0])) // 2, top + pad + 256 + 4),
                      label, font=font, fill=fg)
            x += s + gap

    out = ASSETS / "cache-vault-contact-sheet.png"
    sheet.convert("RGB").save(out)
    return out


def main() -> int:
    ok = True

    missing = check_files()
    if missing:
        ok = False
        print("FAIL  missing required files:")
        for m in missing:
            print(f"        - {m}")
    else:
        print(f"PASS  all {len(REQUIRED)} required files present")

    multi, sizes = check_ico()
    if multi:
        print(f"PASS  ICO has {len(sizes)} sizes: {sorted(sizes)}")
    else:
        ok = False
        print(f"FAIL  ICO has only {len(sizes)} size(s): {sorted(sizes)}")

    bad = check_no_gold()
    if not bad:
        print("PASS  no primary asset uses the gold coin")
    else:
        ok = False
        print("FAIL  gold pixels found in primary assets:")
        for name, n in bad:
            print(f"        - {name}: {n} gold px")

    sheet = build_contact_sheet()
    print(f"INFO  contact sheet -> {sheet.relative_to(ROOT)}")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
