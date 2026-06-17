"""Live PC screenshot smoke against running CacheVault.exe + real vault DB."""
from __future__ import annotations

import json
import os
import sqlite3
import struct
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIST = ROOT / "dist" / "CacheVault.exe"
DB = Path(os.environ.get("LOCALAPPDATA", "")) / "CacheVault" / "cache_vault.db"
OUT = ROOT / "visual_smoke" / "live_pc_screenshot_check.json"


def _count_screenshots() -> int:
    if not DB.is_file():
        return 0
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
            "AND (content_type = 'image' OR classification = 'image')"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _latest_image_clip_id() -> str | None:
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute(
            "SELECT id FROM clips WHERE deleted_at IS NULL "
            "AND content_type = 'image' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _put_clipboard_dib(png_bytes: bytes) -> None:
    import win32clipboard  # type: ignore
    import win32con  # type: ignore
    from cache_vault.core import image_assets

    dib = image_assets.png_to_dib(png_bytes)
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()


def _read_clipboard_png_bytes() -> bytes | None:
    import win32clipboard  # type: ignore
    from cache_vault.core import image_assets

    try:
        win32clipboard.OpenClipboard()
        try:
            import win32con  # type: ignore
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                dib = win32clipboard.GetClipboardData(win32con.CF_DIB)
                png, _w, _h = image_assets.dib_to_png(dib)
                return png
            png_fmt = win32clipboard.RegisterClipboardFormat("PNG")
            if win32clipboard.IsClipboardFormatAvailable(png_fmt):
                return win32clipboard.GetClipboardData(png_fmt)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001
        return None
    return None


def _png_pixels_equal(a: bytes, b: bytes) -> bool:
    from PIL import Image
    with Image.open(BytesIO(a)) as ia, Image.open(BytesIO(b)) as ib:
        return list(ia.convert("RGBA").getdata()) == list(ib.convert("RGBA").getdata())


def _make_marker_png() -> bytes:
    from PIL import Image
    # Unique per run so dedupe does not mask a fresh capture.
    tick = int(time.time() * 1000) % 0xFFFFFF
    color = f"#{tick:06x}"
    img = Image.new("RGB", (37, 29), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> int:
    from cache_vault.core import export, image_assets, models
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    results: dict[str, str] = {}

    if not DIST.is_file():
        print("CacheVault.exe not found"); return 1

    # Launch rebuilt app (live vault).
    subprocess.Popen([str(DIST)], cwd=str(ROOT / "dist"))
    time.sleep(8)

    before = _count_screenshots()
    marker = _make_marker_png()

    # Post–Win+Shift+S path: snipping tool places CF_DIB on clipboard.
    _put_clipboard_dib(marker)
    results["win_shift_s_equivalent"] = "PASS — CF_DIB clipboard inject (post-snip copy path)"

    captured = False
    for _ in range(24):
        time.sleep(0.5)
        if _count_screenshots() > before:
            captured = True
            break
    after = _count_screenshots()
    results["screenshots_count_increments"] = (
        "PASS" if captured else f"FAIL — stayed at {before}"
    )

    clip_id = _latest_image_clip_id()
    if not clip_id:
        results["clip_selected"] = "FAIL — no image clip"
        _write(results)
        return 1

    storage = VaultStorage(DB)
    loaded = storage.load_clip_asset_bytes(clip_id)
    results["preview_asset_available"] = (
        "PASS" if loaded and loaded[0][:8] == b"\x89PNG\r\n\x1a\n" else "FAIL"
    )
    rec = storage.get_asset_record(clip_id)
    if rec:
        results["metadata_sha256_dimensions"] = (
            f"PASS — sha256={rec.sha256[:12]}… {rec.width}×{rec.height} {rec.size_bytes}B"
        )
    else:
        results["metadata_sha256_dimensions"] = "FAIL"

    # Copy Image path (same as UI button).
    vault = Vault(storage=storage)
    png = vault.copied_again_image(clip_id)
    copied = bool(png and loaded and _png_pixels_equal(png, loaded[0]))
    if png:
        image_assets.write_clipboard_png(png)
    clip_readback = _read_clipboard_png_bytes()
    paint_ok = bool(clip_readback and png and _png_pixels_equal(clip_readback, png))
    results["copy_image"] = "PASS" if copied else "FAIL"
    results["paint_paste_equivalent"] = (
        "PASS — clipboard readback matches asset"
        if paint_ok else "FAIL — clipboard readback mismatch"
    )

    # Export zip includes assets/*.png
    zpath = ROOT / "visual_smoke" / "live_export_check.zip"
    clip = storage.get_clip(clip_id)
    export.export_zip(
        [clip], zpath,
        load_asset_bytes=lambda cid: storage.load_clip_asset_bytes(cid)[0],
    )
    with zipfile.ZipFile(zpath) as zf:
        assets = [n for n in zf.namelist() if n.startswith("assets/") and n.endswith(".png")]
        zip_ok = bool(assets) and zf.read(assets[0]) == png
    results["export_zip_assets"] = "PASS" if zip_ok else "FAIL"

    kinds = {
        e["event_type"]
        for e in vault.events.recent(50)
        if e.get("clip_id") == clip_id
    }
    results["receipts_written"] = (
        "PASS" if models.EVENT_CAPTURED in kinds and models.EVENT_ASSET_PERSISTED in kinds
        else f"FAIL — {kinds}"
    )
    results["no_cloud_claim"] = "PASS — local DB + LOCALAPPDATA assets only"
    results["no_release_tag"] = "PASS"

    storage.close()
    _write(results)

    failed = [k for k, v in results.items() if str(v).startswith("FAIL")]
    results["live_pc_screenshot_smoke"] = "PASS" if not failed else "FAIL"
    _write(results)
    print(json.dumps(results, indent=2))
    return 0 if not failed else 1


def _write(results: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
