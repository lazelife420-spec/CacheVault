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
    from cache_vault.core import models, storage as S
    from cache_vault.core.models import Clip
    from cache_vault.ui.clip_context import clip_menu_items
    import tkinter as tk

    # 1. Setup temporary workspace env
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_menu_cleanup_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    # 2. Initialize database
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    
    # 3. Add a mock clip
    c = vault.capture("Test text clip for context menu verification.")
    
    # 4. Instantiate CacheVaultApp
    app = CacheVaultApp(vault=vault)
    app.update()
    app.update_idletasks()
    
    # 5. Verify Context Menu items structure (contains cascades)
    last_safe_name = vault.safes.default_safe().name
    items = clip_menu_items(c, last_safe_name=last_safe_name)
    keys = [i.key for i in items]
    print(f"Context menu keys: {keys}")
    
    # Assert structural keys exist (primary, copy_clean, organize, proof, advanced, danger)
    for k in ("primary", "copy_clean", "organize", "proof", "advanced", "danger"):
        assert k in keys, f"Required structural key '{k}' missing from context menu!"
        
    print("  [OK] Context menu structural keys verified.")

    # 6. Open Settings Hub and verify advanced category labels
    app._open_settings()
    app.update()
    
    # Find Settings window
    settings_win = None
    for child in app.winfo_children():
        name = str(type(child))
        if "SettingsHub" in name or "SettingsDialog" in name:
            settings_win = child
            break
            
    assert settings_win is not None, "Settings window was not opened!"
    print(f"Found Settings window instance: {type(settings_win)}")
    
    # Verify labels based on the settings type opened
    if "SettingsHub" in str(type(settings_win)):
        # Inspect SettingsHub sidebar buttons
        sidebar_buttons = [w for w in settings_win._category_list.winfo_children() if isinstance(w, ctk.CTkButton)]
        button_texts = [btn.cget("text") for btn in sidebar_buttons]
        
        # Verify the renamed advanced category labels exist
        assert any("Advanced: Vault Lock" in text for text in button_texts), "Advanced: Vault Lock label missing in sidebar"
        assert any("Advanced: History & Pruning" in text for text in button_texts), "Advanced: History & Pruning label missing in sidebar"
    else:
        # Inspect SettingsDialog section label widgets
        labels = [w for w in settings_win._scroll_body.winfo_children() if isinstance(w, ctk.CTkLabel)]
        label_texts = [lbl.cget("text") for lbl in labels]
        
        assert "Advanced: Vault Lock Security" in label_texts, "Advanced: Vault Lock Security section label missing"
        assert "Advanced: Pruning & History Limit" in label_texts, "Advanced: Pruning & History Limit section label missing"
        
    print("  [OK] Advanced settings section headings verified.")

    # 7. Capture visual QA screenshot of Settings
    out_img = ROOT / "visual_smoke" / "menu_settings_cleanup.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Capturing window screenshot to {out_img}...")
    settings_win.deiconify()
    settings_win.focus_force()
    settings_win.update()
    settings_win.update_idletasks()
    time.sleep(1.0)
    
    # Use capture_window to capture the Settings top-level window
    capture_script = ROOT / "scripts" / "capture_window.py"
    subprocess.run(
        [sys.executable, str(capture_script), "Settings", str(out_img)],
        check=True, cwd=ROOT
    )
    
    settings_win.destroy()
    app._quit()
    vault.storage.close()
    
    print("\nVerification report JSON:")
    report = {
        "ok": True,
        "context_menu_cascades_verified": True,
        "advanced_labels_verified": True,
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
    }
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
