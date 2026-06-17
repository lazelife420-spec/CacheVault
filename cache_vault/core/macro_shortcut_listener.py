"""Global text-shortcut listener for Vault Macros (Windows low-level hook)."""

from __future__ import annotations

import ctypes
import string
import threading
from ctypes import wintypes
from collections.abc import Callable
from typing import Optional

from .paste_delivery import foreground_window, is_password_field
from .vault_macros import Macro, TRIGGER_TEXT_SHORTCUT

try:
    import win32gui  # type: ignore

    _HAS_WIN32 = True
except Exception:  # noqa: BLE001
    _HAS_WIN32 = False

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
VK_BACK = 0x08
VK_RETURN = 0x0D
VK_TAB = 0x09

_user32 = ctypes.windll.user32 if _HAS_WIN32 else None
_kernel32 = ctypes.windll.kernel32 if _HAS_WIN32 else None


class TextShortcutListener:
    """Track typed characters and fire when a configured shortcut suffix matches."""

    def __init__(
        self,
        on_match: Callable[[Macro, str, int, object], None],
        *,
        should_skip: Callable[[object], bool] | None = None,
        max_buffer: int = 48,
    ):
        self._on_match = on_match
        self._should_skip = should_skip or (lambda _h: False)
        self._max_buffer = max_buffer
        self._enabled = False
        self._macros: list[Macro] = []
        self._buffer = ""
        self._thread: Optional[threading.Thread] = None
        self._hook_id = None

    def update(self, macros: list[Macro], *, enabled: bool) -> None:
        self._macros = [
            m for m in macros
            if m.enabled and m.trigger_type == TRIGGER_TEXT_SHORTCUT and (m.trigger_value or "").strip()
        ]
        self._enabled = enabled and bool(self._macros)

    @property
    def active(self) -> bool:
        return self._enabled and _HAS_WIN32

    def start(self) -> None:
        if not _HAS_WIN32 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="macro-shortcut-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._hook_id and _user32:
            try:
                _user32.UnhookWindowsHookEx(self._hook_id)
            except Exception:  # noqa: BLE001
                pass
        self._hook_id = None

    def _append_char(self, ch: str) -> None:
        self._buffer = (self._buffer + ch)[-self._max_buffer :]

    def _vk_to_char(self, vk: int) -> str | None:
        if not _user32:
            return None
        keyboard_state = (ctypes.c_byte * 256)()
        if not _user32.GetKeyboardState(keyboard_state):
            return None
        buf = (wintypes.WCHAR * 2)()
        scan = _user32.MapVirtualKeyW(vk, 0)
        rc = _user32.ToUnicodeEx(vk, scan, keyboard_state, buf, 2, 0, 0)
        if rc == 1 and buf[0]:
            return buf[0]
        return None

    def _handle_key(self, vk: int) -> None:
        if not self._enabled:
            return
        hwnd = foreground_window()
        if hwnd and self._should_skip(hwnd):
            return
        if hwnd and is_password_field(hwnd):
            return

        if vk == VK_BACK:
            self._buffer = self._buffer[:-1]
            return

        ch = self._vk_to_char(vk)
        if not ch or ch not in string.printable:
            return
        self._append_char(ch.lower())

        from .macro_execute import match_shortcut_suffix

        hit = match_shortcut_suffix(self._buffer, self._macros)
        if hit:
            shortcut, macro = hit
            self._buffer = self._buffer[: -len(shortcut)]
            try:
                self._on_match(macro, shortcut, len(shortcut), hwnd)
            except Exception:  # noqa: BLE001
                pass

    def _run(self) -> None:  # pragma: no cover - Windows hook thread
        if not _user32 or not _kernel32:
            return

        CMPFUNC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p)

        @CMPFUNC
        def hook_proc(n_code, w_param, l_param):
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kb = ctypes.cast(l_param, ctypes.POINTER(ctypes.c_ulong * 4)).contents
                vk = kb[0]
                self._handle_key(vk)
            return _user32.CallNextHookEx(self._hook_id, n_code, w_param, l_param)

        self._hook_id = _user32.SetWindowsHookExW(WH_KEYBOARD_LL, hook_proc, _kernel32.GetModuleHandleW(None), 0)
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))
