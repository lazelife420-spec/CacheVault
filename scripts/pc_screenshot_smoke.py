"""PC screenshot smoke — verifies the full local asset pipeline without a phone."""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _png(w: int = 16, h: int = 12, color: str = "teal") -> bytes:
    img = Image.new("RGB", (w, h), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> int:
    import os
    from cache_vault.core import export, models
    from cache_vault.core.storage import FILTER_SCREENSHOTS, VaultStorage
    from cache_vault.core.vault import Vault

    tmp = Path(tempfile.mkdtemp(prefix="cv_pc_smoke_"))
    os.environ["LOCALAPPDATA"] = str(tmp)
    db = tmp / "CacheVault" / "cache_vault.db"
    storage = VaultStorage(db)
    vault = Vault(storage=storage, settings=__import__(
        "cache_vault.core.settings", fromlist=["Settings"]).Settings.load())

    before = vault.counts().get(FILTER_SCREENSHOTS, 0)
    png = _png(32, 24)
    clip = vault.capture_image(png, width=32, height=24, source_app="SnippingTool.exe")
    assert clip is not None, "capture_image failed"
    after = vault.counts().get(FILTER_SCREENSHOTS, 0)
    assert after == before + 1, f"screenshot count {before} -> {after}"

    asset_path = tmp / "CacheVault" / "assets" / f"{clip.id}.png"
    assert asset_path.is_file(), "PNG not on disk"

    rec = storage.get_asset_record(clip.id)
    assert rec is not None
    assert rec.sha256 == models.bytes_hash(png)
    assert rec.width == 32 and rec.height == 24

    loaded = storage.load_clip_asset_bytes(clip.id)
    assert loaded and loaded[0] == png

    again = vault.copied_again_image(clip.id)
    assert again == png

    zpath = tmp / "export.zip"
    export.export_zip(
        [clip], zpath,
        load_asset_bytes=lambda cid: storage.load_clip_asset_bytes(cid)[0],
    )
    with zipfile.ZipFile(zpath) as zf:
        assets = [n for n in zf.namelist() if n.startswith("assets/") and n.endswith(".png")]
        assert assets, "export zip missing assets/*.png"
        assert zf.read(assets[0]) == png

    kinds = {e["event_type"] for e in vault.events.recent() if e.get("clip_id") == clip.id}
    assert models.EVENT_CAPTURED in kinds
    assert models.EVENT_ASSET_PERSISTED in kinds

    storage.close()
    print(json.dumps({
        "ok": True,
        "clip_id": clip.id,
        "screenshots": after,
        "asset_path": str(asset_path),
        "sha256": rec.sha256[:16],
        "dimensions": f"{rec.width}x{rec.height}",
        "export_assets": assets,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
