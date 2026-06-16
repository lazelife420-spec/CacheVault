"""Paste delivery helpers — focus restore, Ctrl+V, clipboard snapshot."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32process  # type: ignore

    _HAS_WIN32 = True
except Exception:  # noqa: BLE001
    _HAS_WIN32 = False


@dataclass
class PasteResult:
    ok: bool
    reason: str = ""
    target_title: str = ""


def _read_clipboard_text() -> str | None:
    if not _HAS_WIN32:
        return None
    try:
        import win32clipboard  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001
        return None
    return None


def snapshot_clipboard_text() -> str | None:
    return _read_clipboard_text()


def restore_clipboard_text(text: str | None) -> bool:
    if not _HAS_WIN32 or text is None:
        return False
    try:
        import win32clipboard  # type: ignore

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:  # noqa: BLE001
        return False


def window_title(hwnd) -> str:
    if not _HAS_WIN32 or not hwnd:
        return ""
    try:
        title = win32gui.GetWindowText(hwnd) or ""
        return title[:120]
    except Exception:  # noqa: BLE001
        return ""


def hwnd_belongs_to_widget(hwnd, widget) -> bool:
    """True when ``hwnd`` is the tk widget or a descendant window."""
    if not _HAS_WIN32 or not hwnd or widget is None:
        return False
    try:
        root_id = widget.winfo_id()
        current = int(hwnd)
        while current:
            if current == root_id:
                return True
            current = win32gui.GetParent(current)
    except Exception:  # noqa: BLE001
        return False
    return False


def _force_foreground(hwnd) -> bool:
    if not _HAS_WIN32 or not hwnd:
        return False
    try:
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        fg = win32gui.GetForegroundWindow()
        fg_thread = win32process.GetWindowThreadProcessId(fg)[0]
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
        cur_thread = win32api.GetCurrentThreadId()
        attached_fg = attached_target = False
        try:
            if fg_thread and fg_thread != cur_thread:
                attached_fg = bool(win32process.AttachThreadInput(cur_thread, fg_thread, True))
            if target_thread and target_thread != cur_thread:
                attached_target = bool(
                    win32process.AttachThreadInput(cur_thread, target_thread, True),
                )
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            return win32gui.GetForegroundWindow() == hwnd
        finally:
            if attached_target:
                win32process.AttachThreadInput(cur_thread, target_thread, False)
            if attached_fg:
                win32process.AttachThreadInput(cur_thread, fg_thread, False)
    except Exception:  # noqa: BLE001
        try:
            win32gui.SetForegroundWindow(hwnd)
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:  # noqa: BLE001
            return False


def deliver_ctrl_v(hwnd, *, delay_s: float = 0.08) -> PasteResult:
    """Restore focus to ``hwnd`` and send Ctrl+V."""
    title = window_title(hwnd)
    if not _HAS_WIN32:
        return PasteResult(False, "paste_unavailable", title)
    if not hwnd:
        return PasteResult(False, "no_target_window", title)
    if not _force_foreground(hwnd):
        return PasteResult(False, "focus_restore_failed", title)
    time.sleep(delay_s)
    vk_ctrl, vk_v, keyup = 0x11, 0x56, 0x0002
    try:
        win32api.keybd_event(vk_ctrl, 0, 0, 0)
        win32api.keybd_event(vk_v, 0, 0, 0)
        win32api.keybd_event(vk_v, 0, keyup, 0)
        win32api.keybd_event(vk_ctrl, 0, keyup, 0)
    except Exception:  # noqa: BLE001
        return PasteResult(False, "send_keys_failed", title)
    return PasteResult(True, "ok", title)


def foreground_window():
    if not _HAS_WIN32:
        return None
    try:
        return win32gui.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        return None
