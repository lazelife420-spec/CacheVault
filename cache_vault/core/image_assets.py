"""Screenshot/image asset file storage under Cache Vault app data."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image


@dataclass
class ClipAssetRecord:
    asset_id: str
    clip_id: str
    mime_type: str
    file_ext: str
    size_bytes: int
    sha256: str
    created_at: str
    original_name: str | None
    storage_name: str
    width: int | None = None
    height: int | None = None


def assets_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "CacheVault" / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def dib_to_png(dib: bytes) -> tuple[bytes, int, int]:
    """Convert a Windows CF_DIB clipboard payload to PNG bytes."""
    if len(dib) < 40:
        raise ValueError("DIB too small")
    header_size = struct.unpack_from("<I", dib, 0)[0]
    if header_size < 40 or header_size > len(dib):
        raise ValueError("invalid DIB header size")
    bpp = struct.unpack_from("<H", dib, 14)[0]
    n_colors = struct.unpack_from("<I", dib, 32)[0]
    if bpp <= 8:
        if n_colors == 0:
            n_colors = 2 ** bpp
    else:
        n_colors = 0
    pixel_offset = header_size + n_colors * 4
    file_offset = 14 + pixel_offset
    bmp = b"BM" + struct.pack("<IHHI", len(dib) + 14, 0, 0, file_offset) + dib
    with Image.open(BytesIO(bmp)) as img:
        rgb = img.convert("RGBA")
        out = BytesIO()
        rgb.save(out, format="PNG")
        w, h = rgb.size
        return out.getvalue(), w, h


def png_dimensions(png: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(png)) as img:
        return img.size


def write_asset_file(storage_name: str, data: bytes) -> Path:
    path = assets_dir() / storage_name
    path.write_bytes(data)
    return path


def read_asset_file(storage_name: str) -> bytes | None:
    path = assets_dir() / storage_name
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_asset_file(storage_name: str) -> None:
    path = assets_dir() / storage_name
    if path.is_file():
        path.unlink()


def make_storage_name(clip_id: str, ext: str = "png") -> str:
    return f"{clip_id}.{ext.lstrip('.')}"


def image_preview_label(width: int, height: int, mime: str = "image/png") -> str:
    kind = "Screenshot" if mime == "image/png" else "Image"
    if width and height:
        return f"{kind} ({width}×{height})"
    return kind


def image_content_label(width: int, height: int) -> str:
    if width and height:
        return f"[Screenshot PNG {width}×{height}]"
    return "[Screenshot PNG]"


def png_to_dib(png_bytes: bytes) -> bytes:
    """Convert PNG bytes to a Windows CF_DIB payload (no BMP file header)."""
    with Image.open(BytesIO(png_bytes)) as img:
        rgb = img.convert("RGB")
        with BytesIO() as out:
            rgb.save(out, format="BMP")
            bmp = out.getvalue()
    # Drop the 14-byte BITMAPFILEHEADER; CF_DIB is the DIB only.
    return bmp[14:]


def write_clipboard_png(png_bytes: bytes) -> bool:
    """Put a PNG on the Windows clipboard. Returns False if unavailable."""
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore
    except Exception:  # noqa: BLE001
        return False
    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            try:
                png_fmt = win32clipboard.RegisterClipboardFormat("PNG")
                win32clipboard.SetClipboardData(png_fmt, png_bytes)
            except Exception:  # noqa: BLE001
                dib = png_to_dib(png_bytes)
                win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:  # noqa: BLE001
        return False
