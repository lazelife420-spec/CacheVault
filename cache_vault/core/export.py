"""Export / Save As for clips and collections.

Single clips export to .txt / .md / .html / .json. Multiple clips (or a
collection) export to an organized folder or a zip with:

    index.html     human-readable export browser
    manifest.json  machine-readable metadata
    clips/         one text file per clip
    files/         optional real-file copies (only if include_files=True)

File safety: path clips export their path/reference + metadata by default.
Real files are copied (never moved/deleted) into ``files/`` only when the user
explicitly opts in, and only for regular files that exist. Directories are
referenced only. Clip contents are never executed.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

from .. import __version__
from . import models, pathutil
from .models import Clip


def _slug(text: str, limit: int = 40) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", (text or "").strip()).strip("-")
    return (base[:limit] or "clip").rstrip("-")


def clip_metadata(clip: Clip, *, export_ts: str | None = None) -> dict:
    """The metadata record preserved for a clip on export."""
    is_path = pathutil.is_local_path(clip.content)
    return {
        "id": clip.id,
        "name": clip.preview or "",
        "content": clip.content,
        "is_reference": is_path,
        "reference_exists": pathutil.target_exists(clip.content) if is_path else None,
        "type": clip.classification,
        "format": clip.content_type,
        "size_bytes": len((clip.content or "").encode("utf-8")),
        "date_added": clip.created_at,
        "date_used": clip.updated_at,
        "source_app": clip.source_app,
        "source_window": clip.source_window,
        "is_favorite": bool(clip.is_pinned),
        "collection": clip.collection,
        "export_timestamp": export_ts or models.now_iso(),
        "cache_vault_version": __version__,
    }


# --- single-clip renderers -------------------------------------------------
def clip_as_text(clip: Clip) -> str:
    return clip.content or ""


def clip_as_markdown(clip: Clip, *, export_ts: str | None = None) -> str:
    m = clip_metadata(clip, export_ts=export_ts)
    lines = [
        f"# {m['name'] or 'Clip'}",
        "",
        f"- Type: {m['type']}",
        f"- Date added: {m['date_added']}",
        f"- Source: {m['source_app'] or '—'}",
        f"- Favorite: {'yes' if m['is_favorite'] else 'no'}",
        f"- Collection: {m['collection'] or '—'}",
        "",
        "```",
        clip.content or "",
        "```",
        "",
    ]
    return "\n".join(lines)


def clip_as_json(clip: Clip, *, export_ts: str | None = None) -> str:
    return json.dumps(clip_metadata(clip, export_ts=export_ts), indent=2)


def clip_as_html(clip: Clip, *, export_ts: str | None = None) -> str:
    m = clip_metadata(clip, export_ts=export_ts)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(m['name'] or 'Clip')}</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:2rem;}"
        "pre{background:#f4f4f5;padding:1rem;border-radius:8px;white-space:pre-wrap;"
        "word-break:break-word;}dt{font-weight:600;}</style></head><body>"
        f"<h1>{html.escape(m['name'] or 'Clip')}</h1>"
        f"<p>Type: {html.escape(m['type'])} · Added: {html.escape(m['date_added'])}"
        f" · Source: {html.escape(m['source_app'] or '—')}</p>"
        f"<pre>{html.escape(clip.content or '')}</pre>"
        "</body></html>"
    )


_EXTS = {".txt": "txt", ".md": "md", ".markdown": "md",
         ".html": "html", ".htm": "html", ".json": "json"}


def export_single(clip: Clip, dest_path: str | os.PathLike,
                  fmt: str | None = None, *, export_ts: str | None = None) -> Path:
    """Write a single clip to ``dest_path``. Format inferred from the extension
    when ``fmt`` is omitted (defaults to txt)."""
    dest = Path(dest_path)
    fmt = (fmt or _EXTS.get(dest.suffix.lower(), "txt")).lower()
    if fmt == "md":
        body = clip_as_markdown(clip, export_ts=export_ts)
    elif fmt == "html":
        body = clip_as_html(clip, export_ts=export_ts)
    elif fmt == "json":
        body = clip_as_json(clip, export_ts=export_ts)
    else:
        body = clip_as_text(clip)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    return dest


# --- collection / multi-clip export ----------------------------------------
def _index_html(metas: list[dict], clips: list[Clip], collection_name: str | None) -> str:
    rows = []
    for m, clip in zip(metas, clips):
        ref = ""
        if m["is_reference"]:
            state = "exists" if m["reference_exists"] else "missing"
            ref = f"<p><em>File reference ({state})</em></p>"
        rows.append(
            "<div class='clip'>"
            f"<h2>{html.escape(m['name'] or m['id'])}</h2>"
            f"<p class='meta'>{html.escape(m['type'])} · {html.escape(m['date_added'])}"
            f" · {html.escape(m['source_app'] or '—')}"
            f"{' · ★ favorite' if m['is_favorite'] else ''}"
            f"{(' · ' + html.escape(m['collection'])) if m['collection'] else ''}</p>"
            f"{ref}"
            f"<pre>{html.escape(clip.content or '')}</pre>"
            "</div>"
        )
    title = f"Cache Vault export — {collection_name}" if collection_name else "Cache Vault export"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:2rem;max-width:900px;}"
        ".clip{border:1px solid #e4e4e7;border-radius:10px;padding:1rem;margin:1rem 0;}"
        ".meta{color:#71717a;font-size:.9rem;}"
        "pre{background:#f4f4f5;padding:1rem;border-radius:8px;white-space:pre-wrap;"
        "word-break:break-word;}</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"<p class='meta'>{len(clips)} clip(s) · exported {html.escape(models.now_iso())}</p>"
        + "".join(rows) + "</body></html>"
    )


def _build_artifacts(clips: list[Clip], *, include_files: bool,
                     collection_name: str | None, export_ts: str):
    """Return (generated_text_files, real_file_copies, metas).

    generated_text_files: dict arcname -> text body (manifest/index/clips).
    real_file_copies: list of (src_path, arcname) to copy verbatim.
    """
    metas = [clip_metadata(c, export_ts=export_ts) for c in clips]
    generated: dict[str, str] = {}

    generated["manifest.json"] = json.dumps({
        "exported_at": export_ts,
        "cache_vault_version": __version__,
        "collection": collection_name,
        "count": len(clips),
        "include_files": include_files,
        "clips": metas,
    }, indent=2)
    generated["index.html"] = _index_html(metas, clips, collection_name)

    file_copies: list[tuple[str, str]] = []
    for i, clip in enumerate(clips):
        stem = f"{i:03d}_{_slug(clip.preview or clip.id)}"
        generated[f"clips/{stem}.txt"] = clip.content or ""
        if include_files and pathutil.is_local_path(clip.content):
            src = pathutil.clean_path(clip.content)
            # Copy real *files* only; directories are referenced, never bulk-copied.
            if os.path.isfile(src):
                file_copies.append((src, f"files/{i:03d}_{os.path.basename(src)}"))
    return generated, file_copies, metas


def export_collection(clips: list[Clip], dest_dir: str | os.PathLike, *,
                      include_files: bool = False, collection_name: str | None = None,
                      export_ts: str | None = None) -> Path:
    """Export clips into an organized folder."""
    export_ts = export_ts or models.now_iso()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    generated, file_copies, _ = _build_artifacts(
        clips, include_files=include_files, collection_name=collection_name,
        export_ts=export_ts)
    for arcname, body in generated.items():
        fp = dest / arcname
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(body, encoding="utf-8")
    for src, arcname in file_copies:
        fp = dest / arcname
        fp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, fp)  # copy, never move — original is untouched
    return dest


def export_zip(clips: list[Clip], dest_zip: str | os.PathLike, *,
               include_files: bool = False, collection_name: str | None = None,
               export_ts: str | None = None) -> Path:
    """Export clips into a single zip archive with the same structure."""
    export_ts = export_ts or models.now_iso()
    dest = Path(dest_zip)
    dest.parent.mkdir(parents=True, exist_ok=True)
    generated, file_copies, _ = _build_artifacts(
        clips, include_files=include_files, collection_name=collection_name,
        export_ts=export_ts)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, body in generated.items():
            zf.writestr(arcname, body)
        for src, arcname in file_copies:
            zf.write(src, arcname)
    return dest
