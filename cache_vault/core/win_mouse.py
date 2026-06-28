"""Windows-specific mouse side-button handling for navigation."""

from __future__ import annotations

import logging
from typing import Callable

try:
    import win32con
    import win32gui
    import ctypes
    from ctypes import wintypes

    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

logger = logging.getLogger(__name__)

# Constants
WM_XBUTTONDOWN = 0x020B
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
GWLP_WNDPROC = -4

if _HAS_WIN32:
    WNDPROC_TYPE = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,  # LRESULT
        wintypes.HWND,     # HWND
        wintypes.UINT,     # UINT
        wintypes.WPARAM,   # WPARAM
        wintypes.LPARAM    # LPARAM
    )

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
            # We must keep a reference to the callback to prevents GC
            self._new_wndproc_ptr = WNDPROC_TYPE(self._wndproc)
            
            # Subclass the window
            res = win32gui.SetWindowLong(self._hwnd, GWLP_WNDPROC, self._new_wndproc_ptr)
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
            return win32gui.CallWindowProc(self._old_wndproc, hwnd, msg, wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def stop(self) -> None:
        if self._active and self._old_wndproc:
            try:
                win32gui.SetWindowLong(self._hwnd, GWLP_WNDPROC, self._old_wndproc)
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
