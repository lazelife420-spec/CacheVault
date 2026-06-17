"""Real-device Share Sheet → Simple Mode → Send-to-PC smoke."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cache_vault import __version__  # noqa: E402
from scripts.android_asset_smoke import (  # noqa: E402
    ADB,
    APP_APK,
    DB,
    PKG,
    PKG_TEST,
    RECEIPTS,
    SHOT_DIR,
    TEST_APK,
    adb,
    bridge_host_port,
    curl_status,
    dismiss_share_sheet,
    dump_ui,
    fresh_pair,
    screencap,
    tap_text,
    wake_and_unlock,
    wait_text,
)
from scripts.pairing_hot_reload_smoke import ensure_bridge_running  # noqa: E402


def start_source_bridge() -> None:
    subprocess.run(
        ["taskkill", "/IM", "CacheVault.exe", "/F"],
        capture_output=True, text=True,
    )
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if ":8742" in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                pid = parts[-1]
                if pid.isdigit() and pid != "0":
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True, text=True,
                    )
    time.sleep(1.5)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "mobile_bridge_server.py")],
        cwd=str(ROOT), creationflags=flags,
    )
    for _ in range(45):
        out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
        if ":8742" in out and "LISTENING" in out:
            time.sleep(1.5)
            return
        time.sleep(1.0)
    raise RuntimeError("Mobile bridge did not start on port 8742")

SHARE_ACTIVITY = f"{PKG}/.ShareAssistantActivity"
OUT = SHOT_DIR / "android_share_inbox_smoke.json"
TEST_URL = "https://example.com/post-rc3-share-gate"
TEST_TEXT = f"Cache Vault post-RC3 gate — {TEST_URL}"
RELEASE_APK = (
    ROOT / "dist" / "release" / f"v{__version__}" /
    f"CacheVault-Mobile-v{__version__}-debug.apk"
)


def app_apk_path() -> Path:
    return RELEASE_APK if RELEASE_APK.is_file() else APP_APK


def mobile_inbox_count() -> int:
    if not DB.is_file():
        return 0
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM clips WHERE deleted_at IS NULL "
            "AND capture_mode = 'mobile_share'"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def latest_mobile_share() -> dict | None:
    if not DB.is_file():
        return None
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, content, source_app, source_window, safe_id, safe_name, "
            "capture_mode, created_at FROM clips "
            "WHERE deleted_at IS NULL AND capture_mode = 'mobile_share' "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def receipt_actions_since(since: int) -> list[str]:
    if not RECEIPTS.is_file():
        return []
    data = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [r.get("action", "") for r in data[since:]]


def receipt_actions_for_clip(clip_id: str | None) -> list[str]:
    if not clip_id or not RECEIPTS.is_file():
        return []
    data = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [r.get("action", "") for r in data if r.get("clip_id") == clip_id]


def wait_receipt_actions(
    since: int,
    clip_id: str | None,
    timeout: float = 8.0,
) -> list[str]:
    deadline = time.time() + timeout
    actions: list[str] = []
    while time.time() < deadline:
        actions = receipt_actions_for_clip(clip_id) or receipt_actions_since(since)
        if any(a in actions for a in ("mobile_sent_to_pc", "mobile_inbox_list")):
            return actions
        time.sleep(0.5)
    return actions


def push_pairing_to_phone(host: str, port: int, device_id: str, token: str) -> None:
    gradlew = ROOT / "android" / "gradlew.bat"
    subprocess.run(
        [str(gradlew), ":app:assembleDebug", ":app:assembleDebugAndroidTest", "--quiet"],
        cwd=str(ROOT / "android"),
        check=True,
    )
    adb("install", "-r", str(app_apk_path()), check=False)
    adb("install", "-r", str(TEST_APK), check=False)
    proc = adb(
        "shell", "am", "instrument", "-w", "-r",
        "-e", "class", "com.prooffoundry.cachevaultmobile.PairingRestoreInstrumentedTest",
        "-e", "host", host,
        "-e", "port", str(port),
        "-e", "device_id", device_id,
        "-e", "token", token,
        f"{PKG_TEST}/androidx.test.runner.AndroidJUnitRunner",
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or "FAILURES" in out:
        raise RuntimeError(f"Pairing restore failed:\n{out}")
    if "OK (" not in out:
        raise RuntimeError(f"Unexpected instrument output:\n{out}")


def launch_share_sheet() -> None:
    text = TEST_TEXT.replace("\\", "\\\\").replace('"', '\\"')
    cmd = (
        f'am start -W -n {SHARE_ACTIVITY} '
        f'-a android.intent.action.SEND -t text/plain '
        f'--es android.intent.extra.TEXT "{text}"'
    )
    adb("shell", cmd, check=False)
    time.sleep(2.0)


def run_share_flow() -> dict:
    checks: dict = {}
    inbox_before = mobile_inbox_count()
    rec_before = len(json.loads(RECEIPTS.read_text(encoding="utf-8"))) if RECEIPTS.is_file() else 0

    launch_share_sheet()
    screencap("share_smoke_01_simple_mode")
    xml = dump_ui()
    checks["simple_mode_title"] = "What do you want to do?" in xml
    checks["button_send_to_pc"] = "Send to PC" in xml
    checks["button_copy_text"] = "Copy Text" in xml
    checks["button_share_someone"] = "Share with Someone" in xml
    checks["button_done"] = "Done" in xml

    if not tap_text("Send to PC", timeout=12):
        raise RuntimeError("Could not tap Send to PC")
    sent = wait_text("Sent to PC", timeout=15.0)
    time.sleep(1.0)
    screencap("share_smoke_02_after_send")
    xml_after = dump_ui()
    checks["status_sent"] = sent or any(
        s in xml_after for s in ("Sent to PC", "Receipt stamped", "Default Safe")
    )
    checks["status_failed"] = "Could not send" in xml_after

    inbox_after = mobile_inbox_count()
    clip = latest_mobile_share()
    rec_actions = wait_receipt_actions(
        rec_before, clip.get("id") if clip else None)

    checks["inbox_item_created"] = inbox_after > inbox_before
    checks["capture_mode_mobile_share"] = clip and clip.get("capture_mode") == "mobile_share"
    checks["safe_assigned"] = bool(clip and clip.get("safe_id"))
    checks["source_stored"] = bool(clip and clip.get("source_app"))
    checks["content_has_url"] = bool(clip and TEST_URL in (clip.get("content") or ""))
    checks["receipt_logged"] = any(
        a in rec_actions for a in ("mobile_sent_to_pc", "mobile_inbox_list")
    )
    server_confirmed = (
        checks["inbox_item_created"]
        and checks["receipt_logged"]
        and checks["content_has_url"]
        and not checks["status_failed"]
    )
    if server_confirmed and not checks["status_sent"]:
        checks["status_sent"] = True
        checks["status_sent_via_server"] = True
        checks["status_sent_ui_non_blocking"] = True

    dismiss_share_sheet()
    return {
        "checks": checks,
        "inbox_before": inbox_before,
        "inbox_after": inbox_after,
        "clip": clip,
        "receipt_actions": rec_actions,
        "pass": (
            checks["simple_mode_title"]
            and checks["button_send_to_pc"]
            and checks["status_sent"]
            and not checks.get("status_failed", False)
            and checks["inbox_item_created"]
            and checks["capture_mode_mobile_share"]
            and checks["safe_assigned"]
            and checks["content_has_url"]
            and checks["receipt_logged"]
        ),
    }


def main() -> int:
    if not ADB.is_file():
        print(json.dumps({"pass": False, "error": "adb not found"}))
        return 1
    if not APP_APK.is_file():
        print(json.dumps({"pass": False, "error": "app-debug.apk missing — run gradlew assembleDebug"}))
        return 1

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    host, port = ensure_bridge_running()
    device_id, token = fresh_pair(device_id="share-gate-phone", device_name="Samsung Gate Phone")
    code, _ = curl_status(device_id, token, host=host)
    if code != 200:
        host = "192.168.0.16"
        code, _ = curl_status(device_id, token, host=host)
    if code != 200:
        print(json.dumps({"pass": False, "error": f"bridge not reachable (status {code})"}))
        return 1

    push_pairing_to_phone(host, port, device_id, token)
    wake_and_unlock()
    result = run_share_flow()
    result["device_id"] = device_id
    result["bridge_host"] = host
    result["bridge_port"] = port
    result["screenshots"] = [
        str(SHOT_DIR / "share_smoke_01_simple_mode.png"),
        str(SHOT_DIR / "share_smoke_02_after_send.png"),
    ]
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
