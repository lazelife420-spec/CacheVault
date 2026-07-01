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
    from cache_vault.core.contextmenu import clip_menu_items

    # 1. Setup temporary workspace env
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_copy_safe_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    # 2. Initialize database and add mock clips
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    c1 = vault.capture("Copy to Safe target item", source_app="Notepad.exe")
    
    print("Populated clip in temp DB:")
    print(f"  Clip 1 (Text): {c1.id}")

    # Create custom Safe
    custom_safe = vault.create_safe("Personal Safe")
    print(f"  Created custom safe: {custom_safe.name} (id: {custom_safe.id})")

    # 3. Instantiate CacheVaultApp
    app = CacheVaultApp(vault=vault)
    app.update()
    app.update_idletasks()
    
    # 4. Verify context menu entries
    app._select_visible_clip_by_id(c1.id)
    app.update()
    
    # Context menu check (Default Safe is default "Last Safe" initially)
    last_safe_name = getattr(app, "_last_safe_name", None) or vault.safes.default_safe().name
    items = clip_menu_items(c1, last_safe_name=last_safe_name)
    organize_sec = next(i for i in items if i.key == "organize")
    keys = [item.key for item in organize_sec.children]
    
    assert "copy_to_safe" in keys, "copy_to_safe action missing from context menu"
    assert "copy_to_last_safe" in keys, "copy_to_last_safe action missing from context menu"
    assert "move_safe" in keys, "move_safe action missing from context menu"
    print("Context menu keys and default Safe tracking verified successfully.")

    # 5. Trigger Copy to Last Safe (copies c1 to Default Safe)
    original_count = len(vault.storage.list_clips())
    app._copy_to_last_safe(c1.id)
    app.update()
    
    new_clips = vault.storage.list_clips()
    assert len(new_clips) == original_count + 1, "Duplicate clip was not created!"
    
    # Find the new copied clip
    copied_clip = next(c for c in new_clips if c.id != c1.id)
    assert copied_clip.content == c1.content, "Copied content does not match original"
    assert copied_clip.safe_id == "default", "Copied clip safe destination is incorrect"
    print("  [OK] Successfully copied clip to Last Safe.")

    # 6. Verify focus safety: no selected item does not crash
    app._selected_clip_ids = set()
    try:
        app._copy_to_last_safe(None)
        app._copy_to_safe(None)
        print("  [OK] No selected item cases handled safely without crashes.")
    except Exception as e:
        print(f"  [FAIL] Crash on no selected item: {e}")
        return 1

    # 7. Capture visual QA screenshot
    out_img = ROOT / "visual_smoke" / "copy_to_safe_workflow.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Capturing window screenshot to {out_img}...")
    # Select the copied clip to show it in the UI
    app._select_visible_clip_by_id(copied_clip.id)
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
        "menu_presence_verified": True,
        "copy_delivery_verified": True,
        "safe_failure_handled": True,
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
    }
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
