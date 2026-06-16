"""Real-device Android screenshot asset smoke — adb UI + PC receipt verification."""
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

from cache_vault.core import models  # noqa: E402
from cache_vault.core.mobile.models import (  # noqa: E402
    PairedDevice,
    hash_token,
    new_device_token,
)
from cache_vault.core.settings import Settings  # noqa: E402

ADB = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
PKG = "com.prooffoundry.cachevaultmobile"
ACTIVITY = f"{PKG}/.MainActivity"
EXE = ROOT / "dist" / "CacheVault.exe"
RECEIPTS = Path(os.environ.get("LOCALAPPDATA", "")) / "CacheVault" / "mobile_access_receipts.json"
DB = Path(os.environ.get("LOCALAPPDATA", "")) / "CacheVault" / "cache_vault.db"
OUT = ROOT / "visual_smoke" / "android_asset_smoke.json"
SHOT_DIR = ROOT / "visual_smoke"
PKG_TEST = f"{PKG}.test"
INSTRUMENT = "androidx.test.runner.AndroidJUnitRunner"
TEST_APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "androidTest" / "debug" / "app-debug-androidTest.apk"
APP_APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
UI_DUMP = "/sdcard/cv_smoke_ui.xml"


def adb(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(ADB), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def wake_and_unlock() -> None:
    adb("shell", "svc", "power", "stayon", "usb", check=False)
    adb("shell", "input", "keyevent", "224", check=False)  # WAKEUP
    time.sleep(0.4)
    adb("shell", "wm", "dismiss-keyguard", check=False)
    adb("shell", "input", "swipe", "540", "2100", "540", "700", "300", check=False)
    time.sleep(0.5)
    adb("shell", "input", "swipe", "540", "2100", "540", "700", "300", check=False)
    time.sleep(0.8)


def receipt_count() -> int:
    if not RECEIPTS.is_file():
        return 0
    try:
        data = json.loads(RECEIPTS.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError):
        return 0


def recent_receipts(since: int) -> list[dict]:
    if not RECEIPTS.is_file():
        return []
    data = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    return data[since:] if isinstance(data, list) else []


def latest_image_clip_id() -> str | None:
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute(
            "SELECT id FROM clips WHERE deleted_at IS NULL "
            "AND content_type = 'image' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def escape_adb_text(value: str) -> str:
    out = []
    for ch in value:
        if ch == " ":
            out.append("%s")
        elif ch in "\\;&|<>^()[]{}$`\"'":
            out.append(f"\\{ch}")
        else:
            out.append(ch)
    return "".join(out)


def fresh_pair(device_id: str = "pixel-live", device_name: str = "Pixel Phone") -> tuple[str, str]:
    settings = Settings.load()
    settings.mobile_access_enabled = True
    token = new_device_token()
    device = PairedDevice(
        device_id=device_id.strip(),
        device_name=device_name.strip(),
        created_at=models.now_iso(),
        token_hash=hash_token(token),
    )
    settings.paired_devices = [
        d for d in settings.paired_devices if d.get("device_id") != device.device_id
    ]
    settings.paired_devices.append(device.to_dict())
    settings.save()
    return device_id, token


def restart_cache_vault() -> None:
    subprocess.run(
        ["taskkill", "/IM", "CacheVault.exe", "/F"],
        capture_output=True,
        text=True,
    )
    time.sleep(2.0)
    if not EXE.is_file():
        raise RuntimeError(f"CacheVault.exe not found: {EXE}")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(EXE)], cwd=str(ROOT), creationflags=flags)
    for _ in range(60):
        out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
        if ":8742" in out and "LISTENING" in out:
            time.sleep(2.0)
            return
        time.sleep(1.0)
    raise RuntimeError("Mobile bridge did not start on port 8742")


def find_edittexts(xml_text: str) -> list[ET.Element]:
    if not xml_text.strip():
        return []
    root = ET.fromstring(xml_text)
    edits = [
        n for n in root.iter("node")
        if "EditText" in (n.attrib.get("class") or "")
        and n.attrib.get("package", PKG) == PKG
    ]
    def y_pos(node: ET.Element) -> int:
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
        return int(m.group(2)) if m else 0
    return sorted(edits, key=y_pos)


