"""Generate 1200x630 Cache Vault social share image for og:image / twitter:image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
OUT = Path(__file__).resolve().parents[1] / "docs" / "cache-vault-social-share.png"

BG = (7, 17, 31)
BG2 = (11, 18, 32)
ACCENT = (45, 212, 191)
ACCENT2 = (94, 234, 212)
TEXT = (246, 248, 251)
MUTED = (184, 194, 214)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_logo(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0) -> None:
    s = scale
    body = (20, 29, 40)
    draw.rounded_rectangle(
        (cx - 52 * s, cy - 52 * s, cx + 52 * s, cy + 52 * s),
        radius=int(18 * s),
        fill=body,
        outline=ACCENT,
        width=max(2, int(3 * s)),
    )
    draw.rounded_rectangle(
        (cx - 22 * s, cy - 58 * s, cx + 22 * s, cy - 38 * s),
        radius=int(8 * s),
        fill=ACCENT,
    )
    draw.ellipse(
        (cx - 28 * s, cy - 28 * s, cx + 28 * s, cy + 28 * s),
        fill=ACCENT2,
    )
    for dx, dy in [(-18, -18), (18, -18), (-18, 18), (18, 18)]:
        draw.line(
            (cx, cy, cx + dx * s, cy + dy * s),
            fill=ACCENT,
            width=max(2, int(4 * s)),
        )


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(BG[0] + (BG2[0] - BG[0]) * t)
        g = int(BG[1] + (BG2[1] - BG[1]) * t)
        b = int(BG[2] + (BG2[2] - BG[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw.ellipse((-120, -80, 420, 420), fill=(45, 212, 191, 0))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((780, -60, 1280, 440), fill=(45, 212, 191, 28))
    od.ellipse((900, 280, 1240, 620), fill=(94, 234, 212, 18))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((48, 48, W - 48, H - 48), radius=28, outline=(255, 255, 255, 30), width=1)

    _draw_logo(draw, 130, H // 2 - 10, scale=1.15)

    x = 230
    draw.text((x, 150), "Cache Vault", fill=TEXT, font=_font(72, bold=True))
    draw.text((x, 240), "Clipboard vault for serious work", fill=ACCENT2, font=_font(38, bold=True))
    draw.text((x, 320), "Local-first · No cloud · No subscription", fill=MUTED, font=_font(28))
    draw.text((x, 380), "Free vault + Founder proof workflows", fill=MUTED, font=_font(28))

    draw.rounded_rectangle((x, 460, x + 320, 520), radius=14, fill=ACCENT)
    draw.text((x + 28, 474), "Windows · Lifetime license", fill=(4, 47, 46), font=_font(24, bold=True))

    draw.rounded_rectangle((W - 280, H - 72, W - 48, H - 28), radius=12, outline=ACCENT, width=2)
    draw.text((W - 252, H - 62), "Proof Foundry", fill=ACCENT, font=_font(22, bold=True))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)
    saved = Image.open(OUT)
    if saved.size != (W, H):
        raise SystemExit(f"Expected {W}x{H}, got {saved.size}")
    print(f"Wrote {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()
