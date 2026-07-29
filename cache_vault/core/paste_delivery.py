"""Paste delivery helpers — focus restore, Ctrl+V, clipboard snapshot."""

from __future__ import annotations

import time
from dataclasses import dataclass

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


# OpenClipboard transiently fails whenever another window currently holds the
# clipboard open — most notably the paste target itself, which briefly opens
# the clipboard to read the delivered content right after a synthetic Ctrl+V.
# That window is normally a handful of milliseconds. Retrying a short, bounded
# number of times clears it without masking a genuinely unavailable clipboard.
#
# Retry budget: up to _CLIPBOARD_OPEN_RETRY_ATTEMPTS attempts, with a sleep
# only *between* attempts (never after the last one). For the defaults below
# that is 4 sleeps of 15ms = 60ms maximum scheduled delay, not 5.
_CLIPBOARD_OPEN_RETRY_ATTEMPTS = 5
_CLIPBOARD_OPEN_RETRY_DELAY_S = 0.015  # 4 gaps x 15ms = 60ms max scheduled delay


def _win32_error_code(exc: Exception) -> int | None:
    """Best-effort Win32 error code extraction (pywintypes.error, OSError)."""
    code = getattr(exc, "winerror", None)
    if code is None:
        args = getattr(exc, "args", None)
        if args:
            first = args[0]
            if isinstance(first, int):
                code = first
    return code


def _log_clipboard_stage(
    operation: str, stage: str, result: str, *, attempt: int | None = None,
    total_attempts: int | None = None, exc: Exception | None = None,
) -> None:
    from . import capture_debug

    parts = [f"operation={operation}", f"stage={stage}", f"result={result}"]
    if attempt is not None:
        parts.append(f"attempt={attempt}")
    if total_attempts is not None:
        parts.append(f"total_attempts={total_attempts}")
    if exc is not None:
        parts.append(f"error_type={type(exc).__name__}")
        code = _win32_error_code(exc)
        if code is not None:
            parts.append(f"error_code={code}")
    capture_debug.log("clipboard_write_stage", " ".join(parts))


