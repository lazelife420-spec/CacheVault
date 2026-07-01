import os
import sys
import tempfile
import time
import json
import subprocess
from pathlib import Path

# Ensure ROOT is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import customtkinter as ctk

def main() -> int:
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.core import models

    # 1. Setup temporary workspace env
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_do_not_save_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    # 2. Initialize database
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    
    # 3. Instantiate CacheVaultApp
    app = CacheVaultApp(vault=vault)
    app.update()
    app.update_idletasks()
    
    # 4. Verify initial OptionMenu text
    initial_status = app._control_strip._capture.get()
    assert initial_status in ("Capture: On", "Capture: Paused"), f"Unexpected initial status: {initial_status}"
    print(f"Initial option menu status verified: {initial_status}")

    # 5. Arm Do Not Save Next Copy
    app._ignore_next_copy()
    app.update()
    
    armed_status = app._control_strip._capture.get()
    assert armed_status == "Next copy will not be saved", f"Armed status incorrect: {armed_status}"
    print(f"Armed option menu status verified: {armed_status}")

    # 6. Simulate first clipboard copy (should be ignored)
    payload_ignored = {"text": "My super secret password", "source_app": "KeePass.exe"}
    app._ingest(payload_ignored)
    app.update()
    
    # Verify no clips in database
    clips_after_ignore = vault.storage.list_clips()
    assert len(clips_after_ignore) == 0, "Clipboard item was saved when it should have been ignored!"
    print("  [OK] First clipboard copy was successfully ignored (not saved).")

    # Verify OptionMenu status cleared back to normal
    cleared_status = app._control_strip._capture.get()
    assert cleared_status in ("Capture: On", "Capture: Paused"), f"Status did not clear: {cleared_status}"
    print(f"Option menu status cleared back to normal: {cleared_status}")

    # 7. Simulate second clipboard copy (should be saved normally)
    payload_saved = {"text": "Normal public research data", "source_app": "Chrome.exe"}
    app._ingest(payload_saved)
    app.update()
    
    clips_after_save = vault.storage.list_clips()
    assert len(clips_after_save) == 1, "Subsequent clipboard copy was not saved!"
    assert clips_after_save[0].content == "Normal public research data"
    print("  [OK] Second clipboard copy was successfully saved normally.")

    # 8. Capture visual QA screenshot
    out_img = ROOT / "visual_smoke" / "do_not_save_next_copy_workflow.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
    # Arm one more time to capture "Next copy will not be saved" state visually
    app._ignore_next_copy()
    app.update()
    
    print(f"Capturing window screenshot to {out_img}...")
    app.deiconify()
    app.focus_force()
    app.update()
    app.update_idletasks()
    time.sleep(1.0)
    
    capture_script = ROOT / "scripts" / "capture_window.py"
    subprocess.run(
        [sys.executable, str(capture_script), "Cache Vault", str(out_img)],
        check=True, cwd=ROOT
    )
    
    app._quit()
    vault.storage.close()
    
    print("\nVerification report JSON:")
    report = {
        "ok": True,
        "armed_status_verified": True,
        "first_copy_ignored": True,
        "second_copy_saved": True,
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
    }
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