def type_slow(value: str) -> None:
    for ch in value:
        if ch.isdigit():
            adb("shell", "input", "keyevent", str(7 + int(ch)), check=False)
        elif ch == ".":
            adb("shell", "input", "keyevent", "56", check=False)
        elif ch in "-_":
            adb("shell", "input", "keyevent", "69", check=False)
        elif ch.isalpha():
            adb("shell", "input", "text", ch, check=False)
        else:
            adb("shell", "input", "text", escape_adb_text(ch), check=False)
        time.sleep(0.03)


def clear_field() -> None:
    adb("shell", "input", "keyevent", "123", check=False)
    for _ in range(80):
        adb("shell", "input", "keyevent", "67", check=False)


def dismiss_keyboard() -> None:
    adb("shell", "input", "tap", "540", "280", check=False)
    time.sleep(0.25)


def paste_into_field(text: str) -> None:
    type_slow(text)


def clear_and_type(text: str) -> None:
    adb("shell", "input", "keyevent", "123", check=False)  # MOVE_END
    for _ in range(64):
        adb("shell", "input", "keyevent", "67", check=False)  # DEL
    adb("shell", "input", "text", escape_adb_text(text), check=False)


def fill_edittext(index: int, text: str) -> None:
    dismiss_keyboard()
    edits = find_edittexts(dump_ui())
    if index >= len(edits):
        raise RuntimeError(f"Expected EditText #{index}, found {len(edits)}")
    center = bounds_center(edits[index].attrib.get("bounds", ""))
    if not center:
        raise RuntimeError(f"Could not resolve EditText bounds for index {index}")
    adb("shell", "input", "tap", str(center[0]), str(center[1]))
    time.sleep(0.35)
    clear_field()
    paste_into_field(text)
    dismiss_keyboard()


def pair_phone(host: str, port: int, device_id: str, token: str) -> None:
    wake_and_unlock()
    adb("shell", "am", "start", "-W", "-n", ACTIVITY, check=False)
    time.sleep(1.5)
    if not wait_text("Manual Setup", timeout=15):
        screencap("android_smoke_pair_fail_welcome")
        raise RuntimeError("Welcome screen did not load (unlock phone)")
    if not tap_text("Manual Setup", timeout=8):
        raise RuntimeError("Could not open Manual Setup")
    time.sleep(1.0)
    fill_edittext(0, host)
    fill_edittext(1, str(port))
    fill_edittext(2, device_id)
    fill_edittext(3, token)
    dismiss_keyboard()
    adb("shell", "input", "swipe", "540", "1600", "540", "600", "350", check=False)
    time.sleep(0.5)
    if not tap_text("Connect to My PC", timeout=8):
        raise RuntimeError("Could not tap Connect to My PC")
    if not wait_text("Screenshots", timeout=25):
        screencap("android_smoke_pair_fail")
        raise RuntimeError("Pairing did not reach home screen")
    screencap("android_smoke_00_paired_home")


def is_paired_home() -> bool:
    xml_text = dump_ui()
    return PKG in xml_text and "Screenshots" in xml_text


def mobile_settings() -> dict:
    settings_path = RECEIPTS.parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def bridge_host_port() -> tuple[str, int]:
    s = mobile_settings()
    port = int(s.get("mobile_access_port", 8742))
    host = "192.168.0.11"
    return host, port


