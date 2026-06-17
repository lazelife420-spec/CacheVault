"""Verify mobile pairing credentials work without restarting CacheVault.exe."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.android_asset_smoke import (  # noqa: E402
    EXE,
    bridge_host_port,
    curl_status,
    fresh_pair,
)

OUT = ROOT / "visual_smoke" / "pairing_hot_reload_smoke.json"


def wait_bridge(port: int, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
        if f":{port}" in out and "LISTENING" in out:
            return True
        time.sleep(1.0)
    return False


def kill_port_listeners(port: int = 8742) -> None:
    subprocess.run(["taskkill", "/IM", "CacheVault.exe", "/F"], capture_output=True)
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                subprocess.run(["taskkill", "/PID", parts[-1], "/F"], capture_output=True)
    time.sleep(2.0)


def ensure_bridge_running() -> tuple[str, int]:
    if not EXE.is_file():
        raise RuntimeError(f"Missing packaged exe: {EXE}")
    kill_port_listeners()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(EXE)], cwd=str(ROOT), creationflags=flags)
    host, port = bridge_host_port()
    if not wait_bridge(port):
        raise RuntimeError(f"Bridge did not listen on port {port}")
    time.sleep(3.0)
    return host, port


def main() -> int:
    host, port = ensure_bridge_running()

    device_id, token = fresh_pair(
        device_id="hot-reload-smoke-phone",
        device_name="Hot Reload Smoke Phone",
    )
    time.sleep(0.5)

    ok_code, ok_body = curl_status(device_id, token, host="127.0.0.1")
    bad_code, _ = curl_status(device_id, "definitely-wrong-token", host="127.0.0.1")

    result = {
        "pairing_hot_reload_accepted": ok_code == 200,
        "status_code": ok_code,
        "device_id": device_id,
        "invalid_token_401": bad_code == 401,
        "invalid_token_code": bad_code,
        "bridge_host": host,
        "bridge_port": port,
        "exe_restarted": False,
        "ok": ok_code == 200 and bad_code == 401,
    }
    if ok_body and isinstance(ok_body, str):
        try:
            parsed = json.loads(ok_body)
            result["mobile_api_version"] = parsed.get("mobile_api_version")
        except json.JSONDecodeError:
            pass

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["ok"]:
        print("Pairing hot-reload accepted: YES")
        return 0
    print("Pairing hot-reload accepted: NO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
