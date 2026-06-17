"""Restore a fresh pixel-live pairing on PC and push it to the connected phone."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.android_asset_smoke import (  # noqa: E402
    ADB,
    APP_APK,
    EXE,
    PKG_TEST,
    TEST_APK,
    adb,
    bridge_host_port,
    curl_status,
    fresh_pair,
)


def push_pairing_to_phone(host: str, port: int, device_id: str, token: str) -> None:
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
        "-e", "class", "com.prooffoundry.cachevaultmobile.PairingRestoreInstrumentedTest",
        "-e", "host", host,
        "-e", "port", str(port),
        "-e", "device_id", device_id,
        "-e", "token", token,
        f"{PKG_TEST}/androidx.test.runner.AndroidJUnitRunner",
        check=False,
    )
    if proc.returncode != 0 or "FAILURES" in (proc.stdout or ""):
        raise RuntimeError(f"Pairing restore failed:\n{proc.stdout}\n{proc.stderr}")
    if "OK (1 test)" not in (proc.stdout or "") and "OK (" not in (proc.stdout or ""):
        raise RuntimeError(f"Unexpected instrument output:\n{proc.stdout}")


def main() -> int:
    if not ADB.is_file():
        print("adb not found", file=sys.stderr)
        return 1
    devices = adb("devices").stdout.strip().splitlines()
    if len([l for l in devices if "\tdevice" in l]) < 1:
        print("no adb device — plug in phone with USB debugging", file=sys.stderr)
        return 1
    if not EXE.is_file():
        print(f"Missing {EXE} — rebuild first", file=sys.stderr)
        return 1

    host, port = bridge_host_port()
    device_id, token = fresh_pair()
    time.sleep(0.5)
    code, _ = curl_status(device_id, token, host="127.0.0.1")
    if code != 200:
        print(f"PC bridge auth failed: {code}", file=sys.stderr)
        return 1

    push_pairing_to_phone(host, port, device_id, token)
    print(f"OK — phone restored as {device_id} @ {host}:{port}")
    print("Open Cache Vault Mobile and pull to refresh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
