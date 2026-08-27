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


# --- profile-scoped mutex (v0.2.2 isolated-launch patch) ------------------


def test_mutex_name_default_matches_original_fixed_name():
    """profile_dir=None must return the exact original constant -- a real
    launch's mutex name must not change, or two real instances could
    silently stop excluding each other."""
    assert single_instance._mutex_name(None) == single_instance._MUTEX_NAME
    assert single_instance._mutex_name("") == single_instance._MUTEX_NAME


def test_mutex_name_isolated_differs_from_default():
    scoped = single_instance._mutex_name("C:/some/isolated/profile")
    assert scoped != single_instance._MUTEX_NAME
    assert scoped.startswith(single_instance._MUTEX_NAME)


def test_mutex_name_isolated_differs_between_profiles():
    a = single_instance._mutex_name("C:/profile-a")
    b = single_instance._mutex_name("C:/profile-b")
    assert a != b


def test_mutex_name_isolated_stable_for_same_profile():
    a = single_instance._mutex_name("C:/same-profile")
    b = single_instance._mutex_name("C:/same-profile")
    assert a == b


def test_mutex_name_isolated_normalizes_case_and_relative_form(tmp_path):
    """Two spellings of the same real directory must scope to the same
    mutex name (resolved + lowercased), so isolation-scoping can't be
    accidentally bypassed by path-casing differences."""
    target = tmp_path / "Profile"
    target.mkdir()
    upper = str(target).upper()
    lower = str(target).lower()
    assert single_instance._mutex_name(upper) == single_instance._mutex_name(lower)


def test_claim_or_exit_isolated_never_raises_existing_window():
    """The core safety guarantee: with profile_dir set, claim_or_exit must
    never call _raise_existing_window(), even when the (scoped) mutex
    collides -- an isolated launch must never bring any window, real-profile
    or otherwise, to the foreground."""
    mock_kernel32 = MagicMock()
    mock_kernel32.GetLastError.return_value = 183
    mock_user32 = MagicMock()

    ctypes_mock = MagicMock()
    ctypes_mock.windll.kernel32 = mock_kernel32
    ctypes_mock.windll.user32 = mock_user32

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": ctypes_mock}), \
         patch("cache_vault.core.single_instance._raise_existing_window") as mock_raise:
        with pytest.raises(SystemExit) as exc_info:
            single_instance.claim_or_exit(profile_dir="C:/isolated/profile")
        assert exc_info.value.code == 0
        mock_raise.assert_not_called()
        mock_user32.MessageBoxW.assert_called_once()


def test_claim_or_exit_isolated_uses_scoped_mutex_name():
    """CreateMutexW must be called with the isolated (scoped) name, not the
    fixed default, when profile_dir is supplied."""
    mock_kernel32 = MagicMock()
    mock_kernel32.GetLastError.return_value = 0  # no collision
    mock_user32 = MagicMock()

    ctypes_mock = MagicMock()
    ctypes_mock.windll.kernel32 = mock_kernel32
    ctypes_mock.windll.user32 = mock_user32

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": ctypes_mock}):
        single_instance.claim_or_exit(profile_dir="C:/isolated/profile")

    called_name = mock_kernel32.CreateMutexW.call_args[0][2]
    assert called_name == single_instance._mutex_name("C:/isolated/profile")
    assert called_name != single_instance._MUTEX_NAME


def test_claim_or_exit_default_still_uses_fixed_mutex_name():
    """Regression guard: a normal (profile_dir=None) launch must keep using
    the exact original fixed mutex name -- no behavior change for real
    users."""
    mock_kernel32 = MagicMock()
    mock_kernel32.GetLastError.return_value = 0  # no collision
    mock_user32 = MagicMock()

    ctypes_mock = MagicMock()
    ctypes_mock.windll.kernel32 = mock_kernel32
    ctypes_mock.windll.user32 = mock_user32

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"ctypes": ctypes_mock}):
        single_instance.claim_or_exit()

    called_name = mock_kernel32.CreateMutexW.call_args[0][2]
    assert called_name == single_instance._MUTEX_NAME
