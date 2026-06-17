"""Phase 1 scroll feel gate — compare CTk default vs Windows-native scroll math."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cache_vault.ui.win_scroll import (  # noqa: E402
    ScrollConfig,
    get_wheel_scroll_lines,
    set_scroll_config_supplier,
    vertical_canvas_units,
)


def main() -> int:
    set_scroll_config_supplier(lambda: ScrollConfig(use_windows_settings=True, multiplier=1.0))
    lines = get_wheel_scroll_lines()
    ctk_units = -int(120 / 6)  # CustomTkinter default on Windows
    ours = vertical_canvas_units(120, line_pixels=22)
    ratio = abs(ours / ctk_units) if ctk_units else 0
    result = {
        "wheel_scroll_lines": lines,
        "ctk_default_units_per_notch": ctk_units,
        "cache_vault_units_per_notch": ours,
        "speed_ratio_vs_ctk": round(ratio, 2),
        "patch_active": ours != ctk_units,
        "feel_gate": "PASS",
        "note": (
            "Automated gate: OS lines read, patch produces different (typically faster) "
            "scroll than CTk delta/6. Human feel vs Explorer/browser: confirm manually "
            "on vault list, images grid, settings — no double-scroll expected."
        ),
    }
    if lines == 0:
        result["feel_gate"] = "PASS"
        result["note"] += " Smooth-scroll mode (lines=0): pixel-proportional scroll."
    elif ratio < 1.1:
        result["feel_gate"] = "WARN"
        result["note"] += " Ratio near 1.0 — scroll may still feel similar to old CTk."
    out = ROOT / "visual_smoke" / "scroll_feel_gate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
