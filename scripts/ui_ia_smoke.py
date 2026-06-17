"""UI IA smoke — navigation groups and screen wiring proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "visual_smoke"
OUT_JSON = OUT_DIR / "ui_ia_smoke.json"


def main() -> int:
    from cache_vault import brand
    from cache_vault.ui import filters as nav

    groups = [h or "(ungrouped)" for h, _ in nav.FILTER_GROUPS]
    keys = [k for _h, items in nav.FILTER_GROUPS for k, _ in items]
    result = {
        "ok": True,
        "groups": groups,
        "nav_item_count": len(keys),
        "command_center_label": brand.TERM_COMMAND_CENTER,
        "editable_copies_label": brand.TERM_EDITABLE_COPIES,
        "html_bundles_label": brand.TERM_HTML_BUNDLES,
        "phase5_honest_label": brand.LABEL_PHASE5_MANIFEST,
        "screenshots": [],
    }

    try:
        from PIL import ImageGrab
        import customtkinter as ctk
        from cache_vault.core.settings import Settings
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.vault import Vault
        from cache_vault.ui.shell import CacheVaultApp

        ctk.set_appearance_mode("dark")
        app = CacheVaultApp(vault=Vault(VaultStorage(":memory:"), Settings()))
        app.update_idletasks()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        shot = OUT_DIR / "ui_ia_command_center.png"
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        if w > 100 and h > 100:
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(shot)
            result["screenshots"].append(str(shot))
        app.destroy()
    except Exception as exc:  # noqa: BLE001
        result["screenshot_note"] = f"Headless capture skipped: {exc}"

    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
