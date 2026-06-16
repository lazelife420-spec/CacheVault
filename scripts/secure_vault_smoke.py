"""Visual smoke for secure vault UI organization pass."""
from __future__ import annotations

import ctypes
import subprocess
import time
from pathlib import Path

import win32gui

OUT = Path(__file__).resolve().parent.parent / "visual_smoke"
ROOT = Path(__file__).resolve().parent.parent
TITLE = "Cache Vault"


def hwnd_main() -> int:
    found: list[int] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if TITLE.lower() in t.lower() and "settings" not in t.lower() and "stamped" not in t.lower() and "pair" not in t.lower():
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
    time.sleep(0.15)
    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.6)


def cap(name: str, title: str = TITLE) -> None:
    subprocess.run(
        ["python", str(ROOT / "scripts" / "capture_window.py"), title, str(OUT / f"{name}.png")],
        check=True, cwd=ROOT,
    )


def esc() -> None:
    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.5)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for _ in range(40):
        h = hwnd_main()
        if h:
            break
        time.sleep(0.5)
    if not h:
        raise SystemExit("main window not found — launch CacheVault.exe first")

    try:
        win32gui.SetForegroundWindow(h)
    except Exception:
        time.sleep(1.0)
        win32gui.SetForegroundWindow(h)
    time.sleep(1.2)
    l, t, r, b = win32gui.GetWindowRect(h)
    w, ht = r - l, b - t

    cap("sv01_home_vault")
    # Top bar — buttons anchored on the right
    click(r - 280, t + 26)
    time.sleep(1.0)
    cap("sv02_stamped_receipts", "Stamped Receipts")
    esc()

    win32gui.SetForegroundWindow(hwnd_main())
    time.sleep(0.8)
    l, t, r, b = win32gui.GetWindowRect(hwnd_main())
    w, ht = r - l, b - t

    cap("sv02b_sidebar")

    # Settings from top bar (far right)
    click(r - 55, t + 26)
    time.sleep(1.0)
    cap("sv03_settings", "Settings")
    # Pair Android — pinned card
    sh = find_title("Settings")
    if sh:
        sl, st, sr, sb = win32gui.GetWindowRect(sh)
        click(sl + (sr - sl) // 2, st + int((sb - st) * 0.38))
    time.sleep(1.0)
    cap("sv04_pair_android", "Pair")
    esc()
    esc()
    print("done", OUT)


if __name__ == "__main__":
    main()