def curl_status(device_id: str, token: str, host: str | None = None) -> tuple[int, str]:
    lan_host, port = bridge_host_port()
    target = host or lan_host
    req = urllib.request.Request(
        f"http://{target}:{port}/mobile/v1/status",
        headers={
            "X-Device-Id": device_id,
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def dump_ui() -> str:
    adb("shell", "uiautomator", "dump", UI_DUMP, check=False)
    local = SHOT_DIR / "_ui_dump.xml"
    adb("pull", UI_DUMP, str(local), check=False)
    return local.read_text(encoding="utf-8", errors="replace") if local.is_file() else ""


def bounds_center(bounds: str) -> tuple[int, int] | None:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def find_nodes(xml_text: str, text: str | None = None, desc: str | None = None) -> list[ET.Element]:
    if not xml_text.strip():
        return []
    root = ET.fromstring(xml_text)
    out: list[ET.Element] = []
    for node in root.iter("node"):
        if text is not None and node.attrib.get("text") == text:
            out.append(node)
        elif desc is not None and node.attrib.get("content-desc") == desc:
            out.append(node)
    return out


def tap_text(label: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        xml_text = dump_ui()
        nodes = find_nodes(xml_text, text=label)
        if not nodes:
            root = ET.fromstring(xml_text) if xml_text.strip() else None
            if root is not None:
                nodes = [
                    n for n in root.iter("node")
                    if label.lower() in (n.attrib.get("text") or "").lower()
                ]
        for node in nodes:
            center = bounds_center(node.attrib.get("bounds", ""))
            if center:
                adb("shell", "input", "tap", str(center[0]), str(center[1]))
                return True
        time.sleep(0.6)
    return False


def wait_text(label: str, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        xml_text = dump_ui()
        if label in xml_text:
            return True
        if PKG in xml_text and ("Connected:" in xml_text or "Screenshots" in xml_text):
            return True
        time.sleep(0.5)
    return False


def screencap(name: str) -> None:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    remote = f"/sdcard/{name}.png"
    local = SHOT_DIR / f"{name}.png"
    adb("shell", "screencap", "-p", remote, check=False)
    adb("pull", remote, str(local), check=False)


def dismiss_share_sheet() -> None:
    adb("shell", "input", "keyevent", "4", check=False)
    time.sleep(0.5)


def run_ui_flow() -> dict:
    wake_and_unlock()
    adb("shell", "am", "start", "-W", "-n", ACTIVITY, check=False)
    if not wait_text("Screenshots", timeout=20):
        screencap("android_smoke_fail_home")
        raise RuntimeError("App home did not load")
    screencap("android_smoke_01_home")

    if not tap_text("Screenshots"):
        raise RuntimeError("Could not tap Screenshots tab")
    time.sleep(1.5)
    screencap("android_smoke_02_screenshots")

    xml_text = dump_ui()
    clip_nodes = [
        n for n in ET.fromstring(xml_text).iter("node")
        if "Screenshot" in (n.attrib.get("text") or "")
    ]
    if not clip_nodes:
        raise RuntimeError("No screenshot clips visible on phone")
    center = bounds_center(clip_nodes[0].attrib.get("bounds", ""))
    if not center:
        raise RuntimeError("Could not resolve screenshot clip bounds")
    adb("shell", "input", "tap", str(center[0]), str(center[1]))
    if not wait_text("Clip detail", timeout=15):
        raise RuntimeError("Clip detail did not open")
    screencap("android_smoke_03_detail")

    if not tap_text("View"):
        raise RuntimeError("Could not tap View")
    time.sleep(3.0)
    screencap("android_smoke_04_viewed")

    if not tap_text("Share"):
        raise RuntimeError("Could not tap Share")
    time.sleep(1.0)
    screencap("android_smoke_05_share_sheet")
    dismiss_share_sheet()

    if not tap_text("Save to Phone"):
        raise RuntimeError("Could not tap Save to Phone")
    time.sleep(2.0)
    screencap("android_smoke_06_saved")

    return {"ui": "ok", "clip_preview": clip_nodes[0].attrib.get("text")}


def run_instrumented_smoke(host: str, port: int, device_id: str, token: str) -> None:
    gradlew = ROOT / "android" / "gradlew.bat"
    subprocess.run(
        [str(gradlew), ":app:assembleDebug", ":app:assembleDebugAndroidTest", "--quiet"],
        cwd=str(ROOT / "android"),
        check=True,
    )
    adb("install", "-r", str(APP_APK), check=False)
    adb("install", "-r", str(TEST_APK), check=False)
    proc = adb(
        "shell", "am", "instrument", "-w", "-r",
        "-e", "host", host,
        "-e", "port", str(port),
        "-e", "device_id", device_id,
        "-e", "token", token,
        f"{PKG_TEST}/{INSTRUMENT}",
        check=False,
    )
    if proc.returncode != 0 or "FAILURES" in (proc.stdout or "") or "Error" in (proc.stderr or ""):
        raise RuntimeError(
            "Instrumented smoke failed\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    if "OK (1 test)" not in (proc.stdout or "") and "tests passed" not in (proc.stdout or "").lower():
        if "OK (" not in (proc.stdout or ""):
            raise RuntimeError(f"Unexpected instrument output:\n{proc.stdout}\n{proc.stderr}")


def verify_receipts(before: int, clip_id: str | None) -> dict:
    new_rows = recent_receipts(before)
    by_action = {}
    for row in new_rows:
        if row.get("device_id") == "pixel-live" and row.get("result") == "ok":
            by_action.setdefault(row.get("action"), []).append(row)

    checks = {
        "status_or_list": bool(by_action.get("status") or by_action.get("list_clips")),
        "get_asset": bool(by_action.get("get_asset")),
        "share": bool(by_action.get("share")),
        "save": bool(by_action.get("save")),
    }
    if clip_id:
        asset_rows = by_action.get("get_asset", [])
        checks["get_asset_clip"] = any(r.get("clip_id") == clip_id for r in asset_rows)

    phone_ip_hits = [
        r for r in new_rows
        if r.get("device_id") == "pixel-live"
        and r.get("result") == "ok"
        and r.get("action") in {"get_asset", "share", "save", "list_clips", "get_clip"}
        and r.get("remote_ip") not in {None, "192.168.0.11", "127.0.0.1"}
    ]
    checks["phone_lan_ip"] = len(phone_ip_hits) > 0
    return {"checks": checks, "new_receipts": len(new_rows), "by_action": {k: len(v) for k, v in by_action.items()}}


def verify_revoked_device() -> dict:
    """Use a throwaway probe device — never revoke the phone's live pairing."""
    probe_id = "smoke-revoked-probe"
    settings = Settings.load()
    settings.paired_devices = [
        d for d in settings.paired_devices if d.get("device_id") != probe_id
    ]
    settings.save()
    probe_id, probe_token = fresh_pair(probe_id, "Revoke smoke probe")
    restart_cache_vault()
    code, _body = curl_status(probe_id, probe_token, host="127.0.0.1")
    if code != 200:
        return {"revoked_device_401": False, "revoked_receipt": False, "probe_auth": code}

    settings = Settings.load()
    now = models.now_iso()
    updated = []
    for raw in settings.paired_devices:
        row = dict(raw)
        if row.get("device_id") == probe_id:
            row["revoked_at"] = now
        updated.append(row)
    settings.paired_devices = updated
    settings.save()
    restart_cache_vault()
    code, _body = curl_status(probe_id, probe_token, host="127.0.0.1")
    before = receipt_count()
    curl_status(probe_id, probe_token, host="127.0.0.1")
    denied = any(
        r.get("result") == "denied" and r.get("device_id") == probe_id
        for r in recent_receipts(before)
    )
    return {"revoked_device_401": code == 401, "revoked_receipt": denied, "probe_id": probe_id}


def verify_security() -> dict:
    host, port = bridge_host_port()
    code, _body = curl_status("pixel-live", "definitely-wrong-token-smoke")
    wrong_token_ok = code == 401

    before = receipt_count()
    curl_status("pixel-live", "definitely-wrong-token-smoke-2")
    denied = any(
        r.get("result") == "denied" and r.get("action") == "status"
        for r in recent_receipts(before)
    )
    return {"wrong_token_401": wrong_token_ok, "denied_receipt": denied, "host": host, "port": port}


def main() -> int:
    if not ADB.is_file():
        print(json.dumps({"ok": False, "error": f"adb not found: {ADB}"}, indent=2))
        return 1
    devices = adb("devices").stdout.strip().splitlines()
    if len([l for l in devices if "\tdevice" in l]) < 1:
        print(json.dumps({"ok": False, "error": "no adb device"}, indent=2))
        return 1

    clip_id = latest_image_clip_id()
    host, port = bridge_host_port()
    device_id, token = fresh_pair()
    restart_cache_vault()
    code, _ = curl_status(device_id, token, host="127.0.0.1")
    if code != 200:
        print(json.dumps({"ok": False, "error": f"PC bridge auth failed after restart: {code}"}, indent=2))
        return 1

    before = receipt_count()
    security = verify_security()
    run_instrumented_smoke(host, port, device_id, token)
    time.sleep(1.0)
    receipts = verify_receipts(before, clip_id)
    revoked = verify_revoked_device()

    passed = all(
        receipts["checks"].get(k)
        for k in ("get_asset", "share", "save", "phone_lan_ip")
    ) and security["wrong_token_401"] and security["denied_receipt"]
    passed = passed and revoked["revoked_device_401"] and revoked["revoked_receipt"]

    result = {
        "ok": passed,
        "clip_id": clip_id,
        "mode": "instrumented",
        "bridge": "CacheVault.exe",
        "receipts": receipts,
        "security": {**security, **revoked},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
