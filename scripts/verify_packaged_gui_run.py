"""Automated Runner for Packaged GUI QA.

This script pre-populates a temporary SQLite database, launches the packaged
CacheVault.exe, waits for it to render, captures a screenshot to verify visual
layout (image preview card, dates, list), and cleanly shuts down the process.
"""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

# Ensure ROOT is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def _png() -> bytes:
    from io import BytesIO
    img = Image.new("RGB", (340, 250), "#00D1B2")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

def main() -> int:
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core import models

    # 1. Setup temporary workspace env for the packaged app
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_packaged_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    db_dir = tmp / "CacheVault"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "cache_vault.db"

    # 2. Pre-populate database with test clips
    print(f"Pre-populating database at {db_path}...")
    vault = Vault(storage=VaultStorage(db_path))
    
    # Text clip
    c1 = vault.capture("Welcome to Cache Vault v0.1.5-rc1 packaged GUI QA!", source_app="Notepad.exe")
    # Link clip
    c2 = vault.capture("https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip", source_app="Chrome.exe")
    # Image clip (to test preview card, dimensions, file size, original name)
    c3 = vault.capture_image(_png(), width=340, height=250, source_app="SnippingTool.exe")
    
    # Get defaults
    default_safe = vault.safes.default_safe()
    print("Database populated:")
    print(f"  Default Safe: {default_safe.name} ({default_safe.id})")
    print(f"  Clip 1 (Text): {c1.id}")
    print(f"  Clip 2 (Link): {c2.id}")
    print(f"  Clip 3 (Image): {c3.id}")
    
    vault.close()

    # 3. Launch the packaged CacheVault.exe
    exe_path = Path(r"C:\Users\KickA\AppData\Local\Temp\cache_vault_smoke_v015_rc1\extracted\CacheVault.exe")
    if not exe_path.is_file():
        print(f"ERROR: Packaged EXE not found at {exe_path}", file=sys.stderr)
        return 1

    print(f"Launching packaged EXE: {exe_path}...")
    # Run with custom LOCALAPPDATA env set
    proc_env = os.environ.copy()
    proc_env["LOCALAPPDATA"] = str(tmp)
    proc_env["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    proc = subprocess.Popen([str(exe_path)], env=proc_env)
    
    # 4. Wait for window to load and render
    time.sleep(3.0)

    # 5. Capture visual QA screenshot
    out_img = ROOT / "visual_smoke" / "v0.1.5_rc1_packaged_gui_qa.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Capturing window screenshot to {out_img}...")
    capture_script = ROOT / "scripts" / "capture_window.py"
    cap_res = subprocess.run(
        [sys.executable, str(capture_script), "Cache Vault", str(out_img)],
        check=False, cwd=ROOT
    )
    
    # 6. Clean up process
    print("Terminating packaged app...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    # 7. Print verification report
    print("\nVerification report JSON:")
    report = {
        "ok": cap_res.returncode == 0,
        "exe_path": str(exe_path),
        "db_path": str(db_path),
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
        "screenshot_path": str(out_img),
    }
    print(json.dumps(report, indent=2))
    return cap_res.returncode

if __name__ == "__main__":
    raise SystemExit(main())