def _open_clipboard_with_retry(
    win32clipboard,
    *,
    operation: str = "unspecified",
    attempts: int = _CLIPBOARD_OPEN_RETRY_ATTEMPTS,
    delay_s: float = _CLIPBOARD_OPEN_RETRY_DELAY_S,
) -> None:
    """Retry ``OpenClipboard`` a bounded number of times.

    Sleeps only *between* attempts — attempts ``1..attempts-1`` may be
    followed by a ``delay_s`` sleep; the final attempt never sleeps
    afterward, whether it succeeds or exhausts the budget.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            win32clipboard.OpenClipboard()
            _log_clipboard_stage(
                operation, "OpenClipboard", "ok", attempt=attempt, total_attempts=attempts,
            )
            return
        except Exception as exc:  # noqa: BLE001 - retried below; re-raised if exhausted
            last_exc = exc
            _log_clipboard_stage(
                operation, "OpenClipboard", "fail", attempt=attempt,
                total_attempts=attempts, exc=exc,
            )
            if attempt < attempts:
                time.sleep(delay_s)
    assert last_exc is not None
    raise last_exc


def _read_clipboard_text() -> str | None:
    if not _HAS_WIN32:
        return None
    try:
        import win32clipboard  # type: ignore

        _open_clipboard_with_retry(win32clipboard, operation="read_clipboard_text")
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


def _write_clipboard_text(text: str, *, operation: str) -> bool:
    """Shared body for ``set_clipboard_text``/``restore_clipboard_text``.

    ``OpenClipboard`` gets the bounded retry above (the contention-prone
    call). Once it succeeds, a failure in ``EmptyClipboard`` or
    ``SetClipboardData`` is NOT retried — that represents a different,
    non-contention failure class, and retrying after a partial mutation
    without a proven-safe recovery path would be unsound. ``CloseClipboard``
    always runs in ``finally`` once ``OpenClipboard`` has succeeded, and
    never runs otherwise.
    """
    import win32clipboard  # type: ignore

    try:
        _open_clipboard_with_retry(win32clipboard, operation=operation)
    except Exception as exc:  # noqa: BLE001 - OpenClipboard exhausted its retries
        _log_clipboard_stage(operation, "OpenClipboard", "fail_final", exc=exc)
        return False

    try:
        try:
            win32clipboard.EmptyClipboard()
        except Exception as exc:  # noqa: BLE001
            _log_clipboard_stage(operation, "EmptyClipboard", "fail", exc=exc)
            return False
        try:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        except Exception as exc:  # noqa: BLE001
            _log_clipboard_stage(operation, "SetClipboardData", "fail", exc=exc)
            return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception as exc:  # noqa: BLE001
            _log_clipboard_stage(operation, "CloseClipboard", "fail", exc=exc)

    _log_clipboard_stage(operation, "complete", "ok")
    return True


def restore_clipboard_text(text: str | None) -> bool:
    if not _HAS_WIN32 or text is None:
        return False
    try:
        return _write_clipboard_text(text, operation="restore_clipboard_text")
    except Exception as exc:  # noqa: BLE001 - defensive: never let a write raise
        _log_clipboard_stage("restore_clipboard_text", "unexpected", "fail", exc=exc)
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


def set_clipboard_text(text: str) -> bool:
    if not _HAS_WIN32:
        return False
    try:
        return _write_clipboard_text(text, operation="set_clipboard_text")
    except Exception as exc:  # noqa: BLE001 - defensive: never let a write raise
        _log_clipboard_stage("set_clipboard_text", "unexpected", "fail", exc=exc)
        return False


def send_backspaces(hwnd, count: int, *, delay_s: float = 0.02) -> bool:
    """Send Backspace key events to remove typed shortcut text."""
    if not _HAS_WIN32 or count <= 0:
        return False
    if hwnd:
        _force_foreground(hwnd)
        time.sleep(delay_s)
    vk_back = 0x08
    keyup = 0x0002
    try:
        for _ in range(count):
            win32api.keybd_event(vk_back, 0, 0, 0)
            win32api.keybd_event(vk_back, 0, keyup, 0)
            time.sleep(delay_s)
        return True
    except Exception:  # noqa: BLE001
        return False


def _vk_for_char(ch: str) -> tuple[int, int] | None:
    if not _HAS_WIN32 or not ch:
        return None
    if ch == "\n":
        return 0x0D, 0
    if ch == "\t":
        return 0x09, 0
    if ch == "\r":
        return None
    result = win32api.VkKeyScan(ch)
    if result == -1:
        return None
    vk = result & 0xFF
    shift = (result >> 8) & 0xFF
    return vk, shift


def deliver_text_keystrokes(
    hwnd,
    text: str,
    *,
    delay_s: float = 0.01,
) -> PasteResult:
    """Type ``text`` via simulated keystrokes (ASCII-focused, Windows only)."""
    title = window_title(hwnd)
    if not _HAS_WIN32:
        return PasteResult(False, "keystroke_unavailable", title)
    if not hwnd:
        return PasteResult(False, "no_target_window", title)
    if not _force_foreground(hwnd):
        return PasteResult(False, "focus_restore_failed", title)
    time.sleep(delay_s)
    keyup = 0x0002
    vk_shift = 0x10
    try:
        for ch in text:
            if ch == "\r":
                continue
            mapped = _vk_for_char(ch)
            if mapped is None:
                return PasteResult(False, "unsupported_character", title)
            vk, shift = mapped
            if shift:
                win32api.keybd_event(vk_shift, 0, 0, 0)
            win32api.keybd_event(vk, 0, 0, 0)
            win32api.keybd_event(vk, 0, keyup, 0)
            if shift:
                win32api.keybd_event(vk_shift, 0, keyup, 0)
            time.sleep(delay_s)
        return PasteResult(True, "ok", title)
    except Exception:  # noqa: BLE001
        return PasteResult(False, "send_keys_failed", title)


def is_password_field(hwnd) -> bool:
    """Best-effort: focused control uses ES_PASSWORD style."""
    if not _HAS_WIN32 or not hwnd:
        return False
    try:
        ES_PASSWORD = 0x0020
        GWL_STYLE = -16
        style = win32gui.GetWindowLong(hwnd, GWL_STYLE)
        return bool(style & ES_PASSWORD)
    except Exception:  # noqa: BLE001
        return False


def foreground_window():
    if not _HAS_WIN32:
        return None
    try:
        return win32gui.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        return None
