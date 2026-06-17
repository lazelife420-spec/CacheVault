"""UI smoke: capture image clip preview thumbnail."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path

import customtkinter as ctk
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "visual_smoke"


def _png() -> bytes:
    img = Image.new("RGB", (48, 36), "#00D1B2")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> int:
    import os
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.preview import PreviewPanel

    tmp = Path(tempfile.mkdtemp(prefix="cv_ui_smoke_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    vault = Vault(storage=VaultStorage(tmp / "CacheVault" / "cache_vault.db"))
    clip = vault.capture_image(_png(), width=48, height=36)
    assert clip is not None

    root = ctk.CTk()
    root.geometry("400x600")
    root.title("Cache Vault")

    storage = vault.storage

    def asset_meta(clip_id: str):
        rec = storage.get_asset_record(clip_id)
        if not rec:
            return None
        return {"sha256": rec.sha256, "size_bytes": rec.size_bytes,
                "width": rec.width, "height": rec.height}

    panel = PreviewPanel(root, actions={
        "load_asset": storage.load_clip_asset_bytes,
        "asset_meta": asset_meta,
        "copy_again": lambda _id: None,
        "save_asset_as": lambda _id: None,
        "open_asset_folder": lambda _id: None,
    })
    panel.pack(fill="both", expand=True)
    panel.show(clip)
    root.update()
    root.update_idletasks()
    time.sleep(1.5)

    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", str(ROOT / "scripts" / "capture_window.py"),
         "Cache Vault", str(OUT / "sv_image_preview.png")],
        check=True, cwd=ROOT,
    )
    has_image = panel._image_ref is not None
    meta = panel._meta.cget("text")
    print("preview_image:", has_image)
    print("meta_has_sha:", "Asset SHA256" in meta)
    vault.storage.close()
    root.destroy()
    return 0 if has_image and "Asset SHA256" in meta else 1


if __name__ == "__main__":
    raise SystemExit(main())
