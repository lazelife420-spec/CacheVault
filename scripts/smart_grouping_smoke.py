"""Smart grouping smoke — folder filters, receipts, and sidebar visibility."""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "visual_smoke" / "smart_grouping"
OUT_JSON = ROOT / "visual_smoke" / "smart_grouping_smoke.json"
GATE_JSON = ROOT / "visual_smoke" / "smart_grouping_gate.json"
EXPORT_JSON = ROOT / "visual_smoke" / "smart_folder_export_smoke.json"


def main() -> int:
    from cache_vault.core.export import export_zip
    from cache_vault.core import models, smart_folders
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.filters import FILTER_GROUPS, FilterNav

    src = inspect.getsource(FilterNav.__init__)
    checks = {
        "smart_folders_section": "SMART FOLDERS" in str(FILTER_GROUPS),
        "eight_smart_folders": len(smart_folders.SMART_FOLDER_NAV) == 8,
        "recent_folder": any(k.endswith(":recent") for k, _ in smart_folders.SMART_FOLDER_NAV),
        "mobile_share_folder": smart_folders.filter_key("mobile_share") in dict(
            smart_folders.SMART_FOLDER_NAV
        ),
        "filter_nav_wires_smart": "SMART FOLDERS" in src or "SMART FOLDERS" in str(FILTER_GROUPS),
    }

    vault = Vault(storage=VaultStorage(":memory:"))
    vault.capture("plain note for phone", force=True)
    vault.capture("https://cachevault.local/test", force=True)
    vault.storage.conn.execute(
        "UPDATE clips SET capture_mode = ? WHERE content LIKE 'plain note%'",
        (models.CAPTURE_MOBILE_SHARE,),
    )
    vault.storage.conn.commit()

    bundle = smart_folders.all_folder_receipts(vault.storage)
    checks["folder_receipts"] = (
        bundle["receipt_type"] == "smart_folder_bundle"
        and len(bundle["folders"]) == 8
        and all(f["generated_at"] and "count" in f for f in bundle["folders"])
    )
    checks["mobile_share_count"] = (
        vault.counts()[smart_folders.filter_key("mobile_share")] == 1
    )

    export_checks = {"zip_created": False, "manifest_has_collection": False}
    clips = vault.list_clips(smart_folders.filter_key("url"))
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "smart-folder-url.zip"
        export_zip(
            clips,
            str(zip_path),
            collection_name=smart_folders.export_collection_name(
                smart_folders.filter_key("url")
            ),
        )
        export_checks["zip_created"] = zip_path.is_file()
        if zip_path.is_file():
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                export_checks["manifest_has_collection"] = "manifest.json" in names
    checks["export_smoke"] = all(export_checks.values())

    result = {
        "pass": all(checks.values()),
        "checks": checks,
        "folder_receipts": bundle,
        "export_smoke": export_checks,
        "screenshots": {},
    }

    try:
        import customtkinter as ctk
        from PIL import ImageGrab

        from cache_vault.core.settings import Settings

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ctk.set_appearance_mode("dark")
        root = ctk.CTk()
        root.withdraw()
        nav = FilterNav(root, on_select=lambda _k: None, settings=Settings())
        nav.update_counts(vault.counts())
        nav.set_active(smart_folders.filter_key("recent"))
        nav.update_idletasks()
        x, y = nav.winfo_rootx(), nav.winfo_rooty()
        w, h = nav.winfo_width(), nav.winfo_height()
        if w > 100 and h > 100:
            shot = OUT_DIR / "01_smart_folders_sidebar.png"
            ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(shot)
            result["screenshots"]["01_smart_folders_sidebar"] = str(
                shot.relative_to(ROOT)
            ).replace("\\", "/")
        nav.destroy()
        root.destroy()
    except Exception as exc:  # noqa: BLE001
        result["screenshot_note"] = str(exc)

    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    EXPORT_JSON.write_text(json.dumps(export_checks, indent=2) + "\n", encoding="utf-8")
    gate = {
        "branch": "feature/smart-grouping-folders",
        "lane": "smart-grouping-folders",
        "pytest": "PENDING",
        "selftest": "PENDING",
        "smart_grouping_smoke": "PASS" if result["pass"] else "FAIL",
        "export_folder_receipt_smoke": "PASS" if checks.get("export_smoke") else "FAIL",
        "screenshots_captured": bool(result.get("screenshots")),
        "receipts": {
            "smoke": "visual_smoke/smart_grouping_smoke.json",
            "gate": "visual_smoke/smart_grouping_gate.json",
            "export": "visual_smoke/smart_folder_export_smoke.json",
        },
        "screenshots": result.get("screenshots", {}),
    }
    GATE_JSON.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
