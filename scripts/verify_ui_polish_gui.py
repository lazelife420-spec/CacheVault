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
    from PIL import Image
    from io import BytesIO

    # 1. Setup temporary workspace env
    tmp = Path(tempfile.mkdtemp(prefix="cv_qa_ui_polish_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
    
    # 2. Initialize database
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    
    # 3. Add text clip
    c_text = vault.capture("This is a simple plain text clip for date testing.", source_app="Notepad.exe")
    print(f"Added text clip: {c_text.id}")

    # 4. Add image clip with real PNG bytes
    img = Image.new("RGBA", (150, 150), (26, 188, 156, 255)) # beautiful proof-teal color
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    
    c_img = vault.storage.add_clip(Clip(
        content="beautiful_screenshot",
        content_hash=models.content_hash("beautiful_screenshot"),
        preview=models.make_preview("beautiful_screenshot"),
        classification=models.CLASS_IMAGE,
        content_type=models.CONTENT_IMAGE,
        safe_id="default"
    ))
    
    from cache_vault.core.image_assets import ClipAssetRecord, make_storage_name
    asset_rec = ClipAssetRecord(
        asset_id="asset-verify-img",
        clip_id=c_img.id,
        mime_type="image/png",
        file_ext="png",
        size_bytes=len(png_bytes),
        sha256="verify-image-sha",
        created_at=models.now_iso(),
        original_name="beautiful_screenshot.png",
        storage_name=make_storage_name(c_img.id, "png"),
        width=150,
        height=150
    )
    vault.storage.save_clip_asset(asset_rec, png_bytes)
    print(f"Added image clip with asset: {c_img.id}")

    # 5. Instantiate CacheVaultApp
    app = CacheVaultApp(vault=vault)
    
    # Switch to FILTER_ALL using navigate_screen
    app._navigate_screen(S.FILTER_ALL)
    
    # Wait for async batches to render
    for _ in range(50):
        app.update()
        time.sleep(0.01)
    
    # 6. Verify date timestamp on text row is human readable
    app._select_visible_clip_by_id(c_text.id)
    # Wait for selection / preview refresh
    for _ in range(10):
        app.update()
        time.sleep(0.01)
    
    # Get status label of the text row
    assert c_text.id in app._list._row_by_id, f"Text clip {c_text.id} not found in row map! Keys: {list(app._list._row_by_id.keys())}"
    first_row = app._list._row_by_id[c_text.id]
    labels = [w for w in first_row.winfo_children() if isinstance(w, ctk.CTkLabel)]
    # The last label is the status line
    status_label = labels[-1]
    status_text = status_label.cget("text")
    print(f"Formatted status line: {status_text}")
    assert "Added" in status_text and "Last used" in status_text, "Status label format is incorrect"
    assert ":" in status_text, "Time components missing in status line"
    print("  [OK] Human readable timestamp formatting verified.")

    # 7. Select image clip and verify preview details
    app._select_visible_clip_by_id(c_img.id)
    # Wait for selection / preview refresh
    for _ in range(20):
        app.update()
        time.sleep(0.01)
    
    # Verify metadata in PreviewPanel
    hint_text = app._preview._image_hint.cget("text")
    print(f"Image Preview Panel Metadata: {hint_text}")
    assert "beautiful_screenshot.png" in hint_text, "Original filename missing in preview metadata"
    assert "150x150" in hint_text, "Resolution dimensions missing in preview metadata"
    assert "image/png" in hint_text, "Mime type missing in preview metadata"
    print("  [OK] Preview panel image metadata formatting verified.")

    # 8. Capture visual QA screenshot
    out_img = ROOT / "visual_smoke" / "datestamp_image_viewer_polish.png"
    out_img.parent.mkdir(parents=True, exist_ok=True)
    
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
        "date_timestamp_formatted": True,
        "image_metadata_verified": True,
        "screenshot_saved": out_img.is_file() and out_img.stat().st_size > 10000,
    }
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
