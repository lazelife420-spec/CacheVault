"""Manual smoke for first-use guide and help tooltips (screenshots only)."""
from __future__ import annotations

import os
import sys
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "visual_smoke"
OUT.mkdir(parents=True, exist_ok=True)


def grab(app, name: str) -> str:
    from PIL import ImageGrab

    app.update_idletasks()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    path = OUT / f"{name}.png"
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
    return str(path)


def main() -> int:
    import customtkinter as ctk
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.filters import NAV_MOBILE_INBOX, NAV_STAMPED_RECEIPTS
    from cache_vault.ui.shell import CacheVaultApp

    tmp = Path(tempfile.mkdtemp(prefix="cv_guide_smoke_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    assert not vault.settings.first_use_guide_dismissed

    ctk.set_appearance_mode("dark")
    app = CacheVaultApp(vault=vault)
    shots: dict[str, str] = {}
    done = {"ok": False}

    def step1() -> None:
        app._open_first_use_guide(from_settings=False)
        app.update_idletasks()
        time.sleep(0.6)
        shots["first_use_guide"] = grab(app, "first_use_guide")
        for child in app.winfo_children():
            if child.winfo_class() == "CTkToplevel":
                child.destroy()
                break
        vault.settings.first_use_guide_dismissed = True
        vault.settings.save()
        app.after(100, step2)

    def step2() -> None:
        assert vault.settings.first_use_guide_dismissed
        app._navigate_screen(NAV_STAMPED_RECEIPTS)
        app.update_idletasks()
        time.sleep(0.5)
        shots["receipt_tooltip"] = grab(app, "receipt_tooltip")
        app._navigate_screen(NAV_MOBILE_INBOX)
        app.update_idletasks()
        time.sleep(0.5)
        shots["mobile_inbox_empty_state"] = grab(app, "mobile_inbox_empty_state")
        done["ok"] = True
        app.after(100, app.destroy)

    app.after(300, step1)
    app.mainloop()

    result = {
        "pass": done["ok"] and len(shots) == 3,
        "screenshots": shots,
        "dismissed": vault.settings.first_use_guide_dismissed,
        "guide_title": "Welcome to Cache Vault",
    }
    out = OUT / "first_use_guide_smoke.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result)
    return 0 if done["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
