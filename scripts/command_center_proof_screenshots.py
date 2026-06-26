"""Capture the five Phase 1 proof screenshots for Command Center.

Privacy-safe: runs against an isolated temp LOCALAPPDATA with generic demo
fixtures only. Never touches the user's real vault, settings, or run log.

Outputs (visual_smoke/):
  1. proof_1_main_vault.png            - main vault screen
  2. proof_2_hotkey_actions.png        - Command Center -> Hotkey Actions
  3. proof_3_editor.png                - hotkey action editor (ready status)
  4. proof_4_conflict.png              - editor showing conflict warning
  5. proof_5_run_status.png            - successful run toast / status update
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cv_cc_proof_"))
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

    macro_store = MacroStore()
    macro_store.upsert(Macro(id="demo-sig", name="Email signature",
                             body="Best regards,\nYour Name", smart_type="signature"))

    cc.seed_demo_actions(cc.HotkeyActionStore(), macro_id="demo-sig",
                         macro_label="Email signature")
    return vault


def _grab(win, out_name: str):
    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    win.update_idletasks()
    win.lift()
    try:
        win.attributes("-topmost", True)
    except Exception:  # noqa: BLE001
        pass
    win.update()
    time.sleep(0.45)
    hwnd = user32.GetAncestor(win.winfo_id(), 2)
    user32.SetForegroundWindow(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / out_name
    img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom),
                         all_screens=True)
    img.save(out, format="PNG")
    print(f"Wrote {out.relative_to(ROOT)} ({img.size[0]}x{img.size[1]})")


def main() -> int:
    import customtkinter as ctk

    from cache_vault.ui.command_center import HotkeyActionDialog
    from cache_vault.ui.filters import NAV_HOTKEY_ACTIONS
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    apply_app_theme()
    ctk.set_appearance_mode("dark")

    vault = _build_demo()
    app = CacheVaultApp(vault)
    app.geometry("1320x860")
    app.update()

    state = {"step": 0, "ok": False}

    def run_steps():
        try:
            # 1. Main vault.
            app.update()
            _grab(app, "proof_1_main_vault.png")

            # 2. Command Center -> Hotkey Actions.
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            app.update()
            _grab(app, "proof_2_hotkey_actions.png")

            # 3 + 4. Editor dialog (ready, then conflict).
            from cache_vault.core import command_center as cc
            others = app._command_store.load_all()
            dialog = HotkeyActionDialog(
                app, None,
                safes=app._command_safe_options(),
                macros=app._command_macro_options(),
                other_actions=others,
                reserved_specs=app._command_reserved_specs(),
                win32_available=app._command_hotkeys.available,
                on_save=lambda a: None,
                on_delete=None,
            )
            dialog._name.delete(0, "end")
            dialog._name.insert(0, "Save invoice to Safe")
            dialog._hotkey.delete(0, "end")
            dialog._hotkey.insert(0, "ctrl+alt+i")
            dialog._refresh_status()
            dialog.update()
            time.sleep(0.4)
            _grab(dialog, "proof_3_editor.png")

            # Conflict: reuse an existing demo action's shortcut.
            dialog._hotkey.delete(0, "end")
            dialog._hotkey.insert(0, "ctrl+alt+v")  # used by demo "Open Quick Paste"
            dialog._refresh_status()
            dialog.update()
            time.sleep(0.4)
            _grab(dialog, "proof_4_conflict.png")
            dialog.destroy()
            app.update()

            # 5. Successful run -> real toast via the live handler.
            app._navigate_screen(NAV_HOTKEY_ACTIONS)
            app.update()
            app._command_action_run_button("demo-pause-capture")
            app.update()
            time.sleep(0.3)
            _grab(app, "proof_5_run_status.png")

            state["ok"] = True
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            sys.stderr.write(f"capture failed: {exc}\n")
        finally:
            os._exit(0 if state["ok"] else 1)

    app.after(1200, run_steps)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
