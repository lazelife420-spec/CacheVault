"""Automated Runner for v0.1.5-rc2 Packaged GUI QA.

Pre-populates a temporary SQLite database, launches the packaged rc2
CacheVault.exe (extracted from the R2 artifact), waits for it to render,
captures a screenshot to verify visual layout, and cleanly shuts it down.

Usage:
    python scripts/verify_packaged_gui_run_rc2.py [path-to-CacheVault.exe]

Default exe path is the rc2 R2 install-smoke extraction:
    %TEMP%/cv_rc2_smoke/extracted/CacheVault.exe
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

R2_ZIP = "https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc2/CacheVault-v0.1.5-rc2-windows.zip"


def _default_exe() -> Path:
    return Path(tempfile.gettempdir()) / "cv_rc2_smoke" / "extracted" / "CacheVault.exe"


def _png() -> bytes:
    from io import BytesIO

    img = Image.new("RGB", (340, 250), "#00D1B2")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> int:
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.settings import Settings

    exe_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_exe()
    if not exe_path.is_file():
        print(f"ERROR: Packaged EXE not found at {exe_path}", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_packaged_rc2_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"

    db_dir = tmp / "CacheVault"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "cache_vault.db"

    print(f"Pre-populating database at {db_path}...")
    vault = Vault(storage=VaultStorage(db_path))
    c1 = vault.capture("Welcome to Cache Vault v0.1.5-rc2 packaged GUI QA!", source_app="Notepad.exe")
    c2 = vault.capture(R2_ZIP, source_app="Chrome.exe")
    c3 = vault.capture_image(_png(), width=340, height=250, source_app="SnippingTool.exe")
    default_safe = vault.safes.default_safe()
    clip_count = len(vault.storage.list_clips())
    print("Database populated:")
    print(f"  Default Safe: {default_safe.name} ({default_safe.id})")
    print(f"  Clip 1 (Text):  {c1.id}")
    print(f"  Clip 2 (Link):  {c2.id}")
    print(f"  Clip 3 (Image): {c3.id}")
    print(f"  Clip count in DB: {clip_count}")
    vault.close()

    # Skip the first-use onboarding guide so the main clip list is captured.
    s = Settings.load()
    s.first_use_guide_dismissed = True
    s.save()

    print(f"Launching packaged EXE: {exe_path}...")
    proc_env = os.environ.copy()
    proc_env["LOCALAPPDATA"] = str(tmp)
    proc_env["CACHE_VAULT_DISABLE_TRAY"] = "1"
    proc = subprocess.Popen([str(exe_path)], env=proc_env)

    render_wait = float(os.environ.get("CV_QA_RENDER_WAIT", "3.0"))
    time.sleep(render_wait)

    out_img = ROOT / "visual_smoke" / "v0.1.5_rc2_packaged_gui_qa.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    print(f"Capturing window screenshot to {out_img}...")
    capture_script = ROOT / "scripts" / "capture_window.py"
    cap_res = subprocess.run(
        [sys.executable, str(capture_script), "Cache Vault", str(out_img)],
        check=False,
        cwd=ROOT,
    )

    print("Terminating packaged app...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("\nVerification report JSON:")
    report = {
        "ok": cap_res.returncode == 0,
        "version": "0.1.5-rc2",
        "exe_path": str(exe_path),
        "db_path": str(db_path),
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
        "screenshot_path": str(out_img),
    }
    print(json.dumps(report, indent=2))
    return cap_res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
