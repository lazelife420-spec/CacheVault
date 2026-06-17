"""Capture window using PrintWindow (works better for layered dialogs)."""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

import win32con
import win32gui
import win32ui
from PIL import Image

PW_RENDERFULLCONTENT = 2


def find_hwnd(title_sub: str) -> int:
    found: list[int] = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if title_sub.lower() in t.lower():
                found.append(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else 0


def capture(hwnd: int, path: Path) -> None:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    ok = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
    if not ok:
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)
    bmpinfo = bmp.GetInfo()
    bits = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bits, "raw", "BGRX", 0, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)


def main() -> int:
    title = sys.argv[1] if len(sys.argv) > 1 else "Cache Vault"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "capture.png")
    for _ in range(30):
        hwnd = find_hwnd(title)
        if hwnd:
            capture(hwnd, out)
            print(out)
            return 0
        time.sleep(0.5)
    print("window not found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
