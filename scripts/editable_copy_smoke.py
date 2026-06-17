"""Editable copy smoke — verifies originals stay immutable."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "visual_smoke" / "editable_copy_smoke.json"


def main() -> int:
    import os
    import tempfile

    from cache_vault.core.editable_copies import file_sha256
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    result = {"ok": False, "steps": {}}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        original = Path(tmp) / "smoke.txt"
        original.write_text("before", encoding="utf-8")
        before_hash = file_sha256(original)

        vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
        clip = vault.capture(str(original), source_app="smoke")
        result["steps"]["captured"] = clip is not None
        if clip is None:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1

        rec = vault.create_editable_copy(clip.id)
        result["steps"]["copy_created"] = rec is not None
        if rec is None:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1

        Path(rec.copy_path).write_text("after edit", encoding="utf-8")
        saved = vault.save_editable_revision(clip.id)
        result["steps"]["revision_saved"] = saved is not None and saved.revision == 2
        result["steps"]["original_unchanged"] = (
            file_sha256(original) == before_hash
            and original.read_text(encoding="utf-8") == "before"
        )
        result["ok"] = all(result["steps"].values())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
