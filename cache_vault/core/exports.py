"""Proof-backed exports — manifest, SHA256SUMS, receipts, staged copies.

Core-only module: no UI imports. Desktop UI calls :func:`create_export_pack`.
"""

from __future__ import annotations

import getpass
import hashlib
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

# Public aliases for modular proof-pack services.
hash_file = file_sha256
create_export_pack = None  # defined after create_proof_zip
verify_export_pack = None  # defined after verify_zip_hashes


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


def _write_stamped_receipt(
    stage: Path,
    *,
    export_id: str,
    export_ts: str,
    clips: "list",
    collection_name: "str | None" = None,
    machine_label: str = "",
) -> None:
    """Write stamped_receipt.txt — the human-readable Proof Manifest companion.

    This is the document the user can read, print, or share as evidence
    that these specific clips were exported at this specific time from this machine.
    It lists every clip with its SHA-256 content hash so the receipt is verifiable.
    """
    lines: list[str] = [
        "━" * 60,
        f"  {brand.PRODUCT_NAME} — STAMPED RECEIPT",
        "━" * 60,
        f"  Export ID   : {export_id}",
        f"  Timestamp   : {export_ts}",
        f"  Machine     : {machine_label}",
        f"  Clip count  : {len(clips)}",
    ]
    if collection_name:
        lines.append(f"  Collection  : {collection_name}")
    lines += [
        "━" * 60,
        "",
        "  CLIP MANIFEST",
        "",
    ]
    for i, clip in enumerate(clips, 1):
        content_bytes = (clip.content or "").encode("utf-8")
        sha = hashlib.sha256(content_bytes).hexdigest()
        clip_type = getattr(clip, "classification", "unknown")
        lines += [
            f"  [{i:03d}]  id     : {clip.id}",
            f"         type   : {clip_type}",
            f"         sha256 : {sha}",
            "",
        ]
    lines += [
        "━" * 60,
        f"  {brand.RECEIPT_NOTE}",
        "━" * 60,
        "",
    ]
    (stage / "stamped_receipt.txt").write_text("\n".join(lines), encoding="utf-8")




