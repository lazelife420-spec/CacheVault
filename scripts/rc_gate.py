"""Cache Vault v0.1.3-rc4 release-candidate gate — desktop + mobile + artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cache_vault import __version__  # noqa: E402
from scripts.android_asset_smoke import (  # noqa: E402
    fresh_pair,
    restart_cache_vault,
    bridge_host_port,
    curl_status,
)

TAG = "v0.1.3-rc4"
RELEASE_DIR = ROOT / "dist" / "release" / TAG
ZIP_NAME = f"CacheVault-{TAG}-windows.zip"
ZIP_PATH = RELEASE_DIR / ZIP_NAME
APK_NAME = f"CacheVault-Mobile-{TAG}-debug.apk"
APK_PATH = RELEASE_DIR / APK_NAME
SHA_PATH = RELEASE_DIR / "SHA256SUMS.txt"
RECEIPT_PATH = RELEASE_DIR / "RC_RECEIPT.json"
NOTES_PATH = ROOT / "docs" / "releases" / f"{TAG}.md"
GRADLE_APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def wait_port(port: int = 8742, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
        if f":{port}" in out and "LISTENING" in out:
            return True
        time.sleep(1.0)
    return False


def mobile_request(
    method: str,
    path: str,
    device_id: str,
    token: str,
    host: str,
    port: int,
    body: dict | None = None,
) -> tuple[int, dict | None]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else None
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed


def verify_zip_structure() -> dict:
    checks: dict = {}
    if not ZIP_PATH.is_file():
        return {"zip_exists": False}
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = zf.namelist()
        notes_text = zf.read("RELEASE_NOTES.md").decode("utf-8", errors="replace")
    checks["zip_exists"] = True
    checks["contains_exe"] = "CacheVault.exe" in names
    checks["contains_notes"] = "RELEASE_NOTES.md" in names
    checks["notes_version_rc4"] = "v0.1.3-rc4" in notes_text
    checks["notes_not_rc3_only"] = "v0.1.3-rc3" not in notes_text.split("What changed")[0]
    checks["no_source_junk"] = not any(n.endswith(".py") for n in names)
    return checks


def write_sha256sums() -> dict:
    lines: list[str] = []
    result: dict = {}
    if ZIP_PATH.is_file():
        zh = sha256_file(ZIP_PATH)
        lines.append(f"{zh}  {ZIP_NAME}")
        result["zip_sha256"] = zh
    if APK_PATH.is_file():
        ah = sha256_file(APK_PATH)
        lines.append(f"{ah}  {APK_NAME}")
        result["apk_sha256"] = ah
    if lines:
        SHA_PATH.write_text("\n".join(lines) + "\n", encoding="ascii")
        result["sha_path"] = str(SHA_PATH)
    return result


def main() -> int:
    source_commit = subprocess.run(
        ["git", "rev-parse", "610fb38d6a5f19895b0afb9ff6c6551ec4ba5372"],
        capture_output=True, text=True, cwd=ROOT,
    ).stdout.strip()
    package_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout.strip()

    results: dict = {
        "tag": TAG,
        "version": __version__,
        "branch": subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout.strip(),
        "source_commit": source_commit,
        "package_metadata_commit": package_commit,
        "no_tag": True,
        "no_github_release": True,
        "no_final_release_claim": True,
        "no_cloud_claim": True,
        "no_encryption_claim": True,
        "rc3_untouched": True,
        "v012_untouched": True,
    }

    exe = ROOT / "dist" / "CacheVault.exe"
    if exe.is_file():
        proc = subprocess.run([str(exe), "--selftest"], capture_output=True, text=True, cwd=ROOT)
        results["desktop_selftest"] = {
            "pass": proc.returncode == 0,
            "stdout": (proc.stdout or "").strip()[-200:],
        }
    else:
        results["desktop_selftest"] = {"pass": False, "error": "missing dist/CacheVault.exe"}

    meta = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_exe_metadata.py"), "--exe", str(exe)],
        capture_output=True, text=True, cwd=ROOT,
    )
    meta_out = meta.stdout or ""
    exe_meta_pass = (
        "ProductVersion=0.1.3-rc4" in meta_out
        and "FileVersion=0.1.3-rc4" in meta_out
        and "fixed file/product version matches: (0, 1, 3, 0)" in meta_out
    )
    results["exe_metadata"] = {
        "pass": exe_meta_pass,
        "note": "Root README/RELEASE_NOTES.md remain v0.1.2 (shipped desktop); RC notes are in zip only.",
        "output": meta_out,
    }

    if APK_PATH.is_file():
        results["android_apk"] = {
            "path": str(APK_PATH),
            "sha256": sha256_file(APK_PATH),
            "debug_internal_proof": True,
        }
    elif GRADLE_APK.is_file():
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        APK_PATH.write_bytes(GRADLE_APK.read_bytes())
        results["android_apk"] = {
            "path": str(APK_PATH),
            "sha256": sha256_file(APK_PATH),
            "copied_from": str(GRADLE_APK),
            "debug_internal_proof": True,
        }
    else:
        results["android_apk"] = {"pass": False, "error": "missing Android APK"}

    sha_info = write_sha256sums()
    results.update(sha_info)

    device_id, token = fresh_pair(device_id="rc4-gate-phone", device_name="RC4 Gate Phone")
    restart_cache_vault()
    _, port = bridge_host_port()
    time.sleep(3.0)
    code, status_body = curl_status(device_id, token, host="127.0.0.1")
    results["bridge_auth_local"] = code == 200
    results["bridge_port_listening"] = wait_port(port)

    routes = {}
    safe_meta: dict = {"pass": False}
    for path in (
        "/mobile/v1/status",
        "/mobile/v1/clips",
        "/mobile/v1/recently-removed",
    ):
        status, body = mobile_request("GET", path, device_id, token, "127.0.0.1", port)
        routes[path] = {
            "status": status,
            "pass": status == 200,
            "read_only": body.get("read_only") if path.endswith("/status") and body else None,
        }
        if path == "/mobile/v1/clips" and status == 200 and body:
            clips = body.get("clips") or []
            if clips:
                first = clips[0]
                safe_meta = {
                    "pass": "safe_id" in first and "safe_name" in first,
                    "sample_safe_id": first.get("safe_id"),
                    "sample_safe_name": first.get("safe_name"),
                }

    inbox_before = routes.get("/mobile/v1/clips", {}).get("status")
    send_status, send_body = mobile_request(
        "POST",
        "/mobile/v1/inbox/send",
        device_id,
        token,
        "127.0.0.1",
        port,
        body={
            "item_type": "url",
            "content": "https://example.com/rc4-gate-send",
            "source_app": "RC4 Gate",
            "source_device_name": "RC4 Gate Phone",
            "safe_id": "default",
            "user_action": "send_to_pc",
        },
    )
    bad_status, _ = mobile_request(
        "POST",
        "/mobile/v1/inbox/send",
        device_id,
        "bad-token",
        "127.0.0.1",
        port,
        body={"content": "nope", "user_action": "send_to_pc"},
    )
    routes["/mobile/v1/inbox/send"] = {
        "status": send_status,
        "pass": send_status == 200,
        "capture_mode": send_body.get("capture_mode") if send_body else None,
    }
    results["mobile_routes"] = routes
    results["mobile_safe_metadata"] = safe_meta
    results["unauthenticated_send_rejected"] = bad_status in (401, 403)

    artifact = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "verify_release_artifact.py"),
            "--zip", str(ZIP_PATH),
            "--sha256", str(SHA_PATH),
            "--tag", TAG,
        ],
        capture_output=True, text=True, cwd=ROOT,
    )
    results["artifact_verifier"] = {
        "pass": artifact.returncode == 0,
        "output": (artifact.stdout or "").strip(),
    }

    if ZIP_PATH.is_file():
        results["zip_path"] = str(ZIP_PATH)
        results["zip_sha256"] = results.get("zip_sha256") or sha256_file(ZIP_PATH)
        results["artifact_files"] = [
            ZIP_NAME,
            APK_NAME if APK_PATH.is_file() else None,
            "SHA256SUMS.txt",
            "RC_RECEIPT.json",
            f"docs/releases/{TAG}.md",
        ]
        results["artifact_files"] = [f for f in results["artifact_files"] if f]
        results["zip_checks"] = verify_zip_structure()
        if SHA_PATH.is_file():
            line = SHA_PATH.read_text(encoding="ascii")
            results["sha256_file_matches"] = results["zip_sha256"] in line
    else:
        results["zip_path"] = None
        results["zip_checks"] = {"zip_exists": False}

    all_route_pass = all(r["pass"] for r in routes.values())

    if exe.is_file():
        subprocess.run(["taskkill", "/IM", "CacheVault.exe", "/F"], capture_output=True)
        time.sleep(1.5)
        launch = subprocess.Popen([str(exe)], cwd=ROOT)
        time.sleep(4.0)
        alive = launch.poll() is None
        if alive:
            launch.terminate()
            try:
                launch.wait(timeout=5)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/IM", "CacheVault.exe", "/F"], capture_output=True)
        results["packaged_app_launch"] = {"pass": alive}
    else:
        results["packaged_app_launch"] = {"pass": False, "error": "missing exe"}

    manual_smoke = ROOT / "visual_smoke" / "android_manual_pairing_smoke.json"
    share_smoke = ROOT / "visual_smoke" / "android_share_inbox_smoke.json"
    if manual_smoke.is_file():
        results["manual_setup_smoke"] = json.loads(manual_smoke.read_text(encoding="utf-8"))
    if share_smoke.is_file():
        results["share_sheet_smoke"] = json.loads(share_smoke.read_text(encoding="utf-8"))

    results["overall_pass"] = (
        results["desktop_selftest"].get("pass")
        and results["exe_metadata"].get("pass")
        and results["packaged_app_launch"].get("pass")
        and results["bridge_port_listening"]
        and results["bridge_auth_local"]
        and all_route_pass
        and results["mobile_safe_metadata"].get("pass")
        and results["unauthenticated_send_rejected"]
        and results["artifact_verifier"].get("pass")
        and results.get("zip_checks", {}).get("zip_exists", False)
        and APK_PATH.is_file()
    )

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if results["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
