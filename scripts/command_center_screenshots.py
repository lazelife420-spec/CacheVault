"""Capture the Command Center → Hotkey Actions screen with a privacy-safe demo.

Writes screenshots to visual_smoke/ using an isolated temp LOCALAPPDATA so the
user's real vault, settings, hotkey actions, and run log are never touched.
Only generic demo fixtures are used — never real clipboard history.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cv_cc_shot_"))
os.environ["LOCALAPPDATA"] = str(_TMP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "visual_smoke"


def _build_demo():
    from cache_vault.core import command_center as cc
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.vault_macros import Macro, MacroStore

    settings = Settings()
    settings.auto_capture_enabled = False
    settings.capture_paused = True
    settings.first_use_guide_dismissed = True
    settings._persist_path = _TMP / "CacheVault" / "settings.json"

    storage = VaultStorage(str(_TMP / "CacheVault" / "cache_vault.db"))
    vault = Vault(storage=storage, settings=settings)
    for content, app_name in (
        ("docker compose up -d --build", "Terminal"),
        ("https://docs.cachevault.app/getting-started", "Browser"),
        ("Release checklist: pricing, notes, schedule post", "Notes"),
    ):
        vault.capture(content, source_app=app_name, force=True)

    # A demo macro so the "Run Vault Macro" action has a real target.
    macro_store = MacroStore()
    sig = Macro(id="demo-sig", name="Email signature",
                body="Best regards,\nYour Name", smart_type="signature")
    macro_store.upsert(sig)

    cc.seed_demo_actions(cc.HotkeyActionStore(), macro_id="demo-sig",
                         macro_label="Email signature")
    return vault


def _grab(app):
    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    hwnd = user32.GetAncestor(app.winfo_id(), 2)
    user32.SetForegroundWindow(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom),
                          all_screens=True)


def main() -> int:
    import customtkinter as ctk

    from cache_vault.ui.filters import NAV_HOTKEY_ACTIONS
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    apply_app_theme()
    ctk.set_appearance_mode("dark")

    vault = _build_demo()
    app = CacheVaultApp(vault)
    app.geometry("1320x860")
    app.update()

    done = {"ok": False}

    def shoot():
        try:
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            app.update_idletasks()
            app.lift()
            app.attributes("-topmost", True)
            app.update()
            time.sleep(0.5)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out = OUT_DIR / "command_center_hotkey_actions.png"
            _grab(app).save(out, format="PNG")
            print(f"Wrote {out.relative_to(ROOT)}")
            done["ok"] = True
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"capture failed: {exc}\n")
        finally:
            os._exit(0 if done["ok"] else 1)

    app.after(1200, shoot)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