def _item_file_hashes(stage: Path, rel_paths: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in rel_paths:
        path = stage / rel
        if path.is_file():
            out[rel] = file_sha256(path)
    return out


def validate_manifest(manifest: dict) -> list[str]:
    """Return validation errors for a proof-pack manifest (empty = valid)."""
    errors: list[str] = []
    if manifest.get("document_type") != "cache_vault_proof_export":
        errors.append("invalid or missing document_type")
    for key in ("export_id", "export_timestamp", "app_version", "items"):
        if not manifest.get(key):
            errors.append(f"missing top-level field: {key}")
    if manifest.get("manifest_included") is not True:
        errors.append("manifest_included should be true")
    if manifest.get("sha256sums_included") is not True:
        errors.append("sha256sums_included should be true")
    for i, item in enumerate(manifest.get("items") or []):
        prefix = f"items[{i}]"
        for key in (
            "clip_id", "type", "safe_id", "safe_name",
            "capture_mode", "auto_saved", "files",
        ):
            if key not in item:
                errors.append(f"{prefix} missing {key}")
    return errors


def write_export_receipt(payload: dict) -> Path:
    """Write a file receipt for proof-pack export (metadata only)."""
    action = payload.get("action", "export_zip_created")
    return write_file_receipt(action, payload)


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


def _attach_receipt_references(stage: Path, items: list[dict]) -> None:
    dest = stage / "receipts"
    if not dest.is_dir():
        for item in items:
            item.setdefault("receipt_references", [])
        return
    by_clip: dict[str, list[str]] = {item["clip_id"]: [] for item in items}
    for path in sorted(dest.glob("*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cid = body.get("clip_id") or ""
        if cid in by_clip:
            by_clip[cid].append(f"receipts/{path.name}")
        elif body.get("action") == "export_zip_created":
            for item in items:
                by_clip[item["clip_id"]].append(f"receipts/{path.name}")
    for item in items:
        item["receipt_references"] = sorted(set(by_clip.get(item["clip_id"], [])))


def _base_item_entry(clip: Clip) -> dict:
    return {
        "clip_id": clip.id,
        "item_id": clip.id,
        "type": clip.classification,
        "item_type": clip.classification,
        "content_type": clip.content_type,
        "source_app": clip.source_app,
        "source_window": clip.source_window,
        "source_app_version": None,
        "content_hash": clip.content_hash,
        "export_source": "clip_content",
        "export_used": "clip_content",
        "used_editable_copy": False,
        "safe_id": clip.safe_id,
        "safe_name": clip.safe_name,
        "capture_mode": clip.capture_mode,
        "auto_saved": clip.capture_mode == models.CAPTURE_AUTO,
        "files": [],
        "file_hashes": {},
        "receipt_references": [],
        "warnings": [],
    }


def build_manifest_item(
    clip: Clip,
    stage: Path,
    *,
    mode: str,
    editable: EditableCopyRecord | None,
    include_original_file: bool,
    load_asset_bytes: Callable[[str], bytes | None] | None,
    warnings: list[str],
) -> dict:
    """Stage one clip and return a manifest item entry."""
    return _stage_clip(
        clip, stage, mode=mode, editable=editable,
        include_original_file=include_original_file,
        load_asset_bytes=load_asset_bytes, warnings=warnings,
    )


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
    entry = _base_item_entry(clip)
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
            msg = f"Image asset missing for clip {clip.id[:8]}"
            warnings.append(msg)
            entry["warnings"].append(msg)

    if editable and editable.kind == KIND_HTML_BUNDLE and mode in ("auto", "html_bundle"):
        bundle_src = Path(editable.bundle_dir)
        if bundle_src.is_dir():
            bundle_dest = stage / "html_bundles" / clip.id
            if bundle_dest.exists():
                shutil.rmtree(bundle_dest)
            shutil.copytree(bundle_src, bundle_dest)
            meta = load_bundle_meta(bundle_src)
            html_rel = None
            copy_name = Path(editable.copy_path).name
            for p in bundle_dest.rglob("*"):
                if p.is_file() and p.name == copy_name:
                    html_rel = p.relative_to(stage).as_posix()
                    break
            entry["export_source"] = "html_bundle_copy"
            entry["export_used"] = "html_bundle_copy"
            entry["used_editable_copy"] = True
            entry["html_bundle"] = {
                "original_clip_id": clip.id,
                "revision": editable.revision,
                "bundle_dir": f"html_bundles/{clip.id}",
                "bundle_dir_in_zip": f"html_bundles/{clip.id}",
                "exported_html_path": html_rel,
                "copied_asset_count": len(meta.copied_assets) if meta else 0,
                "missing_asset_count": len(meta.missing_assets) if meta else 0,
                "remote_assets_skipped": len(meta.remote_assets) if meta else 0,
                "original_path_metadata": editable.original_path,
                "original_assets_not_fetched": True,
                "original_assets_not_mutated": True,
            }
            for p in sorted(bundle_dest.rglob("*")):
                if p.is_file():
                    entry["files"].append(p.relative_to(stage).as_posix())
            entry["file_hashes"] = _item_file_hashes(stage, entry["files"])
            return entry
        msg = f"HTML bundle folder missing for clip {clip.id[:8]}"
        warnings.append(msg)
        entry["warnings"].append(msg)

    if editable and mode in ("auto", "editable_copy"):
        copy_src = Path(editable.copy_path)
        if copy_src.is_file():
            ed_dir = stage / "editable_copies" / clip.id
            ed_dir.mkdir(parents=True, exist_ok=True)
            dest = ed_dir / copy_src.name
            shutil.copy2(copy_src, dest)
            copy_rel = dest.relative_to(stage).as_posix()
            entry["export_source"] = "editable_copy"
            entry["export_used"] = "editable_copy"
            entry["used_editable_copy"] = True
            entry["editable_copy"] = {
                "original_clip_id": clip.id,
                "revision": editable.revision,
                "original_path_metadata": editable.original_path,
                "copy_path_in_zip": copy_rel,
                "export_used": "editable_copy",
                "used_editable_copy": True,
            }
            entry["files"].append(copy_rel)
            entry["file_hashes"] = _item_file_hashes(stage, entry["files"])
            return entry
        msg = f"Editable copy file missing for clip {clip.id[:8]}"
        warnings.append(msg)
        entry["warnings"].append(msg)

    if include_original_file and pathutil.is_local_file(clip.content):
        src = Path(pathutil.clean_path(clip.content))
        orig_dir = stage / "items" / "original"
        orig_dir.mkdir(parents=True, exist_ok=True)
        dest = orig_dir / src.name
        if src.is_file():
            shutil.copy2(src, dest)
            entry["export_source"] = "original_file_copy"
            entry["export_used"] = "original_file_copy"
            entry["original_path_metadata"] = str(src)
            entry["files"].append(dest.relative_to(stage).as_posix())
        else:
            msg = f"Original file missing: {clip.content[:80]}"
            warnings.append(msg)
            entry["warnings"].append(msg)
            entry["unsupported"] = "original_file_missing"
    elif pathutil.is_local_path(clip.content) and not pathutil.target_exists(clip.content):
        msg = f"Original file missing: {clip.content[:80]}"
        warnings.append(msg)
        entry["warnings"].append(msg)
        entry["original_path_metadata"] = pathutil.clean_path(clip.content)
        entry["reference_only"] = True
        entry["unsupported"] = "original_file_missing"
    elif pathutil.is_local_path(clip.content):
        entry["original_path_metadata"] = pathutil.clean_path(clip.content)
        entry["reference_only"] = True

    entry["file_hashes"] = _item_file_hashes(stage, entry["files"])
    return entry


def _write_readme(stage: Path, export_id: str, export_ts: str) -> None:
    text = (
        f"{brand.PRODUCT_NAME} — Proof Export Package\n"
        f"Export ID: {export_id}\n"
        f"Exported: {export_ts}\n"
        f"App version: {__version__}\n\n"
        "Contents:\n"
        "  manifest.json        — export manifest (items, Safes, capture modes)\n"
        "  SHA256SUMS.txt       — SHA-256 hashes of staged files (not the zip itself)\n"
        "  EXPORT_RECEIPT.txt   — human-readable export summary\n"
        "  stamped_receipt.txt  — per-clip SHA-256 manifest (verifiable proof document)\n"
        "  receipts/            — stamped event + file receipts (metadata only)\n"
        "  items/               — clip text/image payloads\n"
        "  editable_copies/     — managed editable copies (when applicable)\n"
        "  html_bundles/        — copied HTML bundles (when applicable)\n\n"

        f"{brand.RECEIPT_NOTE}\n"
        "Safes are local vault sections — not encrypted containers.\n"
    )
    (stage / "README.txt").write_text(text, encoding="utf-8")


def _finalize_manifest_hashes(stage: Path, manifest: dict) -> dict[str, str]:
    """Write SHA256SUMS.txt and sync manifest hashes/file_list."""
    staged = {
        k: v for k, v in _hash_tree(stage).items() if k != "SHA256SUMS.txt"
    }
    _write_sha256sums(stage, staged)
    final = {
        k: v for k, v in _hash_tree(stage).items() if k != "SHA256SUMS.txt"
    }
    manifest["file_list"] = sorted(final.keys())
    manifest["hashes"] = final
    (stage / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )
    _write_sha256sums(stage, {
        k: v for k, v in _hash_tree(stage).items() if k != "SHA256SUMS.txt"
    })
    return _hash_tree(stage)


def _safe_summary(clips: list[Clip]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for clip in clips:
        key = (clip.safe_id, clip.safe_name, clip.capture_mode)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "safe_id": clip.safe_id,
            "safe_name": clip.safe_name,
            "capture_mode": clip.capture_mode,
        })
    return out


def create_proof_zip(
    clips: list[Clip],
    dest_zip: str | os.PathLike,
    *,
    mode: str = "auto",
    include_original_files: bool = False,
    include_receipts: bool = True,
    collection_name: str | None = None,
    safe_id: str | None = None,
    safe_name: str | None = None,
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
                receipts_dir_path = stage / "receipts"
                receipts_dir_path.mkdir(parents=True, exist_ok=True)
                if not any(receipts_dir_path.iterdir()):
                    (receipts_dir_path / "README.txt").write_text(
                        "No matching receipts for exported clip ids.\n",
                        encoding="utf-8",
                    )

            _attach_receipt_references(stage, item_entries)

            readme = (
                f"{brand.PRODUCT_NAME} — Proof Export\n"
                f"Export ID: {export_id}\n"
                f"Exported: {export_ts}\n"
                f"Version: {__version__}\n\n"
                f"This package contains exported items, receipts, manifest.json, "
                f"SHA256SUMS.txt, and README.txt.\n"
                f"{brand.RECEIPT_NOTE}\n"
            )
            (stage / "EXPORT_RECEIPT.txt").write_text(readme, encoding="utf-8")
            _write_readme(stage, export_id, export_ts)
            _write_stamped_receipt(
                stage,
                export_id=export_id,
                export_ts=export_ts,
                clips=clips,
                collection_name=collection_name,
                machine_label=_machine_label(),
            )


            safes = _safe_summary(clips)
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
                "safe_id": safe_id or (clips[0].safe_id if len(clips) == 1 else None),
                "safe_name": safe_name or (clips[0].safe_name if len(clips) == 1 else None),
                "safes": safes,
                "item_count": len(clips),
                "item_ids": [c.id for c in clips],
                "item_types": [c.classification for c in clips],
                "items": item_entries,
                "file_list": [],
                "hashes": {},
                "receipt_count": receipt_count,
                "receipts_included": include_receipts,
                "sha256sums_included": True,
                "manifest_included": True,
                "warnings": warnings,
                "unsupported_items": [
                    e.get("unsupported") for e in item_entries if e.get("unsupported")
                ],
                "limitations": {
                    "export_by_safe": "deferred — schema supports safe_id/safes fields",
                    "encryption": "none — Safes are local sections, not encrypted vaults",
                    "remote_html_assets": "never fetched — copied local assets only",
                },
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8",
            )

            all_hashes = _finalize_manifest_hashes(stage, manifest)

            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(stage).as_posix())

            primary = clips[0]
            receipt_payload = {
                "action": "export_zip_created",
                "export_id": export_id,
                "clip_id": primary.id if len(clips) == 1 else None,
                "clip_ids": [c.id for c in clips],
                "timestamp": export_ts,
                "output_zip_path": str(dest),
                "manifest_path_in_zip": "manifest.json",
                "manifest_included": True,
                "sha256sums_included": True,
                "receipts_included": include_receipts,
                "sha256sums_path_in_zip": "SHA256SUMS.txt",
                "receipt_count": receipt_count,
                "file_count": len(all_hashes),
                "success": True,
                "app_version": __version__,
                "safe_id": primary.safe_id if len(clips) == 1 else None,
                "safe_name": primary.safe_name if len(clips) == 1 else None,
                "capture_mode": primary.capture_mode if len(clips) == 1 else None,
                "safes": safes,
                "warnings": warnings[:20],
            }
            write_export_receipt(receipt_payload)

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
            "manifest_included": False,
            "sha256sums_included": False,
            "receipts_included": include_receipts,
        }
        write_export_receipt(fail_payload)
        return ProofExportResult(
            export_id=export_id,
            success=False,
            error=str(exc),
            warnings=warnings,
        )


