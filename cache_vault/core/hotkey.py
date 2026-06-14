"""Global (system-wide) hotkey support + paste helper.

Uses the Win32 ``RegisterHotKey`` API on a dedicated thread with its own
message loop, so the hotkey works regardless of which application is focused.
Requires ``pywin32``; without it the listener is a no-op and the feature is
simply unavailable (the rest of the app is unaffected).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:  # pragma: no cover - optional dependency / Windows only
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore
    _HAS_WIN32 = True
except Exception:  # noqa: BLE001
    _HAS_WIN32 = False


# Win32 modifier flags.
_MODS = {
    "ctrl": 0x0002, "control": 0x0002,
    "alt": 0x0001,
    "shift": 0x0004,
    "win": 0x0008, "super": 0x0008, "meta": 0x0008,
}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312

_NAMED_VK = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B, "insert": 0x2D, "ins": 0x2D,
    "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    **{f"f{n}": 0x70 + (n - 1) for n in range(1, 13)},
}


def _vk_for(key: str) -> Optional[int]:
    key = key.lower()
    if len(key) == 1:
        return ord(key.upper())
    return _NAMED_VK.get(key)


def parse_hotkey(spec: str) -> tuple[int, Optional[int]]:
    """Turn ``"ctrl+shift+v"`` into ``(modifier_flags, virtual_key_code)``.

    Returns ``vk = None`` when the spec has no usable main key.
    """
    mods = 0
    vk: Optional[int] = None
    for part in spec.lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in _MODS:
            mods |= _MODS[part]
        else:
            vk = _vk_for(part)
    return mods, vk


def normalize_hotkey(spec: str) -> str:
    """Human-readable, canonical form for display, e.g. ``Ctrl+Shift+V``."""
    order = ["ctrl", "alt", "shift", "win"]
    seen = set()
    mod_parts: list[str] = []
    key_part = ""
    for part in spec.lower().replace(" ", "").split("+"):
        canon = {"control": "ctrl", "super": "win", "meta": "win"}.get(part, part)
        if canon in _MODS and canon not in seen:
            seen.add(canon)
        elif canon not in _MODS and part:
            key_part = part.upper() if len(part) == 1 else part.capitalize()
    for m in order:
        if m in seen:
            mod_parts.append(m.capitalize())
    return "+".join(mod_parts + ([key_part] if key_part else []))


class HotkeyListener:
    """Registers a single global hotkey and calls ``on_activate`` when pressed.

    The callback runs on the listener thread; UI code should marshal back to
    the main thread (the shell uses ``after``).
    """

    def __init__(self, spec: str, on_activate: Callable[[], None]):
        self._spec = spec
        self._on_activate = on_activate
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._registered = False

    @property
    def available(self) -> bool:
        return _HAS_WIN32

    @property
    def registered(self) -> bool:
        return self._registered

    def start(self) -> None:
        if not _HAS_WIN32 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="hotkey-listener",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not _HAS_WIN32 or not self._hwnd:
            return
        try:
            if self._registered:
                win32gui.UnregisterHotKey(self._hwnd, 1)
            win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:  # noqa: BLE001
            pass

    def _run(self) -> None:  # pragma: no cover - needs Windows desktop
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == _WM_HOTKEY:
                try:
                    self._on_activate()
                except Exception:  # noqa: BLE001
                    pass
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "CacheVaultHotkey"
        wc.lpfnWndProc = wndproc
        atom = win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(
            atom, "CacheVaultHotkey", 0, 0, 0, 0, 0, 0, 0, 0, None)

        mods, vk = parse_hotkey(self._spec)
        if vk is not None:
            try:
                win32gui.RegisterHotKey(self._hwnd, 1, mods | _MOD_NOREPEAT, vk)
                self._registered = True
            except Exception:  # noqa: BLE001 - hotkey may be taken by another app
                self._registered = False
        win32gui.PumpMessages()


def focus_and_paste(hwnd) -> None:
    """Restore focus to ``hwnd`` (the app the user was in) and send Ctrl+V."""
    if not _HAS_WIN32:
        return
    try:
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.05)
    vk_ctrl, vk_v, keyup = 0x11, 0x56, 0x0002
    try:
        win32api.keybd_event(vk_ctrl, 0, 0, 0)
        win32api.keybd_event(vk_v, 0, 0, 0)
        win32api.keybd_event(vk_v, 0, keyup, 0)
        win32api.keybd_event(vk_ctrl, 0, keyup, 0)
    except Exception:  # noqa: BLE001
        pass


def foreground_window():
    """Handle of the currently focused window, or ``None``."""
    if not _HAS_WIN32:
        return None
    try:
        return win32gui.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        return None
