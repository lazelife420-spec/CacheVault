"""Launch Cache Vault with a privacy-safe demo vault and capture the real UI.

Writes a real screenshot of the running app to assets/cache-vault-ui-shot.png.

Safety:
  * Uses an isolated temp LOCALAPPDATA, so the user's real vault/settings are
    never read or written.
  * Auto-capture is disabled and capture is paused, so nothing from the real
    clipboard is ever stored. All clips are explicit, generic fixtures.
  * No emails, tokens, personal paths, or private filenames in the fixtures.
"""

from __future__ import annotations

import ctypes
import os
import sys
import tempfile
from ctypes import wintypes
from io import BytesIO
from pathlib import Path

# Isolate all on-disk state BEFORE importing the app (paths read env at runtime).
_TMP = Path(tempfile.mkdtemp(prefix="cv_shot_"))
os.environ["LOCALAPPDATA"] = str(_TMP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

OUT = ROOT / "assets" / "cache-vault-ui-shot.png"


def _demo_png() -> bytes:
    img = Image.new("RGB", (480, 300), (16, 20, 26))
    d = ImageDraw.Draw(img)
    for y in range(300):
        t = y / 300
        d.line([(0, y), (480, y)], fill=(int(16 + 10 * t), int(40 + 30 * t), int(50 + 40 * t)))
    d.rounded_rectangle((30, 30, 450, 120), radius=10, outline=(52, 196, 174), width=3)
    d.rectangle((30, 160, 300, 175), fill=(52, 196, 174))
    d.rectangle((30, 195, 220, 208), fill=(90, 110, 120))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_demo_vault():
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    settings = Settings()
    settings.auto_capture_enabled = False
    settings.capture_paused = True
    settings.block_sensitive_auto_capture = True
    settings.mobile_access_enabled = False
    settings.vault_lock_enabled = False
    settings.vault_lock_on_startup = False
    settings.first_use_guide_dismissed = True
    settings.start_with_windows = False
    settings._persist_path = _TMP / "CacheVault" / "settings.json"

    storage = VaultStorage(str(_TMP / "CacheVault" / "cache_vault.db"))
    vault = Vault(storage=storage, settings=settings)

    fixtures = [
        ("docker compose up -d --build", "Terminal"),
        ("https://docs.cachevault.app/getting-started", "Browser"),
        ("Standup notes: clipboard vault MVP done, wiring proof export next", "Notes"),
        ("def export_proof(clips, path):\n    return create_proof_zip(clips, path)", "Editor"),
        ("git switch -c release/v0.1.3 && git push -u origin HEAD", "Terminal"),
        ("Cache Vault launch checklist: finalize pricing, cut release notes, schedule post", "Notes"),
    ]
    clips = []
    for content, app_name in fixtures:
        clip = vault.capture(content, source_app=app_name, force=True)
        if clip is not None:
            clips.append(clip)

    img_clip = vault.capture_image(_demo_png(), width=480, height=300,
                                   source_app="Snipping Tool",
                                   original_name="dashboard-preview.png", force=True)

    # Favorites (float to top, survive pruning) and a collection — real features.
    if clips:
        vault.set_favorite(clips[-1].id, True)   # launch checklist
        vault.set_favorite(clips[1].id, True)    # docs link
        for c in (clips[-1], clips[4], clips[2]):
            vault.set_collection(c.id, "Launch")

    select_id = clips[-1].id if clips else (img_clip.id if img_clip else None)
    return vault, select_id


def _toplevel_hwnd(app) -> int:
    GA_ROOT = 2
    return ctypes.windll.user32.GetAncestor(app.winfo_id(), GA_ROOT)


def _grab_window(app) -> Image.Image:
    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    hwnd = _toplevel_hwnd(app)
    user32.SetForegroundWindow(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    return ImageGrab.grab(bbox=bbox, all_screens=True)


def main() -> int:
    import customtkinter as ctk

    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    apply_app_theme()
    ctk.set_appearance_mode("dark")

    vault, select_id = build_demo_vault()
    app = CacheVaultApp(vault)
    app.geometry("1320x860")
    app.update()

    state = {"done": False}

    def stage():
        try:
            if select_id is not None:
                app._select_clip_by_id(select_id)
            app.update_idletasks()
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"stage warning: {exc}\n")

    def shoot():
        try:
            app.lift()
            app.attributes("-topmost", True)
            app.update()
            import time
            time.sleep(0.4)
            img = _grab_window(app)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            img.save(OUT, format="PNG")
            print(f"Wrote {OUT.relative_to(ROOT)} ({img.size[0]}x{img.size[1]})")
            state["done"] = True
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"capture failed: {exc}\n")
        finally:
            os._exit(0 if state["done"] else 1)

    app.after(700, stage)
    app.after(1600, shoot)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
