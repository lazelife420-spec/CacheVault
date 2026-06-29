"""
Stream 6 — Proof Manifest completeness tests.

Verifies that every bulk zip export contains:
  manifest.json        — machine-readable proof manifest
  SHA256SUMS.txt       — file integrity hashes
  stamped_receipt.txt  — human-readable per-clip SHA-256 proof document
  EXPORT_RECEIPT.txt   — export summary

And that:
  - manifest has correct clip_count (item_count field)
  - stamped_receipt.txt SHA-256 entries match each clip's content hash
  - stamped_receipt.txt export_id matches manifest export_id
"""

from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from cache_vault.core.exports import create_proof_zip
from cache_vault.core.models import Clip, new_id, now_iso


def _clip(content: str, classification: str = "plain") -> Clip:
    return Clip(
        id=new_id(),
        content=content,
        preview=content[:80],
        classification=classification,
        created_at=now_iso(),
        updated_at=now_iso(),
    )


def test_bulk_zip_contains_manifest_json(tmp_path):
    clips = [_clip("alpha"), _clip("beta"), _clip("gamma")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success, result.error

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "manifest.json" in names


def test_bulk_zip_manifest_has_clip_count(tmp_path):
    clips = [_clip("one"), _clip("two"), _clip("three")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        manifest = json.loads(zf.read("manifest.json"))

    assert manifest["item_count"] == 3


def test_bulk_zip_contains_sha256sums(tmp_path):
    clips = [_clip("hello"), _clip("world")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "SHA256SUMS.txt" in names


def test_bulk_zip_contains_stamped_receipt(tmp_path):
    """The key missing file — stamped_receipt.txt must be in every zip."""
    clips = [_clip("important note"), _clip("another fact")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success, result.error

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "stamped_receipt.txt" in names, (
        f"stamped_receipt.txt missing from zip. Found: {sorted(names)}"
    )


def test_stamped_receipt_sha256_matches_clip_content(tmp_path):
    """Every clip's SHA-256 in stamped_receipt.txt must match actual content."""
    clips = [_clip("verify me carefully"), _clip("also verify this one")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        receipt_text = zf.read("stamped_receipt.txt").decode("utf-8")

    for clip in clips:
        expected_sha = hashlib.sha256(clip.content.encode("utf-8")).hexdigest()
        assert expected_sha in receipt_text, (
            f"SHA-256 for clip {clip.id} not found in stamped_receipt.txt"
        )


def test_stamped_receipt_export_id_matches_manifest(tmp_path):
    """Export ID in stamped_receipt.txt must match manifest.json."""
    clips = [_clip("consistency check")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        receipt_text = zf.read("stamped_receipt.txt").decode("utf-8")

    export_id = manifest["export_id"]
    assert export_id in receipt_text, (
        f"Export ID '{export_id}' not found in stamped_receipt.txt"
    )


def test_stamped_receipt_includes_collection_name(tmp_path):
    """If a collection name is given, it must appear in stamped_receipt.txt."""
    clips = [_clip("work thing"), _clip("work other thing")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest, collection_name="Work Research")
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        receipt_text = zf.read("stamped_receipt.txt").decode("utf-8")

    assert "Work Research" in receipt_text


def test_single_clip_zip_also_has_stamped_receipt(tmp_path):
    """Single-clip exports must also include stamped_receipt.txt."""
    clips = [_clip("solo clip")]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert "stamped_receipt.txt" in names


def test_stamped_receipt_contains_all_clip_ids(tmp_path):
    """Every clip ID must appear in stamped_receipt.txt."""
    clips = [_clip(f"clip content {i}") for i in range(5)]
    dest = tmp_path / "export.zip"
    result = create_proof_zip(clips, dest)
    assert result.success

    with zipfile.ZipFile(dest) as zf:
        receipt_text = zf.read("stamped_receipt.txt").decode("utf-8")

    for clip in clips:
        assert clip.id in receipt_text, f"Clip ID {clip.id} missing from stamped_receipt.txt"
