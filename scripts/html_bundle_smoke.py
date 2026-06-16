"""HTML bundle smoke — editable copy with local assets."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "visual_smoke" / "html_bundle_smoke.json"


def main() -> int:
    import os

    from cache_vault.core.editable_copies import file_sha256, receipts_dir
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    result = {"ok": False, "steps": {}}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        root = Path(tmp) / "site"
        (root / "css").mkdir(parents=True)
        (root / "img").mkdir()
        html = root / "demo.html"
        css = root / "css" / "style.css"
        img = root / "img" / "logo.png"
        css.write_text("h1 { color: navy; }", encoding="utf-8")
        img.write_bytes(b"\x89PNG")
        html.write_text(
            '<html><head><link href="css/style.css" rel="stylesheet"></head>'
            '<body><img src="img/logo.png"><p>smoke</p></body></html>',
            encoding="utf-8",
        )
        before = {
            "html": file_sha256(html),
            "css": file_sha256(css),
            "img": file_sha256(img),
        }

        vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
        clip = vault.capture(str(html), source_app="smoke")
        result["steps"]["captured"] = clip is not None
        if clip is None:
            _write(result)
            return 1

        rec = vault.create_editable_copy(clip.id)
        result["steps"]["copy_created"] = rec is not None
        result["steps"]["original_html_unchanged"] = file_sha256(html) == before["html"]
        result["steps"]["original_css_unchanged"] = file_sha256(css) == before["css"]
        result["steps"]["original_img_unchanged"] = file_sha256(img) == before["img"]
        if rec is None:
            _write(result)
            return 1

        copy_html = Path(rec.copy_path)
        result["steps"]["copied_html_exists"] = copy_html.is_file()
        result["steps"]["copied_css_exists"] = (Path(rec.bundle_dir) / "css" / "style.css").is_file()
        result["steps"]["copied_img_exists"] = (Path(rec.bundle_dir) / "img" / "logo.png").is_file()

        old_hash = rec.copy_hash
        copy_html.write_text(copy_html.read_text(encoding="utf-8") + "<!-- edit -->", encoding="utf-8")
        saved = vault.save_editable_revision(clip.id)
        result["steps"]["revision_saved"] = saved is not None
        result["steps"]["copied_hash_changed"] = saved is not None and saved.copy_hash != old_hash

        receipts = list(receipts_dir().glob("editable_html_copy_created-*.json"))
        result["steps"]["receipt_exists"] = bool(receipts)
        if receipts:
            result["receipt_path"] = str(receipts[0])

        result["ok"] = all(v for k, v in result["steps"].items() if isinstance(v, bool))

    _write(result)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def _write(result: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
