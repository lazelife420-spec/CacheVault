from __future__ import annotations

import sys
import io
from types import SimpleNamespace

import pytest

from PIL import Image

from cache_vault.core import image_assets


def _make_sample_png() -> bytes:
    with Image.new("RGBA", (8, 8), (255, 0, 0, 255)) as im:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()


@pytest.mark.skipif(sys.platform != "win32", reason="Clipboard image test requires Windows")
def test_write_clipboard_png_places_image_on_windows_clipboard():
    """Attempt to write a PNG to the Windows clipboard and verify a format exists.

    This test is guarded and will be skipped on non-Windows systems or CI without
    pywin32 installed.
    """
    png = _make_sample_png()
    # Should return True when win32clipboard is available and writable.
    ok = image_assets.write_clipboard_png(png)
    assert ok is True, "write_clipboard_png should return True when clipboard available"

    # Try to read back a registered PNG clipboard format to ensure image data present.
    try:
        import win32clipboard
    except Exception as exc:  # pragma: no cover - platform-dependent
        pytest.skip(f"pywin32 not available: {exc}")

    win32clipboard.OpenClipboard()
    try:
        png_fmt = win32clipboard.RegisterClipboardFormat("PNG")
        try:
            data = win32clipboard.GetClipboardData(png_fmt)
        except Exception:
            # Fall back to CF_DIB if PNG format not stored
            from win32con import CF_DIB

            data = win32clipboard.GetClipboardData(CF_DIB)
        assert data, "Clipboard should contain image data (PNG or DIB)"
    finally:
        win32clipboard.CloseClipboard()
