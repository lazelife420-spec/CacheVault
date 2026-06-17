"""Proof-pack export smoke — manifest, SHA256SUMS, receipts, Safes metadata."""
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
    from cache_vault.core.exports import verify_export_pack, verify_zip_hashes
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    result: dict = {"ok": False, "steps": {}, "manifest_summary": {}}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        root = Path(tmp)
        vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())

        work = vault.create_safe("Smoke Work Safe")
        clip = vault.capture_manual(
            "smoke export text", safe_id=work.id, source_app="smoke",
        )
        result["steps"]["text_captured"] = clip is not None

        note = root / "note.txt"
        note.write_text("original note", encoding="utf-8")
        note_before = file_sha256(note)
        file_clip = vault.capture(str(note), source_app="smoke")
        ed = vault.create_editable_copy(file_clip.id)
        assert ed is not None
        Path(ed.copy_path).write_text("edited smoke copy", encoding="utf-8")

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

        text_zip = root / "text-export.zip"
        edit_zip = root / "editable-export.zip"
        html_zip = root / "html-export.zip"

        tr = vault.export_proof_zip([clip.id], str(text_zip))
        er = vault.export_proof_zip([file_clip.id], str(edit_zip), mode="editable_copy")
        hr = vault.export_proof_zip([html_clip.id], str(html_zip), mode="html_bundle")

        result["steps"]["text_export_ok"] = tr.success
        result["steps"]["editable_export_ok"] = er.success
        result["steps"]["html_export_ok"] = hr.success
        result["steps"]["text_zip_exists"] = text_zip.is_file()
        result["sample_zip"] = str(text_zip)

        with zipfile.ZipFile(text_zip) as zf:
            names = zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))
        result["steps"]["manifest_exists"] = "manifest.json" in names
        result["steps"]["sha256sums_exists"] = "SHA256SUMS.txt" in names
        result["steps"]["readme_exists"] = "README.txt" in names
        result["steps"]["receipts_in_zip"] = any(n.startswith("receipts/") for n in names)

        ok, errors = verify_zip_hashes(text_zip)
        result["steps"]["hashes_validate"] = ok
        result["steps"]["hash_errors"] = errors

        ok_pack, pack_errors = verify_export_pack(text_zip)
        result["steps"]["proof_pack_validates"] = ok_pack
        result["steps"]["proof_pack_errors"] = pack_errors

        item = manifest["items"][0]
        result["manifest_summary"] = {
            "safe_id": item.get("safe_id"),
            "safe_name": item.get("safe_name"),
            "capture_mode": item.get("capture_mode"),
            "auto_saved": item.get("auto_saved"),
            "receipts_included": manifest.get("receipts_included"),
            "sha256sums_included": manifest.get("sha256sums_included"),
        }
        result["steps"]["manifest_has_safe_metadata"] = (
            item.get("safe_id") == work.id
            and item.get("capture_mode") == "manual_save_hotkey"
        )

        result["steps"]["original_note_unchanged"] = file_sha256(note) == note_before
        result["steps"]["original_html_unchanged"] = file_sha256(html) == html_hash_before
        result["steps"]["original_css_unchanged"] = file_sha256(css) == css_hash_before

        receipts = list(receipts_dir().glob("export_zip_created-*.json"))
        result["steps"]["export_receipt_exists"] = bool(receipts)
        if receipts:
            result["receipt_path"] = str(receipts[-1])
            body = json.loads(receipts[-1].read_text(encoding="utf-8"))
            result["steps"]["export_receipt_has_manifest_flags"] = (
                body.get("manifest_included") and body.get("sha256sums_included")
            )

        result["ok"] = all(
            v for k, v in result["steps"].items()
            if isinstance(v, bool) and k not in ("hash_errors",)
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
