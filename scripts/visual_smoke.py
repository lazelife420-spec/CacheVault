"""Automated visual smoke captures for manual gate review."""
from __future__ import annotations

import ctypes
import time
from pathlib import Path

import win32con
import win32gui

OUT = Path(__file__).resolve().parent.parent / "visual_smoke"
TITLE = "Cache Vault"


def find_hwnd() -> int:
    found: list[int] = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if TITLE.lower() in t.lower():
                found.append(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else 0


def click(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.15)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # down
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # up
    time.sleep(0.4)


def capture(name: str) -> None:
    import subprocess
    out = OUT / f"{name}.png"
    subprocess.run(
        ["python", str(Path(__file__).parent / "capture_window.py"), TITLE, str(out)],
        check=True,
        cwd=Path(__file__).resolve().parent.parent,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for _ in range(40):
        hwnd = find_hwnd()
        if hwnd:
            win32gui.SetForegroundWindow(hwnd)
            break
        time.sleep(0.25)
    else:
        raise SystemExit("Cache Vault window not found")

    time.sleep(1.5)
    capture("01_home")

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    # Sidebar "All Clips" — below Home, grouped nav
    click(left + 100, top + int(h * 0.22))
    time.sleep(0.8)
    capture("02_all_clips_cards")

    # Grid segmented button (right toolbar row)
    click(left + int(w * 0.72), top + int(h * 0.14))
    time.sleep(0.6)
    capture("03_all_clips_grid")

    # Stamped Receipts top bar
    click(left + int(w * 0.62), top + 28)
    time.sleep(1.0)
    capture("04_stamped_receipts")
    # Close receipts (Escape)
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.5)

    # Settings
    win32gui.SetForegroundWindow(hwnd)
    click(left + int(w * 0.88), top + 28)
    time.sleep(1.0)
    capture("05_settings")
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.5)

    # Pair Android via Settings again + scroll + pair — open settings, scroll down, pair
    win32gui.SetForegroundWindow(hwnd)
    click(left + int(w * 0.88), top + 28)
    time.sleep(0.8)
    # scroll mobile section into view
    for _ in range(6):
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120, 0)
        time.sleep(0.1)
    time.sleep(0.3)
    capture("06_settings_mobile_scroll")
    # Pair Android button approx center-bottom of settings
    sw_left, sw_top, sw_right, sw_bottom = win32gui.GetWindowRect(find_hwnd())
    # Settings is modal - find topmost child
    click(sw_left + int((sw_right - sw_left) * 0.5), sw_top + int((sw_bottom - sw_top) * 0.72))
    time.sleep(1.2)
    capture("07_pair_android_or_hint")
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)

    print(f"Captures saved under {OUT}")


if __name__ == "__main__":
    main()
