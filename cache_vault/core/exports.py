"""Proof-backed exports — manifest, SHA256SUMS, receipts, staged copies."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import socket
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .. import __version__, brand
from . import models, pathutil
from .editable_copies import (
    KIND_HTML_BUNDLE,
    EditableCopyRecord,
    file_sha256,
    load_bundle_meta,
    receipts_dir,
    write_file_receipt,
)
from .models import Clip


@dataclass
class ProofExportResult:
    export_id: str
    zip_path: Path | None = None
    folder_path: Path | None = None
    manifest: dict = field(default_factory=dict)
    success: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    file_count: int = 0
    receipt_count: int = 0


def export_zip_basename(ts: str | None = None) -> str:
    stamp = ts or datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    stamp = stamp.replace(":", "").replace("T", "-")[:19]
    return f"CacheVault-export-{stamp}.zip"


def _machine_label() -> str:
    host = os.environ.get("COMPUTERNAME") or socket.gethostname() or "local"
    user = getpass.getuser()
    return f"{host}/{user}"


def _safe_arcname(base: str, name: str) -> str:
    clean = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .") or "file"
    return f"{base}/{clean}"


def _hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = file_sha256(path)
    return out


def _write_sha256sums(root: Path, hashes: dict[str, str]) -> None:
    lines = [
        f"{digest}  {rel}"
        for rel, digest in sorted(hashes.items())
        if rel != "SHA256SUMS.txt"
    ]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_file_receipts(stage: Path, clip_ids: set[str]) -> int:
    count = 0
    dest = stage / "receipts"
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted(receipts_dir().glob("*.json")):
        try:
            body = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cid = body.get("clip_id") or ""
        if clip_ids and cid and cid not in clip_ids:
            continue
        shutil.copy2(src, dest / src.name)
        count += 1
    return count


def _copy_event_receipts(
    stage: Path,
    clip_ids: set[str],
    events: list[dict],
) -> int:
    dest = stage / "receipts"
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for ev in events:
        cid = ev.get("clip_id")
        if clip_ids and cid and cid not in clip_ids:
            continue
        name = f"event-{ev.get('id', count)}.json"
        (dest / name).write_text(json.dumps(ev, indent=2), encoding="utf-8")
        count += 1
    return count


def _stage_clip(
    clip: Clip,
    stage: Path,
    *,
    mode: str,
    editable: EditableCopyRecord | None,
    include_original_file: bool,
    load_asset_bytes: Callable[[str], bytes | None] | None,
    warnings: list[str],
) -> dict:
    """Stage one clip; return manifest item entry."""
    entry: dict = {
        "clip_id": clip.id,
        "type": clip.classification,
        "content_type": clip.content_type,
        "export_source": "clip_content",
        "files": [],
    }
    items_dir = stage / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    text_path = items_dir / f"{clip.id}.txt"
    text_path.write_text(clip.content or "", encoding="utf-8")
    entry["files"].append(text_path.relative_to(stage).as_posix())

    if clip.content_type == models.CONTENT_IMAGE and load_asset_bytes:
        data = load_asset_bytes(clip.id)
        if data:
            img = items_dir / f"{clip.id}.png"
            img.write_bytes(data)
            entry["files"].append(img.relative_to(stage).as_posix())
        else:
            warnings.append(f"Image asset missing for clip {clip.id[:8]}")

    if editable and editable.kind == KIND_HTML_BUNDLE and mode in ("auto", "html_bundle"):
        bundle_src = Path(editable.bundle_dir)
        if bundle_src.is_dir():
            bundle_dest = stage / "html_bundles" / clip.id
            if bundle_dest.exists():
                shutil.rmtree(bundle_dest)
            shutil.copytree(bundle_src, bundle_dest)
            meta = load_bundle_meta(bundle_src)
            entry["export_source"] = "html_bundle_copy"
            entry["html_bundle"] = {
                "revision": editable.revision,
                "bundle_dir_in_zip": f"html_bundles/{clip.id}",
                "copied_asset_count": len(meta.copied_assets) if meta else 0,
                "missing_asset_count": len(meta.missing_assets) if meta else 0,
                "remote_assets_skipped": len(meta.remote_assets) if meta else 0,
                "original_path_metadata": editable.original_path,
            }
            for p in sorted(bundle_dest.rglob("*")):
                if p.is_file():
                    entry["files"].append(p.relative_to(stage).as_posix())
            return entry
        warnings.append(f"HTML bundle folder missing for clip {clip.id[:8]}")

    if editable and mode in ("auto", "editable_copy"):
        copy_src = Path(editable.copy_path)
        if copy_src.is_file():
            ed_dir = stage / "editable_copies" / clip.id
            ed_dir.mkdir(parents=True, exist_ok=True)
            dest = ed_dir / copy_src.name
            shutil.copy2(copy_src, dest)
            entry["export_source"] = "editable_copy"
            entry["editable_copy"] = {
                "revision": editable.revision,
                "original_path_metadata": editable.original_path,
                "copy_path_in_zip": dest.relative_to(stage).as_posix(),
            }
            entry["files"].append(dest.relative_to(stage).as_posix())
            return entry
        warnings.append(f"Editable copy file missing for clip {clip.id[:8]}")

    if include_original_file and pathutil.is_local_file(clip.content):
        src = Path(pathutil.clean_path(clip.content))
        orig_dir = stage / "items" / "original"
        orig_dir.mkdir(parents=True, exist_ok=True)
        dest = orig_dir / src.name
        if src.is_file():
            shutil.copy2(src, dest)
            entry["export_source"] = "original_file_copy"
            entry["original_path_metadata"] = str(src)
            entry["files"].append(dest.relative_to(stage).as_posix())
        else:
            warnings.append(f"Original file missing: {clip.content[:80]}")
            entry["unsupported"] = "original_file_missing"
    elif pathutil.is_local_path(clip.content) and not pathutil.target_exists(clip.content):
        warnings.append(f"Original file missing: {clip.content[:80]}")
        entry["original_path_metadata"] = pathutil.clean_path(clip.content)
        entry["reference_only"] = True
        entry["unsupported"] = "original_file_missing"
    elif pathutil.is_local_path(clip.content):
        entry["original_path_metadata"] = pathutil.clean_path(clip.content)
        entry["reference_only"] = True

    return entry


def create_proof_zip(
    clips: list[Clip],
    dest_zip: str | os.PathLike,
    *,
    mode: str = "auto",
    include_original_files: bool = False,
    include_receipts: bool = True,
    collection_name: str | None = None,
    get_editable_copy: Callable[[str], EditableCopyRecord | None] | None = None,
    events_for_clips: Callable[[list[str]], list[dict]] | None = None,
    load_asset_bytes: Callable[[str], bytes | None] | None = None,
    export_ts: str | None = None,
) -> ProofExportResult:
    """Build a proof-backed export zip. Never mutates originals on disk."""
    export_id = models.new_id()
    export_ts = export_ts or models.now_iso()
    warnings: list[str] = []
    clip_ids = {c.id for c in clips}
    get_editable_copy = get_editable_copy or (lambda _cid: None)
    events_for_clips = events_for_clips or (lambda _ids: [])

    dest = Path(dest_zip)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="cv-export-") as tmp:
            stage = Path(tmp)
            item_entries: list[dict] = []
            for clip in clips:
                editable = get_editable_copy(clip.id)
                item_entries.append(_stage_clip(
                    clip, stage, mode=mode, editable=editable,
                    include_original_file=include_original_files,
                    load_asset_bytes=load_asset_bytes,
                    warnings=warnings,
                ))

            receipt_count = 0
            if include_receipts:
                receipt_count += _copy_event_receipts(
                    stage, clip_ids, events_for_clips(list(clip_ids)),
                )
                receipt_count += _copy_file_receipts(stage, clip_ids)

            readme = (
                f"{brand.PRODUCT_NAME} — Proof Export\n"
                f"Export ID: {export_id}\n"
                f"Exported: {export_ts}\n"
                f"Version: {__version__}\n\n"
                f"This package contains exported items, receipts, manifest.json, "
                f"and SHA256SUMS.txt.\n"
                f"{brand.RECEIPT_NOTE}\n"
            )
            (stage / "EXPORT_RECEIPT.txt").write_text(readme, encoding="utf-8")

            content_hashes = _hash_tree(stage)
            file_list = sorted(content_hashes.keys()) + ["manifest.json", "SHA256SUMS.txt"]
            manifest = {
                "document_type": "cache_vault_proof_export",
                "export_id": export_id,
                "export_timestamp": export_ts,
                "app_version": __version__,
                "machine_label": _machine_label(),
                "product": brand.PRODUCT_NAME,
                "studio": brand.STUDIO_NAME,
                "export_type": "multi_clip" if len(clips) > 1 else "single_item",
                "collection": collection_name,
                "item_count": len(clips),
                "item_ids": [c.id for c in clips],
                "item_types": [c.classification for c in clips],
                "items": item_entries,
                "file_list": file_list,
                "hashes": content_hashes,
                "receipt_count": receipt_count,
                "receipts_included": include_receipts,
                "sha256sums_included": True,
                "manifest_included": True,
                "warnings": warnings,
                "unsupported_items": [
                    e.get("unsupported") for e in item_entries if e.get("unsupported")
                ],
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8",
            )

            all_hashes = _hash_tree(stage)
            _write_sha256sums(stage, all_hashes)
            all_hashes = _hash_tree(stage)

            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(stage).as_posix())

            receipt_payload = {
                "action": "export_zip_created",
                "export_id": export_id,
                "clip_id": clips[0].id if len(clips) == 1 else None,
                "clip_ids": [c.id for c in clips],
                "timestamp": export_ts,
                "output_zip_path": str(dest),
                "manifest_path_in_zip": "manifest.json",
                "sha256sums_included": True,
                "receipt_count": receipt_count,
                "file_count": len(all_hashes),
                "success": True,
                "app_version": __version__,
                "warnings": warnings[:20],
            }
            write_file_receipt("export_zip_created", receipt_payload)

            return ProofExportResult(
                export_id=export_id,
                zip_path=dest,
                manifest=manifest,
                success=True,
                warnings=warnings,
                file_count=len(all_hashes),
                receipt_count=receipt_count,
            )
    except OSError as exc:
        fail_payload = {
            "action": "export_zip_created",
            "export_id": export_id,
            "timestamp": export_ts,
            "success": False,
            "error": str(exc)[:200],
            "app_version": __version__,
        }
        write_file_receipt("export_zip_created", fail_payload)
        return ProofExportResult(
            export_id=export_id,
            success=False,
            error=str(exc),
            warnings=warnings,
        )


def verify_zip_hashes(zip_path: Path) -> tuple[bool, list[str]]:
    """Verify SHA256SUMS.txt inside an export zip matches file contents."""
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        if "SHA256SUMS.txt" not in zf.namelist():
            return False, ["SHA256SUMS.txt missing"]
        sums: dict[str, str] = {}
        for line in zf.read("SHA256SUMS.txt").decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            digest, _, rel = line.partition("  ")
            sums[rel.strip()] = digest.strip()
        for rel, expected in sums.items():
            if rel == "SHA256SUMS.txt":
                continue
            if rel not in zf.namelist():
                errors.append(f"missing file: {rel}")
                continue
            data = zf.read(rel)
            import hashlib
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                errors.append(f"hash mismatch: {rel}")
    return not errors, errors
