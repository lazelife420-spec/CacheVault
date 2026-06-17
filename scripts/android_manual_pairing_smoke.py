"""Real-device Manual Setup UI + invalid token + Share-to-PC smoke."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
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
    fresh_pair,
    screencap,
    tap_text,
    wait_text,
)
from scripts.pairing_hot_reload_smoke import ensure_bridge_running  # noqa: E402

OUT = SHOT_DIR / "android_manual_pairing_smoke.json"
SHARE_ACTIVITY = f"{PKG}/.ShareAssistantActivity"
TEST_URL = "https://example.com/manual-pairing-gate"
TEST_TEXT = f"Cache Vault manual pairing gate — {TEST_URL}"
INVALID_TOKEN = "00000000000000000000000000000000"
MANUAL_SETUP_TEST = "com.prooffoundry.cachevaultmobile.ManualSetupFlowInstrumentedTest"
RELEASE_APK = (
    ROOT / "dist" / "release" / f"v{__version__}" /
    f"CacheVault-Mobile-v{__version__}-debug.apk"
)


def app_apk_path() -> Path:
    return RELEASE_APK if RELEASE_APK.is_file() else APP_APK


def build_and_install() -> None:
    gradlew = ROOT / "android" / "gradlew.bat"
    subprocess.run(
        [str(gradlew), ":app:assembleDebug", ":app:assembleDebugAndroidTest", "--quiet"],
        cwd=str(ROOT / "android"),
        check=True,
    )
    adb("install", "-r", str(app_apk_path()), check=False)
    adb("install", "-r", str(TEST_APK), check=False)
    adb("shell", "am", "force-stop", PKG, check=False)
    time.sleep(1.0)


def run_manual_setup_ui(
    host: str,
    port: int,
    device_id: str,
    token: str,
    *,
    expect_failure: bool = False,
) -> None:
    args = [
        "shell", "am", "instrument", "-w", "-r",
        "-e", "class", MANUAL_SETUP_TEST,
        "-e", "host", host,
        "-e", "port", str(port),
        "-e", "device_id", device_id,
        "-e", "token", token,
    ]
    if expect_failure:
        args.extend(["-e", "expect_failure", "1"])
    args.append(f"{PKG_TEST}/androidx.test.runner.AndroidJUnitRunner")
    proc = adb(*args, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or "FAILURES" in out or "OK (" not in out:
        raise RuntimeError(f"Manual Setup UI test failed:\n{out}")


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


def wait_receipt_actions_since(since: int, timeout: float = 8.0) -> list[str]:
    deadline = time.time() + timeout
    actions: list[str] = []
    while time.time() < deadline:
        actions = receipt_actions_since(since)
        if "mobile_sent_to_pc" in actions:
            return actions
        time.sleep(0.5)
    return actions


def launch_share_sheet() -> None:
    text = TEST_TEXT.replace("\\", "\\\\").replace('"', '\\"')
    cmd = (
        f'am start -W -n {SHARE_ACTIVITY} '
        f'-a android.intent.action.SEND -t text/plain '
        f'--es android.intent.extra.TEXT "{text}"'
    )
    adb("shell", cmd, check=False)
    time.sleep(2.0)


def run_share_flow(inbox_before: int, rec_before: int) -> dict:
    launch_share_sheet()
    screencap("share_smoke_01_simple_mode")
    if not tap_text("Send to PC", timeout=12):
        raise RuntimeError("Could not tap Send to PC")
    sent = wait_text("Sent to PC", timeout=15.0)
    time.sleep(1.0)
    screencap("share_smoke_02_after_send")
    inbox_after = mobile_inbox_count()
    clip = latest_mobile_share()
    rec_actions = wait_receipt_actions_since(rec_before)
    server_confirmed = inbox_after > inbox_before and "mobile_sent_to_pc" in rec_actions
    dismiss_share_sheet()
    return {
        "checks": {
            "status_sent": sent or server_confirmed,
            "inbox_item_created": inbox_after > inbox_before,
            "content_has_url": bool(clip and TEST_URL in (clip.get("content") or "")),
            "receipt_logged": "mobile_sent_to_pc" in rec_actions,
        },
        "inbox_before": inbox_before,
        "inbox_after": inbox_after,
        "clip": clip,
        "receipt_actions": rec_actions,
    }


def unauthenticated_send_rejected(host: str, port: int) -> bool:
    payload = json.dumps({
        "item_type": "text",
        "content": "should-not-land",
        "user_action": "send_to_pc",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}/mobile/v1/inbox/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status >= 400
    except urllib.error.HTTPError as e:
        return e.code in (401, 403, 503)
    except OSError:
        return True


def capture_manual_setup_screenshot() -> None:
    adb("shell", "am", "start", "-W", "-n", f"{PKG}/.MainActivity", check=False)
    time.sleep(2.0)
    if tap_text("Manual Setup", timeout=10):
        time.sleep(1.0)
        screencap("mobile_manual_setup")


def main() -> int:
    if not ADB.is_file():
        print(json.dumps({"pass": False, "error": "adb not found"}))
        return 1

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    host, port = ensure_bridge_running()
    device_id, token = fresh_pair(device_id="manual-pair-gate", device_name="Samsung Manual Gate")
    code, _ = curl_status(device_id, token, host=host)
    if code != 200:
        host = "192.168.0.16"
        code, _ = curl_status(device_id, token, host=host)
    if code != 200:
        print(json.dumps({"pass": False, "error": f"bridge not reachable (status {code})"}))
        return 1

    build_and_install()
    capture_manual_setup_screenshot()

    invalid_error: str | None = None
    try:
        run_manual_setup_ui(host, port, device_id, INVALID_TOKEN, expect_failure=True)
        invalid_pass = True
    except RuntimeError as exc:
        invalid_pass = False
        invalid_error = str(exc)

    inbox_before = mobile_inbox_count()
    rec_before = len(json.loads(RECEIPTS.read_text(encoding="utf-8"))) if RECEIPTS.is_file() else 0

    run_manual_setup_ui(host, port, device_id, token, expect_failure=False)
    share = run_share_flow(inbox_before, rec_before)
    unauth = unauthenticated_send_rejected(host, port)

    result = {
        "manual_setup_ui": {"pass": True, "host": host, "port": port, "device_id": device_id},
        "invalid_token_pass": invalid_pass,
        "invalid_token_error": None if invalid_pass else invalid_error,
        "share_flow": share,
        "unauthenticated_send_rejected": unauth,
        "pass": (
            invalid_pass
            and share["checks"]["inbox_item_created"]
            and share["checks"]["content_has_url"]
            and share["checks"]["receipt_logged"]
            and unauth
        ),
        "screenshots": [
            str(SHOT_DIR / "mobile_manual_setup.png"),
            str(SHOT_DIR / "share_smoke_01_simple_mode.png"),
            str(SHOT_DIR / "share_smoke_02_after_send.png"),
        ],
        "receipt_path": str(RECEIPTS),
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
