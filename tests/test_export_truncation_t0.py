"""Regression tests for DEF-001: Export Artifact Truncation fix.

Verifies that bulk folder and ZIP exports preserve full clip text content
and do not truncate clips to the short ~80 character preview string.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from cache_vault.core import models
from cache_vault.core.export import export_collection, export_zip
from cache_vault.core.models import Clip, make_preview


def test_export_collection_full_text_preserved():
    marker_start = "UNIQUE_EXPORT_START_MARKER_"
    marker_end = "_UNIQUE_EXPORT_END_MARKER"
    full_content = marker_start + ("X" * 1500) + marker_end
    preview = make_preview(full_content)

    clip = Clip(id="c_def001_1", content=full_content, preview=preview)

    tmp = Path(tempfile.mkdtemp(prefix="test_cv_t0_export_"))
    try:
        dest = export_collection([clip], tmp / "folder_export")
        txt_files = list((dest / "clips").glob("*.txt"))
        assert len(txt_files) == 1, "Expected exactly one text file in clips/"
        
        exported_text = txt_files[0].read_text(encoding="utf-8")
        assert len(exported_text) == len(full_content), (
            f"Exported text length ({len(exported_text)}) differs from full content ({len(full_content)})"
        )
        assert exported_text == full_content
        assert marker_end in exported_text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_zip_full_text_preserved():
    marker_start = "ZIP_EXPORT_START_MARKER_"
    marker_end = "_ZIP_EXPORT_END_MARKER"
    full_content = marker_start + ("Y" * 1200) + marker_end
    preview = make_preview(full_content)

    clip = Clip(id="c_def001_2", content=full_content, preview=preview)

    tmp = Path(tempfile.mkdtemp(prefix="test_cv_t0_zip_"))
    try:
        zip_path = export_zip([clip], tmp / "export.zip")
        assert zip_path.is_file()

        with zipfile.ZipFile(zip_path) as zf:
            clip_names = [n for n in zf.namelist() if n.startswith("clips/") and n.endswith(".txt")]
            assert len(clip_names) == 1
            exported_text = zf.read(clip_names[0]).decode("utf-8")

        assert len(exported_text) == len(full_content)
        assert exported_text == full_content
        assert marker_end in exported_text
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_preview_fallback_when_content_empty():
    preview = "fallback preview text"
    clip = Clip(id="c_def001_3", content="", preview=preview)

    tmp = Path(tempfile.mkdtemp(prefix="test_cv_t0_fallback_"))
    try:
        dest = export_collection([clip], tmp / "fallback_export")
        txt_files = list((dest / "clips").glob("*.txt"))
        assert len(txt_files) == 1
        exported_text = txt_files[0].read_text(encoding="utf-8")
        assert exported_text == preview
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_export_manifest_and_index_structure_unaffected():
    clip = Clip(id="c_def001_4", content="Hello World Test", preview="Hello World Test")
    tmp = Path(tempfile.mkdtemp(prefix="test_cv_t0_meta_"))
    try:
        dest = export_collection([clip], tmp / "meta_export", collection_name="Test Col")
        manifest_file = dest / "manifest.json"
        assert manifest_file.is_file()
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert data["collection"] == "Test Col"
        assert data["count"] == 1
        assert (dest / "index.html").is_file()
        assert (dest / "stamped_receipt.txt").is_file()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
