"""Live end-to-end smoke test driving the REAL Windows clipboard.

Saves the current clipboard, pushes a handful of samples through the actual
win32 ``AddClipboardFormatListener`` path, prints how each was classified, then
restores the original clipboard. Run manually:  python tools/live_clipboard_smoke.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32clipboard  # type: ignore
import win32con  # type: ignore

from cache_vault.core.clipboard import ClipboardMonitor
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


def get_clip() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None
    return None


def set_clip(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


SAMPLES = [
    ("https://github.com/anthropics/claude-code", "link"),
    ("git clone https://github.com/foo/bar.git", "command"),
    (r"C:\Users\KickA\Desktop\notes.txt", "path"),
    ("def add(a, b):\n    return a + b", "code"),
    ("zerivonforge@gmail.com", "email"),
    ("sk-abc123DEF456ghi789JKL0mno", "SENSITIVE"),
]


def main() -> int:
    original = get_clip()
    print(f"saved original clipboard ({len(original or '')} chars)\n")

    # The monitor runs on its own thread; SQLite lives on the main thread, so
    # we only *collect* raw (text, source) events on the monitor thread and do
    # the actual capture here. This mirrors the shell's after(0, ...) hop.
    captured_events: list[tuple[str, dict]] = []
    monitor = ClipboardMonitor(
        lambda text, src: captured_events.append((text, src)),
    )
    print(f"monitor mode: {monitor.mode}")
    monitor.start()
    time.sleep(0.5)  # let the listener window register

    for text, expected in SAMPLES:
        set_clip(text)
        time.sleep(0.9)  # allow WM_CLIPBOARDUPDATE to fire (avoid coalescing)

    time.sleep(0.4)
    monitor.stop()
    print(f"live listener fired for {len(captured_events)} clipboard change(s)")

    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    for text, src in captured_events:
        vault.capture(text, source_app=src.get("source_app"),
                     source_window=src.get("source_window"))

    clips = vault.list_clips()
    print(f"\ncaptured {len(clips)} clips via the live listener:\n")
    ok = True
    by_content = {c.content.strip(): c for c in clips}
    for text, expected in SAMPLES:
        c = by_content.get(text.strip())
        if c is None:
            print(f"  [MISS] not captured: {text[:40]!r}")
            ok = False
            continue
        got = "SENSITIVE" if c.is_sensitive else c.classification
        mark = "ok " if got == expected else "DIFF"
        shown = c.preview if c.is_sensitive else (c.content[:38].replace("\n", " "))
        print(f"  [{mark}] expect={expected:<10} got={got:<10} {shown!r}")
        if got != expected:
            ok = False

    # Restore.
    if original is not None:
        set_clip(original)
        print("\nrestored original clipboard")
    vault.close()
    print("\nRESULT:", "PASS" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
