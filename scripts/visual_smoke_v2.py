"""Visual smoke v2 — improved navigation coordinates."""
from __future__ import annotations

import ctypes
import subprocess
import time
from pathlib import Path

import win32gui

OUT = Path(__file__).resolve().parent.parent / "visual_smoke"
ROOT = Path(__file__).resolve().parent.parent
TITLE = "Cache Vault"


def hwnd() -> int:
    found: list[int] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if TITLE.lower() in t.lower() and "settings" not in t.lower() and "stamped" not in t.lower():
                found.append(h)
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else 0


def find_title(sub: str) -> int:
    found: list[int] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if sub.lower() in t.lower():
                found.append(h)
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else 0


def click(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.12)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.5)


def cap(name: str, title: str = TITLE) -> None:
    subprocess.run(
        ["python", str(ROOT / "scripts" / "capture_window.py"), title, str(OUT / f"{name}.png")],
        check=True, cwd=ROOT,
    )


def esc() -> None:
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.4)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    h = hwnd()
    if not h:
        raise SystemExit("main window not found")
    win32gui.SetForegroundWindow(h)
    time.sleep(0.8)
    l, t, r, b = win32gui.GetWindowRect(h)
    w, ht = r - l, b - t

    cap("01_home")
    # All Clips in sidebar
    click(l + 95, t + 218)
    cap("02_all_clips_cards")
    # Grid toggle (right toolbar)
    click(l + int(w * 0.835), t + int(ht * 0.155))
    cap("03_all_clips_grid")
    # First clip card in list
    click(l + int(w * 0.42), t + int(ht * 0.38))
    cap("04_preview_clip")
    # Stamped Receipts
    click(l + int(w * 0.56), t + 32)
    time.sleep(0.9)
    cap("05_stamped_receipts", "Stamped Receipts")
    esc()
  # Settings
    win32gui.SetForegroundWindow(hwnd())
    click(l + int(w * 0.78), t + 32)
    time.sleep(0.9)
    cap("06_settings", "Settings")
    # Scroll to Mobile Access
    sh = find_title("Settings")
    if sh:
        sl, st, sr, sb = win32gui.GetWindowRect(sh)
        for _ in range(8):
            ctypes.windll.user32.SetCursorPos(sl + (sr - sl) // 2, st + (sb - st) // 2)
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120, 0)
            time.sleep(0.08)
    time.sleep(0.4)
    cap("07_settings_mobile", "Settings")
    # Pair Android
    if sh:
        sl, st, sr, sb = win32gui.GetWindowRect(sh)
        click(sl + (sr - sl) // 2, st + int((sb - st) * 0.68))
    time.sleep(1.0)
    cap("08_pair_android", "Pair")
    esc()
    esc()
    print("done", OUT)


if __name__ == "__main__":
    main()
