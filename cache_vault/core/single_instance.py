"""Ensure only one Cache Vault desktop instance runs at a time.

The lock is a named Windows mutex. By default (no profile_dir) it uses a
fixed, unscoped name -- unchanged from before this module gained profile
awareness, so ordinary single-instance behavior for real users is identical
to what it has always been.

When a caller passes an explicit profile_dir (an isolated-launch profile,
e.g. via `app.py --profile-dir <path>`), the mutex name is instead derived
from that path. This is a hard isolation guarantee, not a best-effort one:
an isolated launch's mutex name can never collide with the real launch's
fixed name, and can never collide with a *different* isolated profile's
mutex either -- so an isolated launch can neither be blocked by, nor
silently redirected to, a real (or differently-scoped) instance.
"""

from __future__ import annotations

import sys


_MUTEX_NAME = "Local\\CacheVaultSingleInstance_v1"
_mutex_handle = None


def _mutex_name(profile_dir: str | None) -> str:
    """The mutex name to claim for this launch.

    profile_dir=None (the default/real launch) always returns the original
    fixed name, unchanged -- no behavior change for real users. A truthy
    profile_dir returns a name derived from that path's resolved, lowercased
    form, so two different isolated profiles (and the real profile) never
    share a name.
    """
    if not profile_dir:
        return _MUTEX_NAME
    import hashlib
    from pathlib import Path

    digest = hashlib.sha256(str(Path(profile_dir).resolve()).lower().encode("utf-8")).hexdigest()[:16]
    return f"{_MUTEX_NAME}_isolated_{digest}"


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


def claim_or_exit(profile_dir: str | None = None) -> None:
    """Exit with a friendly message if another instance already holds the
    lock for this exact scope.

    profile_dir=None preserves the original behavior exactly: fixed mutex
    name, and on collision, try to raise/focus an existing "Cache Vault"
    window before falling back to a message box.

    profile_dir set (an isolated launch) never calls
    _raise_existing_window() at all, even on collision -- an isolated launch
    must never bring a real-profile (or any other) window to the foreground.
    On collision it goes straight to the message box, then exits, exactly
    like the no-existing-window case always has.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        global _mutex_handle
        mutex_name = _mutex_name(profile_dir)
        _mutex_handle = kernel32.CreateMutexW(None, True, mutex_name)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if not profile_dir and _raise_existing_window():
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
