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
from PIL import Image

def _png() -> bytes:
    from io import BytesIO
    img = Image.new("RGB", (48, 36), "#00D1B2")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

def main() -> int:
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.core import models
    from cache_vault.core.contextmenu import clip_menu_items

    # 1. Setup temporary workspace env
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_paste_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    # 2. Initialize database and add mock clips
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    c1 = vault.capture("Notepad text item for testing", source_app="Notepad.exe")
    c2 = vault.capture("https://github.com/lazelife420-spec/CacheVault", source_app="Chrome.exe")
    c3 = vault.capture_image(_png(), width=48, height=36, source_app="SnippingTool.exe")
    
    print("Populated clips in temp DB:")
    print(f"  Clip 1 (Text): {c1.id}")
    print(f"  Clip 2 (Link): {c2.id}")
    print(f"  Clip 3 (Image): {c3.id}")

    # 3. Verify core context menu labels logic
    text_items = clip_menu_items(c1)
    primary_text = next(i.children for i in text_items if i.key == "primary")
    copy_item = next((i for i in primary_text if i.key == "copy_again"), None)
    paste_item = next((i for i in primary_text if i.key == "paste_selected"), None)
    
    assert copy_item is not None and copy_item.label == "Copy Selected Item", "Stale/Incorrect Copy label"
    assert paste_item is not None and paste_item.label == "Paste Selected Item", "Paste action missing from menu"
    print("Core context menu labels verified successfully.")

    # 4. Instantiate CacheVaultApp
    app = CacheVaultApp(vault=vault)
    app.update()
    app.update_idletasks()
    
    # We select the first clip (c1)
    app._select_visible_clip_by_id(c1.id)
    app.update()
    
    print("Testing Paste Selected Action:")
    # Set mock external window HWND (e.g. 99999) to verify delivery pipeline
    app._last_external_hwnd = 99999
    
    # We will temporarily stub deliver_ctrl_v to avoid raising/failing during tests
    import cache_vault.ui.shell as shell_module
    original_deliver_ctrl_v = shell_module.deliver_ctrl_v
    
    called_hwnd = None
    def mock_deliver_ctrl_v(hwnd):
        nonlocal called_hwnd
        called_hwnd = hwnd
        # Return a successful PasteResult
        from cache_vault.core.paste_delivery import PasteResult
        return PasteResult(True, "ok", "Notepad")
        
    shell_module.deliver_ctrl_v = mock_deliver_ctrl_v
    
    try:
        # Trigger paste selected action (keyboard handler simulation)
        res = app._keyboard_paste_selected()
        assert res == "break", "Keyboard handler did not break event propagation"
        
        # Process pending after actions
        app.update()
        time.sleep(0.2)
        app.update()
        
        assert called_hwnd == 99999, f"deliver_ctrl_v called with {called_hwnd} instead of 99999"
        print("  [OK] Delivered paste event successfully to target HWND.")
        
        # Test focus safety: target HWND belongs to widget
        # hwnd_belongs_to_widget stub logic
        app._last_external_hwnd = app.winfo_id() # belongs to us
        called_hwnd = None
        
        app._keyboard_paste_selected()
        app.update()
        time.sleep(0.2)
        app.update()
        
        assert called_hwnd is None, "Paste delivered to Cache Vault window! Focus safety violation."
        print("  [OK] Focus safety verified: paste skipped when target is Cache Vault itself.")
        
        # Test fallback safely with feedback (hwnd is None/no target)
        app._last_external_hwnd = None
        called_hwnd = None
        
        app._keyboard_paste_selected()
        app.update()
        time.sleep(0.2)
        app.update()
        
        assert called_hwnd is None, "Paste delivered when no target window exists!"
        print("  [OK] Focus safety verified: fails safely when no target window is active.")

    finally:
        shell_module.deliver_ctrl_v = original_deliver_ctrl_v

    # 5. Capture visual QA screenshot
    out_img = ROOT / "visual_smoke" / "selected_item_paste_workflow.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Capturing window screenshot to {out_img}...")
    # Give UI a moment to render completely
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
        "context_menu_copy_label": copy_item.label,
        "context_menu_paste_label": paste_item.label,
        "delivery_verified": True,
        "focus_safety_verified": True,
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
    }
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
