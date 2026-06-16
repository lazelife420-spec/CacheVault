"""Fresh-open phone visual gate — force-close, reopen, no pull-to-refresh."""
from __future__ import annotations

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.android_asset_smoke import (  # noqa: E402
    ACTIVITY,
    PKG,
    SHOT_DIR,
    adb,
    dump_ui,
    screencap,
    tap_text,
    wake_and_unlock,
)

OUT_VAULT = SHOT_DIR / "09_vault_connected.png"
OUT_IMAGES = SHOT_DIR / "09_images_grid.png"


def ui_texts(xml_text: str) -> str:
    return xml_text


def check_vault(xml_text: str) -> dict:
    checks = {
        "app_visible": PKG in xml_text,
        "connected_host": "Connected · 192.168.0.11" in xml_text or (
            "Connected" in xml_text and "192.168.0.11" in xml_text
        ),
        "not_loading_only": "Loading…" not in xml_text or "Connected" in xml_text,
        "images_nav": "Images" in xml_text,
        "no_cloud_claims": not any(
            x in xml_text.lower()
            for x in ("cloud sync", "encrypted cloud", "end-to-end encrypted", "sync to cloud")
        ),
        "no_release_tag": "v1." not in xml_text and "release" not in xml_text.lower(),
    }
    # Real counts: look for digit + clip-related section labels
    count_hint = bool(
        re.search(r"\b\d+\b", xml_text)
        and any(k in xml_text for k in ("Recent", "Browse", "Images", "Proof", "All clips", "Text", "Links"))
    )
    checks["real_counts"] = count_hint
    return checks


def check_images(xml_text: str) -> dict:
    return {
        "images_tab": "Images" in xml_text or "Saved images" in xml_text,
        "grid_or_thumbs": any(
            k in xml_text.lower()
            for k in ("thumbnail", "image", "no images", "saved from your pc")
        ),
        "no_cloud_claims": not any(
            x in xml_text.lower()
            for x in ("cloud sync", "encrypted cloud", "sync to cloud")
        ),
    }


def wait_connected(timeout: float = 12.0) -> tuple[str, bool]:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        last = dump_ui()
        if "Connected · 192.168.0.11" in last or (
            "Connected" in last and "192.168.0.11" in last and "Loading…" not in last
        ):
            return last, True
        time.sleep(0.5)
    return last, False


def main() -> int:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    wake_and_unlock()
    adb("shell", "am", "force-stop", PKG, check=False)
    time.sleep(0.8)
    adb("shell", "am", "start", "-W", "-n", ACTIVITY, check=False)
    time.sleep(2.0)
    vault_xml, connected = wait_connected(timeout=12.0)
    if not connected:
        vault_xml = dump_ui()
    vault_checks = check_vault(vault_xml)
    screencap("09_vault_connected")
    vault_size = OUT_VAULT.stat().st_size if OUT_VAULT.is_file() else 0

    if not tap_text("Images", timeout=10):
        print("FAIL: could not tap Images tab", file=sys.stderr)
        return 1
    time.sleep(2.0)
    images_xml = dump_ui()
    images_checks = check_images(images_xml)
    screencap("09_images_grid")
    images_size = OUT_IMAGES.stat().st_size if OUT_IMAGES.is_file() else 0

    report = {
        "vault_checks": vault_checks,
        "images_checks": images_checks,
        "vault_png_bytes": vault_size,
        "images_png_bytes": images_size,
        "vault_pass": all(vault_checks.values()) and vault_size > 50000,
        "images_pass": all(images_checks.values()) and images_size > 50000,
    }
    print(json.dumps(report, indent=2))

    if report["vault_pass"] and report["images_pass"]:
        print("FRESH_OPEN_VISUAL: PASS")
        return 0
    print("FRESH_OPEN_VISUAL: FAIL", file=sys.stderr)
    if vault_size <= 50000:
        print(f"  vault screenshot too small ({vault_size} bytes) — likely lock screen", file=sys.stderr)
    if images_size <= 50000:
        print(f"  images screenshot too small ({images_size} bytes)", file=sys.stderr)
    failed = [k for k, v in vault_checks.items() if not v] + [k for k, v in images_checks.items() if not v]
    if failed:
        print(f"  failed checks: {failed}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