create_export_pack = create_proof_zip


def verify_zip_hashes(zip_path: Path | os.PathLike) -> tuple[bool, list[str]]:
    """Verify SHA256SUMS.txt inside an export zip matches file contents."""
    errors: list[str] = []
    zip_path = Path(zip_path)
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
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                errors.append(f"hash mismatch: {rel}")
        if "manifest.json" in zf.namelist() and "manifest.json" not in sums:
            errors.append("manifest.json missing from SHA256SUMS.txt")
    return not errors, errors


def verify_export_pack(zip_path: Path | os.PathLike) -> tuple[bool, list[str]]:
    """Verify proof-pack zip: SHA256SUMS + manifest structure."""
    errors: list[str] = []
    ok, hash_errors = verify_zip_hashes(zip_path)
    if not ok:
        errors.extend(hash_errors)
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for required in ("manifest.json", "SHA256SUMS.txt", "EXPORT_RECEIPT.txt"):
            if required not in names:
                errors.append(f"{required} missing from zip")
        manifest: dict | None = None
        if "manifest.json" in names:
            try:
                manifest = json.loads(zf.read("manifest.json"))
            except json.JSONDecodeError:
                errors.append("manifest.json is not valid JSON")
            else:
                errors.extend(validate_manifest(manifest))
        if manifest and manifest.get("receipts_included"):
            if not any(n.startswith("receipts/") for n in names):
                errors.append("receipts/ expected but missing from zip")
    return not errors, errors
