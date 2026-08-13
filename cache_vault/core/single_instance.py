"""Ensure only one Cache Vault desktop instance runs at a time."""

from __future__ import annotations

import sys


_MUTEX_NAME = "Local\\CacheVaultSingleInstance_v1"
_mutex_handle = None


def _raise_existing_window() -> bool:
    """Best-effort: restore an already-running Cache Vault main window.

    Returns True if a window was found and restored; False otherwise.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        target = "Cache Vault"
        found: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd) and user32.IsIconic(hwnd) == 0:
                # withdrawn windows may not be visible — still try title match
                pass
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            title = buf.value
            if title.startswith(target):
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        for hwnd in found:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
        return False
    except Exception:  # noqa: BLE001
        return False


def claim_or_exit() -> None:
    """Exit with a friendly message if another instance already holds the lock."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        global _mutex_handle
        _mutex_handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if _raise_existing_window():
                raise SystemExit(0)
            user32.MessageBoxW(
                0,
                "Cache Vault is already running.\n"
                "Right-click the tray icon and choose Open Cache Vault.",
                "Cache Vault",
                0x40,  # MB_ICONINFORMATION
            )
            raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - best effort; never block launch
        return
