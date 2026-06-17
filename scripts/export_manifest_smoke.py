"""Export manifest + SHA256SUMS smoke."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "visual_smoke" / "export_manifest_smoke.json"


def main() -> int:
    import os
    import tempfile

    from cache_vault.core.editable_copies import file_sha256, receipts_dir
    from cache_vault.core.exports import verify_zip_hashes
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    result = {"ok": False, "steps": {}}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        root = Path(tmp)
        vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())

        clip = vault.capture("smoke export text", source_app="smoke")
        result["steps"]["text_captured"] = clip is not None

        site = root / "site"
        (site / "css").mkdir(parents=True)
        html = site / "index.html"
        css = site / "css" / "site.css"
        css.write_text("h1{color:teal}", encoding="utf-8")
        html.write_text('<html><link href="css/site.css"></html>', encoding="utf-8")
        html_hash_before = file_sha256(html)
        css_hash_before = file_sha256(css)

        html_clip = vault.capture(str(html), source_app="smoke")
        vault.create_editable_copy(html_clip.id)
        Path(vault.latest_editable_copy(html_clip.id).copy_path).write_text(
            "<html><!-- edited --></html>", encoding="utf-8",
        )

        text_zip = root / "text-export.zip"
        html_zip = root / "html-export.zip"
        tr = vault.export_proof_zip([clip.id], str(text_zip))
        hr = vault.export_proof_zip([html_clip.id], str(html_zip), mode="html_bundle")

        result["steps"]["text_export_ok"] = tr.success
        result["steps"]["html_export_ok"] = hr.success
        result["steps"]["text_zip_exists"] = text_zip.is_file()
        result["steps"]["html_zip_exists"] = html_zip.is_file()

        with zipfile.ZipFile(text_zip) as zf:
            names = zf.namelist()
        result["steps"]["manifest_exists"] = "manifest.json" in names
        result["steps"]["sha256sums_exists"] = "SHA256SUMS.txt" in names

        ok, errors = verify_zip_hashes(text_zip)
        result["steps"]["hashes_validate"] = ok
        result["steps"]["hash_errors"] = errors

        result["steps"]["original_html_unchanged"] = file_sha256(html) == html_hash_before
        result["steps"]["original_css_unchanged"] = file_sha256(css) == css_hash_before

        receipts = list(receipts_dir().glob("export_zip_created-*.json"))
        result["steps"]["receipt_exists"] = bool(receipts)
        if receipts:
            result["receipt_path"] = str(receipts[-1])
        result["sample_zip"] = str(html_zip)
        result["manifest_in_zip"] = "manifest.json"
        result["sha256sums_in_zip"] = "SHA256SUMS.txt"

        result["ok"] = all(
            v for k, v in result["steps"].items()
            if isinstance(v, bool) and k != "hash_errors"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
