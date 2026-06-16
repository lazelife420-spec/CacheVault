import json
import zipfile

from cache_vault.core import export, models
from cache_vault.core.models import Clip


def _text_clip(content="hello world", **kw):
    return Clip(content=content, preview=content[:40], **kw)


def test_export_single_txt(tmp_path):
    dest = export.export_single(_text_clip("plain text"), tmp_path / "c.txt")
    assert dest.read_text(encoding="utf-8") == "plain text"


def test_export_single_md_html_json(tmp_path):
    clip = _text_clip("body content", classification=models.CLASS_PLAIN)
    md = export.export_single(clip, tmp_path / "c.md")
    assert md.read_text(encoding="utf-8").startswith("#")
    html_out = export.export_single(clip, tmp_path / "c.html")
    assert "<html" in html_out.read_text(encoding="utf-8").lower()
    js = export.export_single(clip, tmp_path / "c.json")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["content"] == "body content"
    assert data["cache_vault_version"]


def test_export_collection_folder_structure(tmp_path):
    clips = [_text_clip("one"), _text_clip("two")]
    out = export.export_collection(clips, tmp_path / "out", collection_name="Work")
    assert (out / "index.html").exists()
    assert (out / "manifest.json").exists()
    assert list((out / "clips").glob("*.txt"))
    # No files/ copies by default.
    assert not (out / "files").exists()


def test_manifest_contains_metadata(tmp_path):
    clip = _text_clip("meta me", source_app="chrome.exe", is_pinned=True,
                      collection="Links")
    out = export.export_collection([clip], tmp_path / "out")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 1
    m = manifest["clips"][0]
    for key in ("id", "name", "content", "type", "size_bytes", "date_added",
                "date_used", "source_app", "is_favorite", "collection",
                "export_timestamp", "cache_vault_version"):
        assert key in m
    assert m["is_favorite"] is True
    assert m["collection"] == "Links"


def test_export_zip(tmp_path):
    clips = [_text_clip("zipme")]
    z = export.export_zip(clips, tmp_path / "out.zip")
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    assert "index.html" in names
    assert "manifest.json" in names
    assert any(n.startswith("clips/") for n in names)


def test_path_clip_not_copied_by_default(tmp_path):
    src = tmp_path / "real.bin"
    src.write_text("payload", encoding="utf-8")
    clip = _text_clip(str(src), classification=models.CLASS_PATH)
    out = export.export_collection([clip], tmp_path / "out", include_files=False)
    assert not (out / "files").exists()        # original not copied
    assert src.exists()                          # original untouched
    # The reference is still recorded in the manifest.
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["clips"][0]["is_reference"] is True


def test_include_files_copies_into_output_only(tmp_path):
    src = tmp_path / "real.bin"
    src.write_text("payload", encoding="utf-8")
    clip = _text_clip(str(src), classification=models.CLASS_PATH)
    out = export.export_collection([clip], tmp_path / "out", include_files=True)
    copies = list((out / "files").glob("*"))
    assert len(copies) == 1                      # copied into export output
    assert copies[0].read_text(encoding="utf-8") == "payload"
    assert src.exists()                          # original neither moved nor deleted
