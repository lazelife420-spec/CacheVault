"""Regression and retry test for DEF-008: Image Clipboard Contention Handling."""

from unittest.mock import MagicMock, patch
import pytest

from cache_vault.core import image_assets
from cache_vault.core.image_assets import write_clipboard_png, clipboard_has_image


# 1x1 Red PNG byte stream for testing
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01"
    b"\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_write_clipboard_png_no_contention():
    """Verify write_clipboard_png succeeds when OpenClipboard works on attempt 1."""
    mock_win32cb = MagicMock()
    mock_win32con = MagicMock()
    mock_win32con.CF_DIB = 8

    with patch.dict("sys.modules", {"win32clipboard": mock_win32cb, "win32con": mock_win32con}), \
         patch("cache_vault.core.image_assets.png_to_dib", return_value=b"mock_dib"):
        success = write_clipboard_png(TINY_PNG_BYTES)
        assert success is True
        mock_win32cb.OpenClipboard.assert_called_once()
        mock_win32cb.CloseClipboard.assert_called_once()


def test_write_clipboard_png_transient_contention():
    """Verify write_clipboard_png retries and succeeds when transiently locked."""
    mock_win32cb = MagicMock()
    mock_win32con = MagicMock()

    # Fail twice with pywintypes.error / Exception, succeed on 3rd try
    attempts = [0]
    def open_cb_side_effect():
        attempts[0] += 1
        if attempts[0] < 3:
            raise Exception("Access denied / Clipboard locked")
        return None

    mock_win32cb.OpenClipboard.side_effect = open_cb_side_effect

    with patch.dict("sys.modules", {"win32clipboard": mock_win32cb, "win32con": mock_win32con}), \
         patch("cache_vault.core.image_assets.png_to_dib", return_value=b"mock_dib"), \
         patch("time.sleep"):
        success = write_clipboard_png(TINY_PNG_BYTES)
        assert success is True
        assert attempts[0] == 3
        mock_win32cb.CloseClipboard.assert_called_once()


def test_write_clipboard_png_exceeding_budget():
    """Verify write_clipboard_png returns False after budget exhaustion without hanging."""
    mock_win32cb = MagicMock()
    mock_win32con = MagicMock()
    mock_win32cb.OpenClipboard.side_effect = Exception("Clipboard permanently locked")

    with patch.dict("sys.modules", {"win32clipboard": mock_win32cb, "win32con": mock_win32con}), \
         patch("cache_vault.core.image_assets.png_to_dib", return_value=b"mock_dib"), \
         patch("time.sleep"):
        success = write_clipboard_png(TINY_PNG_BYTES)
        assert success is False
        assert mock_win32cb.OpenClipboard.call_count == 10
        mock_win32cb.CloseClipboard.assert_not_called()


def test_write_clipboard_png_invalid_input():
    """Verify write_clipboard_png fails safely on malformed PNG input."""
    success = write_clipboard_png(b"not a valid png payload")
    assert success is False
