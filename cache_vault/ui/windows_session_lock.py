"""Receive Windows interactive-session lock notifications for the main window."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable


class WindowsSessionLockListener:
    WM_WTSSESSION_CHANGE = 0x02B1
    WTS_SESSION_LOCK = 0x7
    NOTIFY_FOR_THIS_SESSION = 0
    GWLP_WNDPROC = -4

    def __init__(self, hwnd: int, on_lock: Callable[[], None]):
        if os.name != "nt":
            raise OSError("Windows session notifications are available only on Windows")
        self.hwnd = int(hwnd)
        self.on_lock = on_lock
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        self._old_wndproc: int | None = None
        self._registered = False
        self._callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )
        self._wndproc = self._callback_type(self._dispatch)

    def start(self) -> None:
        if self._registered:
            return
        hwnd = ctypes.c_void_p(self.hwnd)
        self._wtsapi32.WTSRegisterSessionNotification.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self._wtsapi32.WTSRegisterSessionNotification.restype = ctypes.c_int
        if not self._wtsapi32.WTSRegisterSessionNotification(hwnd, self.NOTIFY_FOR_THIS_SESSION):
            raise ctypes.WinError(ctypes.get_last_error())
        self._registered = True

        setter = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
        setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        setter.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        old_proc = setter(hwnd, self.GWLP_WNDPROC, ctypes.cast(self._wndproc, ctypes.c_void_p))
        error = ctypes.get_last_error()
        if not old_proc and error:
            self.stop()
            raise ctypes.WinError(error)
        self._old_wndproc = int(old_proc or 0)

    def stop(self) -> None:
        hwnd = ctypes.c_void_p(self.hwnd)
        if self._old_wndproc is not None:
            setter = getattr(self._user32, "SetWindowLongPtrW", self._user32.SetWindowLongW)
            setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            setter.restype = ctypes.c_void_p
            setter(hwnd, self.GWLP_WNDPROC, ctypes.c_void_p(self._old_wndproc))
            self._old_wndproc = None
        if self._registered:
            self._wtsapi32.WTSUnRegisterSessionNotification.argtypes = [ctypes.c_void_p]
            self._wtsapi32.WTSUnRegisterSessionNotification.restype = ctypes.c_int
            self._wtsapi32.WTSUnRegisterSessionNotification(hwnd)
            self._registered = False

    def _dispatch(self, hwnd, message, wparam, lparam):
        if message == self.WM_WTSSESSION_CHANGE and wparam == self.WTS_SESSION_LOCK:
            try:
                self.on_lock()
            except Exception:
                pass
        if self._old_wndproc:
            self._user32.CallWindowProcW.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                ctypes.c_size_t, ctypes.c_ssize_t,
            ]
            self._user32.CallWindowProcW.restype = ctypes.c_ssize_t
            return self._user32.CallWindowProcW(
                ctypes.c_void_p(self._old_wndproc), hwnd, message, wparam, lparam,
            )
        self._user32.DefWindowProcW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
        ]
        self._user32.DefWindowProcW.restype = ctypes.c_ssize_t
        return self._user32.DefWindowProcW(hwnd, message, wparam, lparam)
