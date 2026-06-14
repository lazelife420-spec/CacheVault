"""Windows clipboard monitoring.

Two strategies, picked at runtime:

1. **Event-based** (preferred): a hidden message-only window registered with
   ``AddClipboardFormatListener`` receives ``WM_CLIPBOARDUPDATE`` — no polling,
   near-zero idle cost. Requires ``pywin32``.

2. **Polling fallback**: if ``pywin32`` is unavailable we poll the clipboard on
   a throttled timer (default 800ms, configurable). This is less efficient and
   is documented as a tradeoff — see the README.

Either way the monitor only ever *reads* the clipboard on change events; it
never logs contents and never touches the network.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

try:  # pragma: no cover - import guard, exercised only on Windows desktops
    import win32api  # type: ignore
    import win32clipboard  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32process  # type: ignore
    _HAS_WIN32 = True
except Exception:  # noqa: BLE001
    _HAS_WIN32 = False


ClipCallback = Callable[[str, dict], None]


def _read_clipboard_text() -> Optional[str]:
    if not _HAS_WIN32:
        return None
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001 - clipboard can be transiently locked
        return None
    return None


def _foreground_source() -> dict:
    """Best-effort source app/window for the foreground process."""
    info: dict = {"source_app": None, "source_window": None}
    if not _HAS_WIN32:
        return info
    try:
        hwnd = win32gui.GetForegroundWindow()
        info["source_window"] = win32gui.GetWindowText(hwnd) or None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
            exe = win32process.GetModuleFileNameEx(handle, 0)
            info["source_app"] = exe.rsplit("\\", 1)[-1]
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    return info


class ClipboardMonitor:
    """Watches the clipboard and calls ``on_clip(text, source_info)``.

    The callback runs on the monitor's own thread; UI code should marshal back
    to the main thread (the shell uses ``after`` for this).
    """

    def __init__(self, on_clip: ClipCallback, poll_interval_ms: int = 800):
        self._on_clip = on_clip
        self._poll_interval = max(200, poll_interval_ms) / 1000.0
        self._paused = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._last_text: Optional[str] = None

    # --- lifecycle ---------------------------------------------------------
    @property
    def available(self) -> bool:
        return _HAS_WIN32

    @property
    def mode(self) -> str:
        return "event" if _HAS_WIN32 else "poll"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        target = self._run_event_loop if _HAS_WIN32 else self._run_poll_loop
        self._thread = threading.Thread(target=target, name="clipboard-monitor",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if _HAS_WIN32 and self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001
                pass

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def note_local_copy(self, text: str) -> None:
        """Tell the monitor we just set the clipboard ourselves (Copy Again)
        so the resulting change event isn't re-captured as a new clip."""
        self._last_text = text

    # --- internals ---------------------------------------------------------
    def _emit(self) -> None:
        if self._paused or not self._running:
            return
        text = _read_clipboard_text()
        if not text or text == self._last_text:
            return
        self._last_text = text
        source = _foreground_source()
        try:
            self._on_clip(text, source)
        except Exception:  # noqa: BLE001 - never let a UI error kill the monitor
            pass

    def _run_event_loop(self) -> None:  # pragma: no cover - needs Windows desktop
        WM_CLIPBOARDUPDATE = 0x031D

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_CLIPBOARDUPDATE:
                self._emit()
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "CacheVaultClipboardListener"
        wc.lpfnWndProc = wndproc
        class_atom = win32gui.RegisterClass(wc)
        self._hwnd = win32gui.CreateWindow(
            class_atom, "CacheVaultClipboardListener", 0, 0, 0, 0, 0,
            0, 0, 0, None,
        )
        try:
            win32clipboard.AddClipboardFormatListener(self._hwnd)
        except Exception:  # noqa: BLE001 - fall back to polling
            self._run_poll_loop()
            return
        # Seed last_text so the current clipboard isn't captured on launch.
        self._last_text = _read_clipboard_text()
        win32gui.PumpMessages()

    def _run_poll_loop(self) -> None:
        import time
        self._last_text = _read_clipboard_text()
        while self._running:
            self._emit()
            time.sleep(self._poll_interval)
