"""Optional 'start with Windows' support via the per-user registry Run key.

Per-user (``HKEY_CURRENT_USER``) only — no admin rights, no machine-wide
changes, fully reversible. Local-only, consistent with the product doctrine.
"""

from __future__ import annotations

import os
import sys

try:  # pragma: no cover - Windows only
    import winreg  # type: ignore
    _HAS_REG = True
except Exception:  # noqa: BLE001
    _HAS_REG = False

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "CacheVault"


def launch_command() -> str:
    """The command Windows should run at login.

    - Frozen (PyInstaller) build → just the exe path.
    - Dev run → ``pythonw app.py`` (pythonw avoids a console window).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pyw = exe.replace("python.exe", "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    app_py = os.path.join(_project_root(), "app.py")
    return f'"{exe}" "{app_py}"'


def _project_root() -> str:
    # cache_vault/core/startup.py -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def is_enabled() -> bool:
    if not _HAS_REG:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    if not _HAS_REG:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
        return True
    except OSError:
        return False


def disable() -> bool:
    if not _HAS_REG:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        return True  # already absent
    except OSError:
        return False


def sync(desired: bool) -> None:
    """Make the registry match ``desired`` (idempotent)."""
    if desired and not is_enabled():
        enable()
    elif not desired and is_enabled():
        disable()
