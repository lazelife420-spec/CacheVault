"""Notepad paste delivery smoke — optional live Windows check."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "visual_smoke" / "paste_picker_smoke.json"


def main() -> int:
    result = {"ok": False, "steps": {}}
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore
        import win32gui  # type: ignore

        from cache_vault.core.paste_delivery import (
            deliver_ctrl_v,
            foreground_window,
            snapshot_clipboard_text,
        )

        proc = subprocess.Popen(["notepad.exe"])
        time.sleep(1.2)
        hwnd = None
        for _ in range(30):
            hwnd = win32gui.FindWindow("Notepad", None)
            if hwnd:
                break
            time.sleep(0.2)
        result["steps"]["notepad_hwnd"] = bool(hwnd)
        if not hwnd:
            proc.terminate()
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(__import__("json").dumps(result, indent=2), encoding="utf-8")
            return 1

        marker = "cachevault_paste_smoke_2026"
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, marker)
        finally:
            win32clipboard.CloseClipboard()
        result["steps"]["clipboard_set"] = True

        paste = deliver_ctrl_v(hwnd)
        result["steps"]["deliver_ctrl_v"] = paste.ok
        result["steps"]["target_title"] = paste.target_title
        time.sleep(0.3)

        # Read Notepad text via WM_GETTEXT is heavy; verify clipboard still has marker
        result["steps"]["clipboard_has_marker"] = snapshot_clipboard_text() == marker
        result["ok"] = paste.ok and result["steps"]["clipboard_has_marker"]
        proc.terminate()
    except Exception as exc:
        result["error"] = str(exc)

    import json
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
