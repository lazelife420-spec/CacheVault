"""Windows-specific mouse side-button handling for navigation."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable

try:
    _user32 = ctypes.windll.user32  # Windows only
    _HAS_WIN32 = True
except (AttributeError, OSError):
    _user32 = None
    _HAS_WIN32 = False

logger = logging.getLogger(__name__)

# Constants
WM_XBUTTONDOWN = 0x020B
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
GWLP_WNDPROC = -4

# Pointer-sized signed integer (LONG_PTR / LRESULT). Using the *Ptr* variants
# below is mandatory on 64-bit Python: the legacy SetWindowLong/GetWindowLong
# truncate WndProc pointers to 32 bits and corrupt the window subclass.
LONG_PTR = ctypes.c_ssize_t

if _HAS_WIN32:
    WNDPROC_TYPE = ctypes.WINFUNCTYPE(
        LONG_PTR,          # LRESULT
        wintypes.HWND,     # HWND
        wintypes.UINT,     # UINT
        wintypes.WPARAM,   # WPARAM
        wintypes.LPARAM    # LPARAM
    )

    # SetWindowLongPtrW/GetWindowLongPtrW only exist on 64-bit user32; on 32-bit
    # Windows they are header macros for the *W variants, so fall back to those.
    _set_window_long = getattr(_user32, "SetWindowLongPtrW", None) or _user32.SetWindowLongW
    _get_window_long = getattr(_user32, "GetWindowLongPtrW", None) or _user32.GetWindowLongW
    _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
    _set_window_long.restype = LONG_PTR
    _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_window_long.restype = LONG_PTR
    _user32.CallWindowProcW.argtypes = [
        LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    _user32.CallWindowProcW.restype = LONG_PTR
    _user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    _user32.DefWindowProcW.restype = LONG_PTR

class WinMouseHandler:
    """Hooks a window's WndProc to listen for physical side-mouse buttons."""

    def __init__(self, hwnd: int, on_back: Callable, on_forward: Callable):
        self._hwnd = hwnd
        self._on_back = on_back
        self._on_forward = on_forward
        self._old_wndproc = None
        self._new_wndproc_ptr = None
        self._active = False

        if not _HAS_WIN32:
            return

        try:
            # We must keep a reference to the callback to prevent GC.
            self._new_wndproc_ptr = WNDPROC_TYPE(self._wndproc)
            new_ptr = ctypes.cast(self._new_wndproc_ptr, ctypes.c_void_p).value

            # Subclass the window (pointer-safe on 64-bit).
            res = _set_window_long(self._hwnd, GWLP_WNDPROC, new_ptr)
            if res:
                self._old_wndproc = res
                self._active = True
                logger.info("Native mouse back/forward handler registered for HWND %s", hwnd)
        except Exception as exc:
            logger.error("Failed to register native mouse handler: %s", exc)

    def _wndproc(self, hwnd, msg, wparam, lparam) -> int:
        if msg == WM_XBUTTONDOWN:
            # high word of wparam tells us which button
            button = (wparam >> 16) & 0xFFFF
            if button == XBUTTON1:
                self._on_back()
                return 1 # Message handled
            elif button == XBUTTON2:
                self._on_forward()
                return 1 # Message handled
        
        # Fallback to original wndproc
        if self._old_wndproc:
            return _user32.CallWindowProcW(self._old_wndproc, hwnd, msg, wparam, lparam)
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def stop(self) -> None:
        if self._active and self._old_wndproc:
            try:
                _set_window_long(self._hwnd, GWLP_WNDPROC, self._old_wndproc)
                logger.info("Native mouse handler detached.")
            except Exception as exc:
                logger.error("Error detaching native mouse handler: %s", exc)
            self._active = False
            self._old_wndproc = None
            self._new_wndproc_ptr = None

def install_mouse_handler(root, on_back: Callable, on_forward: Callable) -> WinMouseHandler | None:
    if not _HAS_WIN32:
        return None
    try:
        # Get actual HWND from Tkinter
        hwnd = root.winfo_id()
        return WinMouseHandler(hwnd, on_back, on_forward)
    except Exception as exc:
        logger.error("Could not install mouse handler: %s", exc)
        return None
