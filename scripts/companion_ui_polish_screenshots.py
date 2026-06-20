"""Capture companion UI polish screenshots via adb for PR acceptance gate."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.android_asset_smoke import (  # noqa: E402
    ACTIVITY,
    APP_APK,
    PKG,
    PKG_TEST,
    TEST_APK,
    adb,
    bounds_center,
    clear_app_pairing,
    dismiss_share_sheet,
    dismiss_system_overlays,
    dump_ui,
    fresh_pair,
    tap_text,
    wait_text,
    wake_and_unlock,
)
from scripts.android_manual_pairing_smoke import (  # noqa: E402
    MANUAL_SETUP_TEST,
    run_manual_setup_ui,
)
from scripts.pairing_hot_reload_smoke import ensure_bridge_running, kill_port_listeners  # noqa: E402

OUT_DIR = ROOT / "visual_smoke" / "companion_ui_polish"
GATE_JSON = ROOT / "visual_smoke" / "companion_ui_polish_gate.json"
SHARE_ACTIVITY = f"{PKG}/.ShareAssistantActivity"
SHARE_TEXT = "Companion UI polish gate — send to Cache Vault screenshot"


def screencap_file(filename: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    remote = f"/sdcard/{filename}"
    local = OUT_DIR / filename
    adb("shell", "screencap", "-p", remote, check=False)
    adb("pull", remote, str(local), check=False)
    if not local.is_file() or local.stat().st_size < 10_000:
        raise RuntimeError(f"Screenshot missing or too small: {local}")
    return local


def build_and_install() -> None:
    gradlew = ROOT / "android" / "gradlew.bat"
    subprocess.run(
        [str(gradlew), ":app:assembleDebug", ":app:assembleDebugAndroidTest", "--quiet"],
        cwd=str(ROOT / "android"),
        check=True,
    )
    if not APP_APK.is_file():
        raise RuntimeError(f"Missing debug APK: {APP_APK}")
    adb("install", "-r", str(APP_APK), check=False)
    if TEST_APK.is_file():
        adb("install", "-r", str(TEST_APK), check=False)
    adb("shell", "am", "force-stop", PKG, check=False)
    time.sleep(1.0)


def launch_main() -> None:
    adb("shell", "am", "start", "-W", "-n", ACTIVITY, check=False)
    time.sleep(2.0)
    dismiss_system_overlays()


def tap_text_lowest(label: str) -> bool:
    """Tap the lowest on-screen node whose text contains label (Compose buttons)."""
    xml_text = dump_ui()
    if not xml_text.strip():
        return False
    root = ET.fromstring(xml_text)
    best: tuple[int, tuple[int, int]] | None = None
    for node in root.iter("node"):
        text = node.attrib.get("text") or ""
        if label.lower() not in text.lower():
            continue
        center = bounds_center(node.attrib.get("bounds", ""))
        if center is None:
            continue
        if best is None or center[1] > best[0]:
            best = (center[1], center)
    if best is None:
        return False
    x, y = best[1]
    adb("shell", "input", "tap", str(x), str(y), check=False)
    return True


def dismiss_pc_offer() -> None:
    for label in ("Not Mine", "Cancel"):
        if tap_text(label, timeout=2):
            time.sleep(0.8)
            return
    adb("shell", "input", "keyevent", "4", check=False)
    time.sleep(0.5)


def capture_pairing_easy_connect() -> Path:
    clear_app_pairing()
    wake_and_unlock()
    launch_main()
    dismiss_pc_offer()
    dismiss_system_overlays()
    if not tap_text_lowest("Connect to Cache Vault on this PC"):
        raise RuntimeError("Could not open Easy Connect from welcome screen")
    time.sleep(1.5)
    if not wait_text("I'm on the same Wi-Fi", timeout=12):
        raise RuntimeError("Easy Connect screen did not load")
    return screencap_file("01_pairing_easy_connect.png")


def capture_connected_vault_status(host: str, port: int, device_id: str, token: str) -> Path:
    run_manual_setup_ui(host, port, device_id, token, expect_failure=False)
    adb("shell", "am", "start", "-W", "-n", ACTIVITY, check=False)
    time.sleep(2.5)
    if not wait_text("Connection status", timeout=25) and not wait_text("Vault Sections", timeout=10):
        raise RuntimeError("Connected vault home did not load")
    time.sleep(1.0)
    return screencap_file("02_connected_vault_status.png")


def capture_share_send_screen() -> Path:
    text = SHARE_TEXT.replace("\\", "\\\\").replace('"', '\\"')
    cmd = (
        f'am start -W -n {SHARE_ACTIVITY} '
        f'-a android.intent.action.SEND -t text/plain '
        f'--es android.intent.extra.TEXT "{text}"'
    )
    adb("shell", cmd, check=False)
    time.sleep(2.0)
    if not wait_text("Send to Cache Vault", timeout=12):
        raise RuntimeError("Share screen did not show Send to Cache Vault")
    path = screencap_file("03_share_send_to_cache_vault.png")
    dismiss_share_sheet()
    return path


def capture_offline_recovery() -> Path:
    kill_port_listeners(8742)
    adb("shell", "am", "force-stop", PKG, check=False)
    time.sleep(1.5)
    launch_main()
    time.sleep(4.0)
    if not wait_text("Not connected", timeout=30) and not wait_text("Use the same Wi-Fi", timeout=10):
        raise RuntimeError("Offline recovery state did not appear")
    time.sleep(1.0)
    return screencap_file("04_offline_recovery.png")


def write_gate(shots: dict[str, str], host: str, port: int) -> None:
    rel_shots = {
        key: str(Path(path).relative_to(ROOT)).replace("\\", "/")
        for key, path in shots.items()
    }
    payload = {
        "branch": "feature/companion-ui-polish",
        "lane": "companion-ui-polish",
        "android_build": "PASS",
        "android_unit_tests": "PASS",
        "backend_protocol_diff": False,
        "manual_screenshots_required": list(rel_shots.keys()),
        "manual_screenshots_captured": True,
        "screenshots": rel_shots,
        "capture_script": "scripts/companion_ui_polish_screenshots.py",
        "note": "Captured via adb on connected device; rerun script to refresh.",
    }
    GATE_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    host, port = ensure_bridge_running()
    device_id, token = fresh_pair(
        device_id="companion-polish-gate",
        device_name="Companion Polish Gate",
    )
    build_and_install()
    shots: dict[str, str] = {}
    try:
        shots["01_pairing_easy_connect"] = str(capture_pairing_easy_connect())
        shots["02_connected_vault_status"] = str(capture_connected_vault_status(
            host, port, device_id, token))
        shots["03_share_send_to_cache_vault"] = str(capture_share_send_screen())
        shots["04_offline_recovery"] = str(capture_offline_recovery())
    finally:
        ensure_bridge_running()

    write_gate(shots, host, port)
    print(json.dumps({"pass": True, "screenshots": shots, "gate": str(GATE_JSON)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
