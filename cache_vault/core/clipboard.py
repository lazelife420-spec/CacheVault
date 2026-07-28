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

import logging
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


ClipCallback = Callable[[dict], None]
logger = logging.getLogger(__name__)

# A clipboard change normally stabilizes by the second read.  Keep retries
# bounded so a continuously changing clipboard cannot stall the monitor.
STABLE_SNAPSHOT_MAX_ATTEMPTS = 3


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


def _read_clipboard_image() -> tuple[bytes, int, int] | None:
    """Read clipboard image as PNG bytes (CF_DIB). Returns None if no image."""
    if not _HAS_WIN32:
        return None
    try:
        from . import image_assets
        win32clipboard.OpenClipboard()
        try:
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return None
            dib = win32clipboard.GetClipboardData(win32con.CF_DIB)
        finally:
            win32clipboard.CloseClipboard()
        return image_assets.dib_to_png(dib)
    except Exception:  # noqa: BLE001
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


def read_clipboard_payload() -> dict | None:
    """Read current clipboard as a capture payload (text or image)."""
    source = _foreground_source()
    image = _read_clipboard_image()
    if image is not None:
        png, width, height = image
        return {"image_png": png, "width": width, "height": height, **source}
    text = _read_clipboard_text()
    if text and text.strip():
        return {"text": text, **source}
    return None


