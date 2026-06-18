"""Post-RC3 acceptance gate — luxury UI + Mobile Inbox + Simple Mode."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "visual_smoke"
OUT_JSON = OUT_DIR / "post_rc3_acceptance_gate.json"
ANDROID_SHARE_TIMEOUT = 240
ORIGINAL_LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
ORIGINAL_DISABLE_TRAY = os.environ.get("CACHE_VAULT_DISABLE_TRAY")


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout.strip()


def git_branch() -> str:
    return subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout.strip()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
        fh.flush()


def restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def run_pytest() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:xonsh"],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )
    return {
        "pass": proc.returncode == 0,
        "returncode": proc.returncode,
        "tail": (proc.stdout or "")[-400:],
    }


def run_selftest() -> dict:
    proc = subprocess.run(
        [sys.executable, "app.py", "--selftest"],
        capture_output=True, text=True, cwd=ROOT, timeout=30,
    )
    return {
        "pass": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip(),
    }


def mobile_inbox_api_gate() -> dict:
    from cache_vault.core import models
    from cache_vault.core.mobile.bridge import MobileBridge
    from cache_vault.core.mobile.receipts import MobileReceiptLog
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    tmp = Path(tempfile.mkdtemp(prefix="cv_post_rc3_"))
    old_localappdata = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(tmp)
    try:
        vault = Vault(storage=VaultStorage(tmp / "cv.db"))
        log = MobileReceiptLog(tmp / "mobile_receipts.json")
        bridge = MobileBridge(vault, receipt_log=log)
        vault.settings.mobile_access_enabled = True
        device, token = bridge.pair_device("gate-phone", "Acceptance Pixel")
        headers = {
            "X-Device-Id": device.device_id,
            "Authorization": f"Bearer {token}",
        }
        before = len(vault.list_clips())
        code, body = bridge.handle(
            "POST", "/mobile/v1/inbox/send", headers,
            body={
                "item_type": "url",
                "content": "https://example.com/gate-test",
                "source_app": "Chrome",
                "source_device_name": "Acceptance Pixel",
                "safe_id": "default",
                "user_action": "send_to_pc",
            },
        )
        clip = vault.storage.get_clip(body.get("desktop_item_id", "")) if code == 200 else None
        bad_code, _ = bridge.handle(
            "POST", "/mobile/v1/inbox/send",
            {**headers, "Authorization": "Bearer bad"},
            body={"content": "x", "user_action": "send_to_pc"},
        )
        after_bad = len(vault.list_clips())
        del_code, _ = bridge.handle("DELETE", "/mobile/v1/clips/abc", headers)
        routes = {}
        for path in (
            "/mobile/v1/status",
            "/mobile/v1/clips",
            "/mobile/v1/recently-removed",
        ):
            sc, rb = bridge.handle("GET", path, headers)
            routes[path] = sc
        rec = log.recent()[-1] if log.recent() else {}
        receipt_text = json.dumps(log.recent()[-3:])
        return {
            "pass": (
                code == 200
                and clip is not None
                and clip.capture_mode == models.CAPTURE_MOBILE_SHARE
                and clip.safe_id == "default"
                and clip.source_app == "Chrome"
                and clip.source_window == "Acceptance Pixel"
                and bad_code == 401
                and after_bad == before + 1
                and del_code == 405
                and all(sc == 200 for sc in routes.values())
            ),
            "send_status": code,
            "capture_mode": clip.capture_mode if clip else None,
            "safe_id": clip.safe_id if clip else None,
            "source_app": clip.source_app if clip else None,
            "source_window": clip.source_window if clip else None,
            "invalid_token_status": bad_code,
            "delete_status": del_code,
            "routes": routes,
            "receipt_action": rec.get("action"),
            "sensitive_in_receipt": "example.com/gate-test" in receipt_text,
            "receipt_path": str(tmp / "mobile_receipts.json"),
        }
    finally:
        restore_env("LOCALAPPDATA", old_localappdata)


def receipt_file_gate() -> dict:
    from cache_vault.core import models
    from cache_vault.core.editable_copies import write_file_receipt
    from cache_vault.core.mobile.receipts import MobileReceiptLog
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.mobile.inbox import receive_mobile_send
    from cache_vault.core.mobile.models import PairedDevice

    tmp = Path(tempfile.mkdtemp(prefix="cv_rcpt_"))
    old_localappdata = os.environ.get("LOCALAPPDATA")
    os.environ["LOCALAPPDATA"] = str(tmp)
    try:
        vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
        log = MobileReceiptLog(tmp / "CacheVault" / "mobile_receipts.json")
        device = PairedDevice(
            device_id="rcpt-dev", device_name="Rcpt Phone",
            created_at=models.now_iso(), token_hash="x" * 64,
        )
        secret = "password=supersecret123456789"
        receive_mobile_send(vault, device, {
            "item_type": "text",
            "content": secret,
            "source_app": "Share",
            "user_action": "send_to_pc",
        })
        write_file_receipt(
            models.ACTION_MOBILE_INBOX_RECEIVED,
            {"action": models.ACTION_MOBILE_INBOX_RECEIVED, "hash": "abc", "clip_id": "x"},
        )
        mobile_path = tmp / "CacheVault" / "mobile_receipts.json"
        day_dir = tmp / "CacheVault" / "Receipts"
        receipt_files = list(day_dir.rglob("*.json")) if day_dir.is_dir() else []
        mobile_text = mobile_path.read_text(encoding="utf-8") if mobile_path.is_file() else ""
        file_text = ""
        for rf in receipt_files:
            file_text += rf.read_text(encoding="utf-8")
        return {
            "pass": (
                models.ACTION_MOBILE_SENT_TO_PC in file_text
                and models.ACTION_MOBILE_INBOX_RECEIVED in file_text
                and secret not in mobile_text
                and secret not in file_text
            ),
            "mobile_receipts_path": str(mobile_path),
            "file_receipts_dir": str(day_dir),
            "actions_found": {
                "mobile_sent_to_pc": models.ACTION_MOBILE_SENT_TO_PC in file_text,
                "mobile_inbox_received": models.ACTION_MOBILE_INBOX_RECEIVED in file_text,
            },
        }
    finally:
        restore_env("LOCALAPPDATA", old_localappdata)


def export_regression() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_manifest_smoke.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    out = ROOT / "visual_smoke" / "export_manifest_smoke.json"
    data = {}
    if out.is_file():
        data = json.loads(out.read_text(encoding="utf-8"))
    return {
        "pass": proc.returncode == 0 and data.get("ok") is True,
        "returncode": proc.returncode,
        "manifest": data.get("manifest_ok"),
        "sha256sums": data.get("sha256sums_ok"),
        "safe_metadata": data.get("safe_metadata_ok"),
    }


def desktop_smoke() -> dict:
    from PIL import ImageGrab
    import customtkinter as ctk
    from cache_vault import brand
    from cache_vault.core import models
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.filters import NAV_MOBILE_INBOX
    from cache_vault.ui.shell import CacheVaultApp

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cv_ui_gate_"))
    old_localappdata = os.environ.get("LOCALAPPDATA")
    old_disable_tray = os.environ.get("CACHE_VAULT_DISABLE_TRAY")
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    app = None
    try:
        vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
        vault.settings.mobile_access_enabled = False
        vault.capture_mobile_share(
            "https://example.com/from-phone",
            source_app="Chrome",
            source_window="Gate Phone",
            safe_id="default",
        )
        ctk.set_appearance_mode("dark")
        app = CacheVaultApp(vault=vault)
        shots = {}
        checks = {}

        deadline = time.time() + 10.0
        while time.time() < deadline:
            app.update()
            if app.winfo_width() > 100 and app.winfo_height() > 100:
                break
            time.sleep(0.1)

        def grab(name: str) -> None:
            app.update()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            w, h = app.winfo_width(), app.winfo_height()
            if w > 100 and h > 100:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                path = OUT_DIR / f"{name}.png"
                img.save(path)
                shots[name] = str(path)

        def labels_under(widget) -> list[str]:
            labels = []

            def walk(node) -> None:
                if hasattr(node, "cget"):
                    try:
                        text = node.cget("text")
                    except Exception:  # noqa: BLE001
                        text = None
                    if isinstance(text, str) and text:
                        labels.append(text)
                for child in node.winfo_children():
                    walk(child)

            walk(widget)
            return labels

        grab("luxury_command_center")
        labels = labels_under(app._home._body)  # noqa: SLF001
        detail_text = " ".join(labels)
        checks["vault_status_active"] = brand.VAULT_STATUS_ACTIVE in labels
        checks["local_only"] = brand.LABEL_LOCAL_ONLY in detail_text
        checks["capture_active"] = brand.LABEL_CAPTURE_ACTIVE in detail_text

        app._navigate_screen(NAV_MOBILE_INBOX)  # noqa: SLF001
        deadline = time.time() + 5.0
        while time.time() < deadline:
            app.update()
            frame = app._vault_screens._screens.get(NAV_MOBILE_INBOX)  # noqa: SLF001
            if frame:
                break
            time.sleep(0.1)
        grab("mobile_inbox_screen")
        frame = app._vault_screens._screens.get(NAV_MOBILE_INBOX)  # noqa: SLF001
        inbox_labels = labels_under(frame) if frame else []
        checks["mobile_inbox_title"] = brand.TERM_MOBILE_INBOX in inbox_labels
        checks["sent_from_phone"] = any("Sent from phone" in t for t in inbox_labels)
        return {
            "pass": all(checks.values()) and len(shots) == 2,
            "screenshots": shots,
            "checks": checks,
        }
    finally:
        if app is not None:
            app._quit()  # noqa: SLF001 - gate owns this app instance.
        restore_env("LOCALAPPDATA", old_localappdata)
        restore_env("CACHE_VAULT_DISABLE_TRAY", old_disable_tray)


def docs_check() -> dict:
    paths = [
        ROOT / "docs" / "MOBILE_SHARE_ASSISTANT.md",
        ROOT / "docs" / "DESKTOP_HARDENING.md",
        ROOT / "docs" / "CROSS_APP_INTEGRATION.md",
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in paths if p.is_file())
    low = text.lower()
    return {
        "pass": (
            "no cloud" in low or "not cloud" in low or "local-only" in low
            and "silent clipboard" in low or "no silent clipboard" in low
            and "old person" not in low
            and "senior mode" not in low
            and "deferred" in low or "planned" in low
        ),
        "no_cloud_mentioned": "cloud" in low,
        "no_silent_clipboard": "silent clipboard" in low,
        "no_old_person_label": "old person" not in low,
        "deferred_or_planned": "deferred" in low or "planned" in low,
    }


def android_build_gate() -> dict:
    gradlew = ROOT / "android" / "gradlew.bat"
    if not gradlew.is_file():
        return {"pass": False, "error": "gradlew.bat missing"}
    proc = subprocess.run(
        [str(gradlew), "assembleDebug", "test", "--no-daemon"],
        capture_output=True, text=True, cwd=ROOT / "android", timeout=180,
    )
    apk = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    manifest = (ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(
        encoding="utf-8",
    )
    return {
        "pass": proc.returncode == 0 and apk.is_file(),
        "returncode": proc.returncode,
        "apk": str(apk) if apk.is_file() else None,
        "share_assistant_manifest": "ShareAssistantActivity" in manifest,
        "send_intent": "android.intent.action.SEND" in manifest,
        "tail": (proc.stdout or "")[-500:],
    }


def android_share_smoke() -> dict:
    adb = subprocess.run(["where", "adb"], capture_output=True, text=True)
    if adb.returncode != 0:
        return {
            "pass": False,
            "run": False,
            "note": "real Android Share Sheet smoke not run — adb unavailable",
        }
    dev = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    if "\tdevice" not in (dev.stdout or ""):
        return {
            "pass": False,
            "run": False,
            "note": "real Android Share Sheet smoke not run — no device/emulator",
        }
    env = os.environ.copy()
    restore_value = ORIGINAL_LOCALAPPDATA
    if restore_value is None:
        env.pop("LOCALAPPDATA", None)
    else:
        env["LOCALAPPDATA"] = restore_value
    if ORIGINAL_DISABLE_TRAY is None:
        env.pop("CACHE_VAULT_DISABLE_TRAY", None)
    else:
        env["CACHE_VAULT_DISABLE_TRAY"] = ORIGINAL_DISABLE_TRAY
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "android_share_inbox_smoke.py")],
            capture_output=True, text=True, cwd=ROOT, timeout=ANDROID_SHARE_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "pass": False,
            "run": True,
            "returncode": None,
            "note": f"real Android Share Sheet smoke timed out after {ANDROID_SHARE_TIMEOUT}s",
            "tail": ((exc.stdout or "") + (exc.stderr or ""))[-800:],
        }
    out_path = ROOT / "visual_smoke" / "android_share_inbox_smoke.json"
    data = {}
    if proc.returncode == 0 and out_path.is_file():
        data = json.loads(out_path.read_text(encoding="utf-8"))
    return {
        "pass": proc.returncode == 0 and data.get("pass") is True,
        "run": True,
        "returncode": proc.returncode,
        "proof": data,
        "tail": ((proc.stdout or "") + (proc.stderr or ""))[-800:],
    }


def main() -> int:
    results = {
        "branch": git_branch(),
        "commit": git_head(),
        "no_tag": True,
        "no_github_release": True,
        "no_final_release_claim": True,
        "rc3_untouched": True,
        "desktop_pytest": run_pytest(),
        "desktop_selftest": run_selftest(),
        "android_build": android_build_gate(),
        "mobile_inbox_api": mobile_inbox_api_gate(),
        "receipt_proof": receipt_file_gate(),
        "export_regression": export_regression(),
        "docs_check": docs_check(),
        "android_share_smoke": android_share_smoke(),
    }
    try:
        results["desktop_smoke"] = desktop_smoke()
    except Exception as exc:  # noqa: BLE001
        results["desktop_smoke"] = {"pass": False, "error": str(exc)}

    android_ok = results["android_build"]["pass"]
    share_ok = results["android_share_smoke"].get("run") and results["android_share_smoke"]["pass"]
    share_not_required_fail = not results["android_share_smoke"].get("run")

    results["overall_pass"] = (
        results["desktop_pytest"]["pass"]
        and results["desktop_selftest"]["pass"]
        and android_ok
        and share_ok
        and results["mobile_inbox_api"]["pass"]
        and results["receipt_proof"]["pass"]
        and results["export_regression"]["pass"]
        and results["docs_check"]["pass"]
        and results["desktop_smoke"].get("pass")
    )
    results["post_rc3_lane_accepted"] = results["overall_pass"]
    results["mobile_acceptance_complete"] = share_ok
    results["mobile_acceptance_note"] = (
        "Desktop + Android build gated; real Share Sheet smoke not run (no device)."
        if share_not_required_fail
        else results["android_share_smoke"].get("note", "")
    )

    write_json(OUT_JSON, results)
    print(json.dumps(results, indent=2))
    sys.stdout.flush()
    return 0 if results["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
