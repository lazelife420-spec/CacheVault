"""Screenshot/image asset file storage under Cache Vault app data."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from . import models


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


# Image MIME types accepted from the mobile Share Sheet, mapped to file ext.
_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}
ALLOWED_IMAGE_MIME = frozenset(_MIME_EXT)


def ext_for_mime(mime_type: str) -> str:
    """File extension for an accepted image MIME type ('bin' if unknown)."""
    return _MIME_EXT.get((mime_type or "").lower().strip(), "bin")


def image_dimensions(data: bytes) -> tuple[int, int]:
    """Best-effort ``(width, height)`` for image bytes; ``(0, 0)`` if undecodable."""
    try:
        with Image.open(BytesIO(data)) as img:
            return img.size
    except Exception:  # noqa: BLE001 - any decode failure -> unknown size
        return (0, 0)


def is_decodable_image(data: bytes) -> bool:
    """True when ``data`` is a real image Pillow can open (anti-spoof guard)."""
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:  # noqa: BLE001
        return False


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


def canonical_image_fingerprint(png_bytes: bytes) -> str | None:
    """Return a stable fingerprint for image custody matching.

    Windows CF_DIB discards alpha and stores opaque RGB pixels. The monitor
    reads the DIB and converts it back to PNG, so a source PNG and its
    clipboard round-trip can have different byte encodings. This helper
    simulates that round-trip and hashes the canonical RGB pixel buffer
    (mode, width, height, decoded bytes) so the writer and monitor agree.
    """
    try:
        dib = png_to_dib(png_bytes)
        captured_png, width, height = dib_to_png(dib)
        with Image.open(BytesIO(captured_png)) as img:
            rgb = img.convert("RGB")
            pixels = rgb.tobytes()
        return models.bytes_hash(f"RGB:{width}:{height}:".encode() + pixels)
    except Exception:  # noqa: BLE001
        return None


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


def deletion_quarantine_dir() -> Path:
    """App-owned staging area for permanent deletion, on the same volume
    as ``assets_dir()`` so moves into/out of it can use an atomic rename
    (``os.replace``) rather than a copy+delete.
    """
    path = assets_dir().parent / "deletion_quarantine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_managed_path(storage_name: str) -> Path | None:
    """Resolve ``storage_name`` to its canonical on-disk path and confirm
    it is genuinely inside ``assets_dir()`` -- returns ``None`` (never a
    path) for anything that isn't a safe, unambiguous managed-asset file.

    Guards against:
    - path traversal in ``storage_name`` itself (``..``, path separators)
    - a symlink/reparse point placed inside the assets dir whose real
      target resolves outside it (``Path.resolve()`` follows the link,
      so the containment check below catches this automatically)
    - any other resolution failure (permission errors, broken links)

    This must be the only way permanent-deletion code touches a path on
    disk -- never build a path from ``storage_name`` directly.
    """
    if not storage_name:
        return None
    raw = Path(storage_name)
    if raw.is_absolute() or ".." in raw.parts or len(raw.parts) != 1:
        return None
    root = assets_dir().resolve()
    candidate = assets_dir() / storage_name
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _slugify(value: str) -> str:
    """Make a filesystem-safe lowercase slug from a value.

    Replace non-alphanumeric characters with '-', collapse runs, and strip
    leading/trailing '-'. Keep it short.
    """
    import re

    if not value:
        return "unknown"
    s = value.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s[:40] or "unknown"


def make_smart_filename(clip) -> str:
    """Generate a smart filename for an image clip.

    Format: CacheVault_<kind>_<source-app>_<YYYY-MM-DD>_<HHmmss>_<short-id>.png
    Falls back to sensible defaults when metadata is missing.
    """
    from datetime import datetime, timezone

    kind = "screenshot" if getattr(clip, "content_type", "") == "image" or getattr(clip, "classification", "") == "screenshot" else "image"
    source = getattr(clip, "source_app", None) or getattr(clip, "capture_mode", None) or "unknown"
    source_slug = _slugify(str(source))
    created = getattr(clip, "created_at", None)
    try:
        dt = datetime.fromisoformat(created) if created else datetime.now(timezone.utc)
    except Exception:
        # created may be a short date or None
        try:
            dt = datetime.strptime(str(created), "%Y-%m-%d")
        except Exception:
            dt = datetime.now(timezone.utc)
    date = dt.strftime("%Y-%m-%d")
    timestr = dt.strftime("%H%M%S")
    short_id = (getattr(clip, "id", "") or "")[:6]
    if not short_id:
        import uuid

        short_id = uuid.uuid4().hex[:6]
    name = f"CacheVault_{kind}_{source_slug}_{date}_{timestr}_{short_id}.png"
    return name


def next_available_path(path: Path) -> Path:
    """Return a Path that doesn't overwrite existing files by appending -2, -3, etc."""
    if not path.exists():
        return path
    base = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        new = parent / f"{base}-{i}{suffix}"
        if not new.exists():
            return new
        i += 1


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
        dib = png_to_dib(png_bytes)
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            # CF_DIB is what most Windows apps (Paint, Word, Discord) expect.
            win32clipboard.SetClipboardData(win32con.CF_DIB, dib)
            try:
                png_fmt = win32clipboard.RegisterClipboardFormat("PNG")
                win32clipboard.SetClipboardData(png_fmt, png_bytes)
            except Exception:  # noqa: BLE001
                pass
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:  # noqa: BLE001
        return False


def clipboard_has_image() -> bool:
    """Return True if the Windows clipboard currently contains image data.

    This function is best-effort and returns False on non-Windows platforms
    or when clipboard APIs are unavailable.
    """
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore
    except Exception:  # noqa: BLE001
        return False
    try:
        win32clipboard.OpenClipboard()
        try:
            # Check for PNG registered format first
            png_fmt = win32clipboard.RegisterClipboardFormat("PNG")
            if win32clipboard.IsClipboardFormatAvailable(png_fmt):
                return True
            # Fall back to CF_DIB
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return True
            return False
        finally:
            win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001
        return False
