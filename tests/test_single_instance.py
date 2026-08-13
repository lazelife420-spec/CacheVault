from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
import pytest

from cache_vault.core import single_instance


def test_raise_existing_window_returns_bool_non_windows():
    with patch("sys.platform", "linux"):
        assert single_instance._raise_existing_window() is False


def test_claim_or_exit_exits_silently_on_successful_raise():
    mock_kernel32 = MagicMock()
    mock_kernel32.GetLastError.return_value = 183
    mock_user32 = MagicMock()

    ctypes_mock = MagicMock()
    ctypes_mock.windll.kernel32 = mock_kernel32
    ctypes_mock.windll.user32 = mock_user32

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": ctypes_mock}), \
         patch("cache_vault.core.single_instance._raise_existing_window", return_value=True):
        with pytest.raises(SystemExit) as exc_info:
            single_instance.claim_or_exit()
        assert exc_info.value.code == 0
        mock_user32.MessageBoxW.assert_not_called()


def test_claim_or_exit_shows_dialog_on_failed_raise():
    mock_kernel32 = MagicMock()
    mock_kernel32.GetLastError.return_value = 183
    mock_user32 = MagicMock()

    ctypes_mock = MagicMock()
    ctypes_mock.windll.kernel32 = mock_kernel32
    ctypes_mock.windll.user32 = mock_user32

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": ctypes_mock}), \
         patch("cache_vault.core.single_instance._raise_existing_window", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            single_instance.claim_or_exit()
        assert exc_info.value.code == 0
        mock_user32.MessageBoxW.assert_called_once()