class ClipboardMonitor:
    """Watches the clipboard and calls ``on_clip(payload)``.

    Payload keys: ``text``, ``image_png``, ``width``, ``height``,
    ``source_app``, ``source_window``.

    The callback runs on the monitor's own thread; UI code should marshal back
    to the main thread (the shell uses ``after`` for this).
    """

    def __init__(
        self,
        on_clip: ClipCallback,
        poll_interval_ms: int = 800,
        *,
        suppressor=None,
        get_sequence=None,
    ):
        self._on_clip = on_clip
        self._poll_interval = max(200, poll_interval_ms) / 1000.0
        self._paused = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._last_text: Optional[str] = None
        self._last_image_hash: Optional[str] = None
        # Slice A custody: shared suppressor + clipboard sequence tracking.
        self._suppressor = suppressor
        if get_sequence is None:
            from .clipboard_custody import default_clipboard_sequence
            get_sequence = default_clipboard_sequence
        self._get_sequence = get_sequence
        self._last_seq: Optional[int] = None
        self._set_suppressor_cadence()

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

    def note_local_copy_image(self, png_bytes: bytes) -> None:
        """Suppress re-capture after Copy Again puts an image on the clipboard."""
        from . import image_assets
        self._last_image_hash = image_assets.canonical_image_fingerprint(png_bytes)

    # --- internals ---------------------------------------------------------
    def _sequence(self) -> Optional[int]:
        try:
            return self._get_sequence()
        except Exception:  # noqa: BLE001
            return None

    def _set_suppressor_cadence(self) -> None:
        """Tell the shared suppressor our cadence so it can size fallback TTL."""
        if self._suppressor is None:
            return
        try:
            self._suppressor.set_monitor_cadence(
                mode=self.mode,
                cadence_s=self._poll_interval,
            )
        except Exception:  # noqa: BLE001
            pass

    def _suppress_own(self, content_type: str, fingerprint: str, seq: Optional[int]) -> bool:
        """One-shot custody check: consume the matching record, if any."""
        suppressor = self._suppressor
        if suppressor is None:
            return False
        try:
            return suppressor.should_suppress(
                content_type=content_type,
                fingerprint=fingerprint,
                sequence=seq,
            )
        except Exception:  # noqa: BLE001 - custody failure must not drop clips
            return False

    def _emit(self) -> None:
        if self._paused or not self._running:
            return
        from . import capture_debug, image_assets, models

        snapshot = self._read_stable_snapshot()
        if snapshot is None:
            return
        seq, image, text = snapshot
        if seq is not None:
            if seq == self._last_seq:
                return
            self._last_seq = seq
        source = _foreground_source()
        if image is not None:
            png, width, height = image
            ih = image_assets.canonical_image_fingerprint(png)
            if self._suppress_own(models.CONTENT_IMAGE, ih, seq):
                self._last_image_hash = ih
                return
            # Content dedupe only applies when sequence numbers are missing;
            # with sequences, a later genuine identical copy must recapture.
            if seq is not None or ih != self._last_image_hash:
                self._last_image_hash = ih
                payload = {
                    "image_png": png,
                    "width": width,
                    "height": height,
                    "clipboard_sequence": seq,
                    **source,
                }
                capture_debug.log("clipboard_event", capture_debug.payload_summary(payload))
                try:
                    self._on_clip(payload)
                except Exception:  # noqa: BLE001
                    pass
            return
        if not text:
            return
        if self._suppress_own(models.CONTENT_TEXT, text, seq):
            self._last_text = text
            return
        if seq is None and text == self._last_text:
            return
        self._last_text = text
        payload = {"text": text, "clipboard_sequence": seq, **source}
        capture_debug.log("clipboard_event", capture_debug.payload_summary(payload))
        try:
            self._on_clip(payload)
        except Exception:  # noqa: BLE001 - never let a UI error kill the monitor
            pass

    def _read_stable_snapshot(
        self,
    ) -> tuple[int | None, tuple[bytes, int, int] | None, str | None] | None:
        """Read content bracketed by sequence values.

        When both sequence reads are available, content is accepted only if
        they identify the same clipboard state.  A continuously changing
        clipboard is deferred without updating ``_last_seq``, so the next
        listener notification or polling pass can retry.
        """
        for attempt in range(1, STABLE_SNAPSHOT_MAX_ATTEMPTS + 1):
            sequence_before = self._sequence()
            image = _read_clipboard_image()
            text = None if image is not None else _read_clipboard_text()
            sequence_after = self._sequence()

            if sequence_before is not None and sequence_after is not None:
                stable = (
                    int(sequence_before) & 0xFFFFFFFF
                ) == (
                    int(sequence_after) & 0xFFFFFFFF
                )
                if not stable:
                    logger.info(
                        "clipboard snapshot changed during read: "
                        "attempt=%d/%d sequence_before=%s sequence_after=%s",
                        attempt,
                        STABLE_SNAPSHOT_MAX_ATTEMPTS,
                        sequence_before,
                        sequence_after,
                    )
                    continue
                sequence = sequence_after
            else:
                # A missing sequence on either side cannot safely label the
                # payload.  Process it through bounded fingerprint fallback.
                sequence = None

            return sequence, image, text

        logger.warning(
            "clipboard snapshot remained unstable after %d attempts; "
            "deferring capture to the next monitor pass",
            STABLE_SNAPSHOT_MAX_ATTEMPTS,
        )
        return None

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
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception:
            # Already registered or other error, try to continue with the name
            class_atom = wc.lpszClassName
        self._hwnd = win32gui.CreateWindow(
            class_atom, "CacheVaultClipboardListener", 0, 0, 0, 0, 0,
            0, 0, 0, None,
        )
        try:
            win32clipboard.AddClipboardFormatListener(self._hwnd)
        except Exception:  # noqa: BLE001 - fall back to polling
            self._run_poll_loop()
            return
        self._last_text = _read_clipboard_text()
        self._last_seq = self._sequence()
        win32gui.PumpMessages()

    def _run_poll_loop(self) -> None:
        import time
        # The event-listener path can fall back here at runtime when
        # AddClipboardFormatListener fails.  Re-size the custody window for
        # polling even when pywin32 was available during construction.
        if self._suppressor is not None:
            try:
                self._suppressor.set_monitor_cadence(
                    mode="poll",
                    cadence_s=self._poll_interval,
                )
            except Exception:  # noqa: BLE001
                pass
        self._last_text = _read_clipboard_text()
        self._last_seq = self._sequence()
        while self._running:
            self._emit()
            time.sleep(self._poll_interval)
