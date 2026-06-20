"""Settings + hotkey visibility smoke for hotkey-settings-polish lane."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "visual_smoke" / "hotkey_settings_polish"
OUT_JSON = ROOT / "visual_smoke" / "hotkey_settings_smoke.json"
GATE_JSON = ROOT / "visual_smoke" / "hotkey_settings_polish_gate.json"


def _label_texts(widget) -> list[str]:
    import customtkinter as ctk

    texts: list[str] = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            texts.append(child.cget("text"))
        texts.extend(_label_texts(child))
    return texts


def main() -> int:
    from cache_vault.core.settings import Settings
    from cache_vault.ui.dialogs import SettingsDialog

    src = inspect.getsource(SettingsDialog.__init__)
    checks = {
        "keyboard_shortcuts_section": "Keyboard Shortcuts" in src,
        "quick_paste_menu_label": "Quick Paste menu" in src,
        "save_to_vault_label": "Save to Vault" in src,
        "skip_capture_label": "Skip capture" in src,
        "reset_defaults_button": "Reset shortcuts to defaults" in src,
        "shortcut_help_button": "Shortcut help" in src,
        "hotkey_status_helper": "_refresh_hotkey_statuses" in src,
        "geometry_520x720": 'geometry("520x720")' in src.replace(" ", ""),
    }

    result = {
        "pass": all(checks.values()),
        "checks": checks,
        "screenshots": {},
    }

    try:
        import customtkinter as ctk
        from PIL import ImageGrab

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ctk.set_appearance_mode("dark")
        root = ctk.CTk()
        root.withdraw()
        dialog = SettingsDialog(root, Settings(), on_save=lambda _s: None)
        dialog.update_idletasks()

        labels = _label_texts(dialog._scroll_body)
        result["checks"]["status_labels_present"] = any(
            t.startswith("Ready ·") or "Missing key" in t or "Same shortcut" in t
            for t in labels
        )
        result["pass"] = all(result["checks"].values())

        def _grab(win, name: str) -> None:
            win.update_idletasks()
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            if w < 100 or h < 100:
                return
            path = OUT_DIR / name
            ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
            result["screenshots"][name] = str(path.relative_to(ROOT)).replace("\\", "/")

        _grab(dialog, "01_settings_keyboard_shortcuts.png")
        help_win = dialog._show_hotkey_help()
        dialog.update_idletasks()
        if help_win is not None:
            _grab(help_win, "02_hotkey_help.png")
            help_win.destroy()

        dialog.destroy()
        root.destroy()
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["pass"] = False

    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    gate = {
        "branch": "feature/hotkey-settings-polish",
        "lane": "hotkey-settings-polish",
        "pytest": "PENDING",
        "selftest": "PENDING",
        "settings_smoke": "PASS" if result["pass"] else "FAIL",
        "hotkey_visibility_smoke": "PASS" if result["checks"].get("status_labels_present") else "FAIL",
        "screenshots_captured": bool(result.get("screenshots")),
        "receipts": {
            "smoke": "visual_smoke/hotkey_settings_smoke.json",
            "gate": "visual_smoke/hotkey_settings_polish_gate.json",
        },
        "screenshots": result.get("screenshots", {}),
    }
    GATE_JSON.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
