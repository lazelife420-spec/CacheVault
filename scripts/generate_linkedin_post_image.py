"""Generate clean Cache Vault launch images for a LinkedIn post.

Outputs (into assets/):
  cache-vault-linkedin.png          1200x1200  square feed image (preferred)
  cache-vault-linkedin-wide.png     1200x630   link/landscape image

Palette and product language follow cache_vault.brand (the real app theme:
graphite + restrained teal), so the preview reads as the actual product.
Messaging matches the approved post wording, including "No cloud account".
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SHOT = ASSETS / "cache-vault-ui-shot.png"

# --- Palette (from cache_vault.brand) --------------------------------------
FOUNDRY_BLACK = (6, 8, 10)
GRAPHITE = (18, 22, 28)
IRON_GRAY = (26, 31, 38)
BLACK_METAL = (14, 18, 24)
PROOF_TEAL = (26, 158, 140)
PROOF_TEAL_BRIGHT = (52, 196, 174)
RECEIPT_WHITE = (232, 236, 237)
STAMP_GOLD = (201, 162, 77)
MUTED_TEXT = (122, 132, 142)
VAULT_BORDER = (42, 50, 60)
ROW_BG = (16, 20, 26)


def _font(size: int, bold: bool = False, mono: bool = False):
    if mono:
        candidates = ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf"]
    else:
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


def _gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), FOUNDRY_BLACK)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(FOUNDRY_BLACK[0] + (GRAPHITE[0] - FOUNDRY_BLACK[0]) * t)
        g = int(FOUNDRY_BLACK[1] + (GRAPHITE[1] - FOUNDRY_BLACK[1]) * t)
        b = int(FOUNDRY_BLACK[2] + (GRAPHITE[2] - FOUNDRY_BLACK[2]) * t)
        d.line([(0, y), (w, y)], fill=(r, g, b))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-w * 0.25, -h * 0.2, w * 0.35, h * 0.4), fill=(*PROOF_TEAL, 26))
    gd.ellipse((w * 0.7, h * 0.6, w * 1.2, h * 1.15), fill=(*PROOF_TEAL, 18))
    return Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")


def _logo(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float = 1.0) -> None:
    s = scale
    draw.rounded_rectangle(
        (cx - 52 * s, cy - 52 * s, cx + 52 * s, cy + 52 * s),
        radius=int(18 * s), fill=IRON_GRAY, outline=PROOF_TEAL, width=max(2, int(3 * s)),
    )
    draw.rounded_rectangle(
        (cx - 22 * s, cy - 58 * s, cx + 22 * s, cy - 38 * s),
        radius=int(8 * s), fill=PROOF_TEAL,
    )
    draw.ellipse(
        (cx - 26 * s, cy - 26 * s, cx + 26 * s, cy + 26 * s),
        outline=PROOF_TEAL_BRIGHT, width=max(2, int(4 * s)),
    )
    draw.ellipse((cx - 9 * s, cy - 9 * s, cx + 9 * s, cy + 9 * s), fill=PROOF_TEAL_BRIGHT)
    for dx, dy in [(-18, -18), (18, -18), (-18, 18), (18, 18)]:
        draw.line((cx, cy, cx + dx * s, cy + dy * s), fill=PROOF_TEAL, width=max(2, int(4 * s)))


def _round_corners(im: Image.Image, radius: int) -> Image.Image:
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0], im.size[1]), radius=radius, fill=255)
    im.putalpha(mask)
    return im


def _load_shot(target_w: int) -> Image.Image | None:
    """Load the real UI screenshot, trim OS border/taskbar bleed, fit width."""
    if not SHOT.exists():
        return None
    im = Image.open(SHOT).convert("RGB")
    w, h = im.size
    im = im.crop((2, 1, w - 2, h - 16))  # drop window border + bottom taskbar sliver
    w, h = im.size
    scale = target_w / w
    im = im.resize((target_w, round(h * scale)), Image.LANCZOS)
    return _round_corners(im, 18)


def _chip(draw, x, y, text, font, fg, border):
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad_x, pad_y = 18, 10
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=(th + pad_y * 2) // 2, outline=border, width=2,
    )
    draw.text((x + pad_x, y + pad_y - tb[1]), text, font=font, fill=fg)
    return x + tw + pad_x * 2


# --- Mock vault window ------------------------------------------------------
CLIPS = [
    ("CODE", "git rebase -i HEAD~4   # squash before the PR", "Local only", True),
    ("LINK", "https://docs.cachevault.app/proof-manifests", "Receipt stamped", False),
    ("TEXT", "Q3 launch checklist — finalize pricing + release notes", "Favorited", False),
    ("NOTE", "Investor reply: send the one-pager + 90s demo Thursday", "Local only", False),
    ("IMG", "screenshot-2026-06-24-dashboard.png", "Hash verified", True),
]
BADGE = {
    "CODE": PROOF_TEAL_BRIGHT, "LINK": (120, 170, 240),
    "TEXT": MUTED_TEXT, "NOTE": STAMP_GOLD, "IMG": (180, 140, 220),
}


def _window(card_w: int, card_h: int) -> Image.Image:
    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, card_w, card_h), radius=22, fill=GRAPHITE, outline=VAULT_BORDER, width=2)

    bar_h = 56
    d.rounded_rectangle((0, 0, card_w, bar_h + 18), radius=22, fill=BLACK_METAL)
    d.rectangle((0, bar_h - 8, card_w, bar_h + 18), fill=BLACK_METAL)
    for i, col in enumerate([(201, 79, 84), (201, 162, 77), (52, 196, 174)]):
        d.ellipse((22 + i * 26, bar_h // 2 - 7, 22 + i * 26 + 14, bar_h // 2 + 7), fill=col)
    d.text((120, bar_h // 2 - 12), "Cache Vault  —  A Proof Foundry product",
           font=_font(20, bold=True), fill=RECEIPT_WHITE)
    pill = "Local Vault Active"
    pf = _font(17, bold=True)
    pb = d.textbbox((0, 0), pill, font=pf)
    pw = pb[2] - pb[0]
    px = card_w - pw - 70
    d.rounded_rectangle((px - 30, bar_h // 2 - 16, px + pw + 14, bar_h // 2 + 16),
                        radius=16, fill=(12, 40, 36), outline=PROOF_TEAL, width=1)
    d.ellipse((px - 20, bar_h // 2 - 5, px - 10, bar_h // 2 + 5), fill=PROOF_TEAL_BRIGHT)
    d.text((px, bar_h // 2 - 11), pill, font=pf, fill=PROOF_TEAL_BRIGHT)

    body_top = bar_h + 28
    side_w = 230
    d.rounded_rectangle((18, body_top, 18 + side_w, card_h - 18), radius=14, fill=BLACK_METAL)
    nav = [("All Clips", True), ("Favorites", False), ("Collections", False),
           ("Recently Removed", False), ("Quick Paste", False)]
    ny = body_top + 26
    for label, active in nav:
        if active:
            d.rounded_rectangle((34, ny - 8, 18 + side_w - 16, ny + 26), radius=10, fill=(20, 30, 30))
        dot = PROOF_TEAL_BRIGHT if active else MUTED_TEXT
        d.ellipse((50, ny + 6, 60, ny + 16), fill=dot)
        d.text((74, ny), label, font=_font(19, bold=active),
               fill=PROOF_TEAL_BRIGHT if active else MUTED_TEXT)
        ny += 52
    d.line((50, ny + 8, 18 + side_w - 24, ny + 8), fill=VAULT_BORDER, width=1)
    d.text((50, ny + 24), "Your data. Your", font=_font(15), fill=MUTED_TEXT)
    d.text((50, ny + 46), "vault. Your proof.", font=_font(15), fill=MUTED_TEXT)

    main_x = 18 + side_w + 22
    main_w = card_w - main_x - 18
    sb_h = 50
    d.rounded_rectangle((main_x, body_top, main_x + main_w, body_top + sb_h),
                        radius=12, fill=ROW_BG, outline=VAULT_BORDER, width=1)
    d.text((main_x + 22, body_top + 14), "Search your vault...",
           font=_font(19), fill=MUTED_TEXT)
    mgx, mgy = main_x + main_w - 36, body_top + sb_h // 2
    d.ellipse((mgx - 11, mgy - 11, mgx + 5, mgy + 5), outline=PROOF_TEAL, width=3)
    d.line((mgx + 4, mgy + 4, mgx + 11, mgy + 11), fill=PROOF_TEAL, width=3)

    ry = body_top + sb_h + 18
    row_h = 92
    for kind, text, tag, gold in CLIPS:
        d.rounded_rectangle((main_x, ry, main_x + main_w, ry + row_h - 14),
                            radius=12, fill=ROW_BG, outline=VAULT_BORDER, width=1)
        bcol = BADGE[kind]
        d.rounded_rectangle((main_x + 16, ry + 16, main_x + 16 + 64, ry + 16 + 28),
                            radius=8, fill=(22, 28, 34), outline=bcol, width=2)
        bf = _font(15, bold=True)
        bb = d.textbbox((0, 0), kind, font=bf)
        d.text((main_x + 16 + (64 - (bb[2] - bb[0])) // 2, ry + 19), kind, font=bf, fill=bcol)
        is_code = kind == "CODE"
        d.text((main_x + 96, ry + 16), text,
               font=_font(19, mono=is_code), fill=RECEIPT_WHITE)
        tcol = STAMP_GOLD if gold else MUTED_TEXT
        d.text((main_x + 96, ry + 46), f"• {tag}", font=_font(15), fill=tcol)
        ry += row_h
    return img


def render(square: bool) -> Path:
    if square:
        W = H = 1200
        out = ASSETS / "cache-vault-linkedin.png"
    else:
        W, H = 1200, 630
        out = ASSETS / "cache-vault-linkedin-wide.png"

    img = _gradient(W, H)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((30, 30, W - 30, H - 30), radius=26, outline=(255, 255, 255), width=1)

    if square:
        _logo(d, 96, 120, scale=0.95)
        d.text((168, 78), "Cache Vault", font=_font(74, bold=True), fill=RECEIPT_WHITE)
        d.text((170, 162), "Copied work should not disappear.",
               font=_font(30, bold=True), fill=PROOF_TEAL_BRIGHT)
        cx = 64
        for i, (label, fg, bd) in enumerate([
            ("Local-first", PROOF_TEAL_BRIGHT, PROOF_TEAL),
            ("No cloud account", RECEIPT_WHITE, VAULT_BORDER),
            ("No subscription", RECEIPT_WHITE, VAULT_BORDER),
            ("You own your data", RECEIPT_WHITE, VAULT_BORDER),
        ]):
            cx = _chip(d, cx, 230, label, _font(20, bold=True), fg, bd) + 16

        sx, sy = 64, 300
        shot = _load_shot(W - 128)
        if shot is not None:
            d.rounded_rectangle((sx - 3, sy - 3, sx + shot.size[0] + 3, sy + shot.size[1] + 3),
                                radius=21, outline=PROOF_TEAL, width=2)
            img.paste(shot, (sx, sy), shot)
        else:
            win = _window(W - 128, 648)
            img.paste(win, (sx, sy), win)
        img = img.convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((64, H - 64), "Built by The Proof Foundry™", font=_font(22, bold=True), fill=MUTED_TEXT)
        rt = "Free version out now"
        rb = d.textbbox((0, 0), rt, font=_font(22, bold=True))
        d.text((W - 64 - (rb[2] - rb[0]), H - 64), rt, font=_font(22, bold=True), fill=PROOF_TEAL_BRIGHT)
    else:
        _logo(d, 120, H // 2 - 10, scale=1.1)
        x = 224
        d.text((x, 120), "Cache Vault", font=_font(70, bold=True), fill=RECEIPT_WHITE)
        d.text((x, 206), "Copied work should not disappear.",
               font=_font(34, bold=True), fill=PROOF_TEAL_BRIGHT)
        d.text((x, 286), "A local-first Windows clipboard vault.",
               font=_font(28), fill=RECEIPT_WHITE)
        cx = x
        for label, fg, bd in [
            ("No cloud account", RECEIPT_WHITE, VAULT_BORDER),
            ("No subscription", RECEIPT_WHITE, VAULT_BORDER),
            ("You own your data", PROOF_TEAL_BRIGHT, PROOF_TEAL),
        ]:
            cx = _chip(d, cx, 360, label, _font(22, bold=True), fg, bd) + 16
        d.text((x, 470), "Built by The Proof Foundry™  ·  Free version out now",
               font=_font(24, bold=True), fill=MUTED_TEXT)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True)
    print(f"Wrote {out.relative_to(ROOT)} ({img.size[0]}x{img.size[1]})")
    return out


def main() -> None:
    render(square=True)
    render(square=False)


if __name__ == "__main__":
    main()
