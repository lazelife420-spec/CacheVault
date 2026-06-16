"""Editable working copies — originals stay immutable on disk."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import models
from .pathutil import clean_path, is_local_path

KIND_FILE = "file"
KIND_HTML_BUNDLE = "html_bundle"
BUNDLE_META_NAME = "bundle.meta.json"

HTML_SUFFIXES = {".html", ".htm"}
TEXT_SCAN_SUFFIXES = {".html", ".htm", ".css"}
ASSET_FOLDER_NAMES = frozenset({
    "assets", "images", "img", "css", "js", "scripts", "fonts", "media",
})

HREF_SRC_RE = re.compile(
    r"""(?:href|src)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
CSS_URL_RE = re.compile(
    r"""url\s*\(\s*["']?([^"')\s]+)["']?\s*\)""",
    re.IGNORECASE,
)


@dataclass
class EditableCopyRecord:
    id: str
    clip_id: str
    original_path: str
    copy_path: str
    revision: int
    original_hash: str
    copy_hash: str
    created_at: str
    updated_at: str
    kind: str = KIND_FILE
    bundle_dir: str = ""


@dataclass
class HtmlBundleMeta:
    kind: str = KIND_HTML_BUNDLE
    revision: int = 1
    original_path: str = ""
    html_copy_path: str = ""
    bundle_dir: str = ""
    copied_assets: list[str] = field(default_factory=list)
    missing_assets: list[str] = field(default_factory=list)
    remote_assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    success: bool = True
    file_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HtmlBundleMeta:
        return cls(
            kind=data.get("kind", KIND_HTML_BUNDLE),
            revision=int(data.get("revision", 1)),
            original_path=data.get("original_path", ""),
            html_copy_path=data.get("html_copy_path", ""),
            bundle_dir=data.get("bundle_dir", ""),
            copied_assets=list(data.get("copied_assets", [])),
            missing_assets=list(data.get("missing_assets", [])),
            remote_assets=list(data.get("remote_assets", [])),
            warnings=list(data.get("warnings", [])),
            success=bool(data.get("success", True)),
            file_hashes=dict(data.get("file_hashes", {})),
        )


def editable_copies_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "CacheVault" / "EditableCopies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def receipts_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(base) / "CacheVault" / "Receipts" / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str, *, max_len: int = 80) -> str:
    stem = Path(name).name
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    if not stem or stem in {".", ".."}:
        stem = "file"
    return stem[:max_len]


def is_local_file_path(text: str) -> bool:
    if not is_local_path(text):
        return False
    return os.path.isfile(clean_path(text))


def is_html_path(path: os.PathLike | str) -> bool:
    return Path(clean_path(str(path))).suffix.lower() in HTML_SUFFIXES


def file_sha256(path: os.PathLike | str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_dir_for_clip(clip_id: str) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = editable_copies_root() / day / clip_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _revision_name(original_path: str, revision: int) -> str:
    p = Path(clean_path(original_path))
    stem = sanitize_filename(p.stem)
    suffix = p.suffix.lower()
    return f"{stem}.copy.{revision:03d}{suffix}"


def _revision_bundle_dir(clip_root: Path, revision: int) -> Path:
    return clip_root / f"rev-{revision:03d}"


def write_file_receipt(action: str, payload: dict) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rid = payload.get("clip_id") or models.new_id()[:8]
    path = receipts_dir() / f"{action}-{rid}-{ts}.json"
    body = {"action": action, **payload}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


def is_remote_ref(ref: str) -> bool:
    ref = (ref or "").strip()
    if not ref or ref.startswith("#"):
        return True
    lower = ref.lower()
    return lower.startswith((
        "http://", "https://", "//", "data:", "mailto:", "javascript:", "about:",
    ))


def _normalize_ref(ref: str) -> str:
    return ref.strip().split("#")[0].split("?")[0]


def _safe_resolve(ref: str, ref_base: Path, html_root: Path) -> Path | None:
    ref = _normalize_ref(ref)
    if not ref or is_remote_ref(ref):
        return None
    candidate = (ref_base / ref).resolve()
    root = html_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _rel_to_html_root(path: Path, html_root: Path) -> str:
    return path.resolve().relative_to(html_root.resolve()).as_posix()


def _extract_refs(text: str) -> list[str]:
    refs: list[str] = []
    refs.extend(HREF_SRC_RE.findall(text))
    refs.extend(CSS_URL_RE.findall(text))
    return refs


def scan_html_assets(html_path: Path) -> HtmlBundleMeta:
    """Scan HTML (and linked local CSS) for asset references."""
    html_path = Path(clean_path(str(html_path))).resolve()
    html_root = html_path.parent
    remote: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    local_files: dict[str, Path] = {}
    scan_queue: list[tuple[Path, Path]] = [(html_path, html_root)]
    scanned: set[Path] = set()

    while scan_queue:
        file_path, ref_base = scan_queue.pop()
        if file_path in scanned or not file_path.is_file():
            continue
        scanned.add(file_path)
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            warnings.append(f"Could not read {file_path.name}")
            continue
        for raw in _extract_refs(text):
            ref = _normalize_ref(raw)
            if not ref or ref.startswith("#"):
                continue
            if is_remote_ref(ref):
                if ref not in remote:
                    remote.append(ref)
                continue
            resolved = _safe_resolve(ref, ref_base, html_root)
            if resolved is None:
                if ref not in missing:
                    missing.append(ref)
                continue
            rel = _rel_to_html_root(resolved, html_root)
            local_files[rel] = resolved
            if resolved.suffix.lower() == ".css" and resolved not in scanned:
                scan_queue.append((resolved, resolved.parent))

    return HtmlBundleMeta(
        original_path=str(html_path),
        copied_assets=sorted(local_files.keys()),
        missing_assets=sorted(missing),
        remote_assets=sorted(remote),
        warnings=warnings,
        success=True,
    )


def _hash_bundle_dir(bundle_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not bundle_dir.is_dir():
        return out
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file() and path.name != BUNDLE_META_NAME:
            out[path.relative_to(bundle_dir).as_posix()] = file_sha256(path)
    return out


def save_bundle_meta(bundle_dir: Path, meta: HtmlBundleMeta) -> None:
    meta.bundle_dir = str(bundle_dir)
    meta.file_hashes = _hash_bundle_dir(bundle_dir)
    path = bundle_dir / BUNDLE_META_NAME
    path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")


def load_bundle_meta(bundle_dir: Path | str) -> HtmlBundleMeta | None:
    path = Path(bundle_dir) / BUNDLE_META_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return HtmlBundleMeta.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return None


def build_html_bundle(original_html: Path, bundle_dir: Path) -> HtmlBundleMeta:
    """Copy HTML and detected local assets into a managed bundle folder."""
    original_html = Path(clean_path(str(original_html))).resolve()
    html_root = original_html.parent
    html_name = original_html.name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_html_assets(original_html)
    html_dest = bundle_dir / html_name
    shutil.copy2(original_html, html_dest)

    copied: list[str] = []
    for rel in scan.copied_assets:
        src = html_root / rel
        if not src.is_file():
            if rel not in scan.missing_assets:
                scan.missing_assets.append(rel)
            continue
        dest = bundle_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(rel)

    scan.copied_assets = sorted(copied)
    scan.missing_assets = sorted(set(scan.missing_assets))
    scan.html_copy_path = str(html_dest)
    scan.bundle_dir = str(bundle_dir)
    save_bundle_meta(bundle_dir, scan)
    return scan


def bundle_changed_files(bundle_dir: Path, meta: HtmlBundleMeta) -> list[str]:
    current = _hash_bundle_dir(bundle_dir)
    changed: list[str] = []
    for rel, digest in current.items():
        if meta.file_hashes.get(rel) != digest:
            changed.append(rel)
    for rel in meta.file_hashes:
        if rel not in current:
            changed.append(rel)
    return sorted(set(changed))


def export_html_bundle_zip(
    bundle_dir: Path,
    dest_zip: Path,
    *,
    receipt_path: Path | None = None,
) -> None:
    """Zip a copied HTML bundle (never originals)."""
    bundle_dir = Path(bundle_dir)
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                arc = path.relative_to(bundle_dir).as_posix()
                zf.write(path, arc)
        if receipt_path and receipt_path.is_file():
            zf.write(receipt_path, f"receipts/{receipt_path.name}")


class EditableCopyStore:
    """SQLite-backed registry of editable copies."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS editable_copies (
                id            TEXT PRIMARY KEY,
                clip_id       TEXT NOT NULL,
                original_path TEXT NOT NULL,
                copy_path     TEXT NOT NULL,
                revision      INTEGER NOT NULL DEFAULT 1,
                original_hash TEXT,
                copy_hash     TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_editable_copies_clip "
            "ON editable_copies(clip_id)"
        )
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(editable_copies)").fetchall()
        }
        if "kind" not in existing:
            self.conn.execute(
                "ALTER TABLE editable_copies ADD COLUMN kind TEXT NOT NULL DEFAULT 'file'"
            )
        if "bundle_dir" not in existing:
            self.conn.execute(
                "ALTER TABLE editable_copies ADD COLUMN bundle_dir TEXT NOT NULL DEFAULT ''"
            )

    def latest_for_clip(self, clip_id: str) -> EditableCopyRecord | None:
        row = self.conn.execute(
            "SELECT * FROM editable_copies WHERE clip_id = ? "
            "ORDER BY revision DESC, rowid DESC LIMIT 1",
            (clip_id,),
        ).fetchone()
        return _row_to_record(row) if row else None

    def create_copy(self, clip_id: str, original_path: str) -> EditableCopyRecord:
        original_path = clean_path(original_path)
        if not os.path.isfile(original_path):
            raise FileNotFoundError(f"Original file not found: {original_path}")
        if is_html_path(original_path):
            return self._create_html_bundle(clip_id, original_path)
        return self._create_file_copy(clip_id, original_path)

    def _create_file_copy(self, clip_id: str, original_path: str) -> EditableCopyRecord:
        original_hash = file_sha256(original_path)
        latest = self.latest_for_clip(clip_id)
        revision = 1 if latest is None else latest.revision + 1
        copy_dir = _copy_dir_for_clip(clip_id)
        name = _revision_name(original_path, revision)
        copy_path = copy_dir / name
        if copy_path.exists():
            raise FileExistsError(str(copy_path))
        shutil.copy2(original_path, copy_path)
        copy_hash = file_sha256(copy_path)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at, kind, bundle_dir) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, original_path, str(copy_path), revision,
                original_hash, copy_hash, now, now, KIND_FILE, "",
            ),
        )
        self.conn.commit()
        return EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=original_path,
            copy_path=str(copy_path), revision=revision,
            original_hash=original_hash, copy_hash=copy_hash,
            created_at=now, updated_at=now, kind=KIND_FILE,
        )

    def _create_html_bundle(self, clip_id: str, original_path: str) -> EditableCopyRecord:
        original_hash = file_sha256(original_path)
        latest = self.latest_for_clip(clip_id)
        revision = 1 if latest is None else latest.revision + 1
        clip_root = _copy_dir_for_clip(clip_id)
        bundle_dir = _revision_bundle_dir(clip_root, revision)
        if bundle_dir.exists():
            raise FileExistsError(str(bundle_dir))
        meta = build_html_bundle(Path(original_path), bundle_dir)
        html_copy = bundle_dir / Path(original_path).name
        copy_hash = file_sha256(html_copy)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at, kind, bundle_dir) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, original_path, str(html_copy), revision,
                original_hash, copy_hash, now, now, KIND_HTML_BUNDLE, str(bundle_dir),
            ),
        )
        self.conn.commit()
        rec = EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=original_path,
            copy_path=str(html_copy), revision=revision,
            original_hash=original_hash, copy_hash=copy_hash,
            created_at=now, updated_at=now, kind=KIND_HTML_BUNDLE,
            bundle_dir=str(bundle_dir),
        )
        rec._bundle_meta = meta  # type: ignore[attr-defined]
        return rec

    def save_revision(self, clip_id: str) -> EditableCopyRecord | None:
        latest = self.latest_for_clip(clip_id)
        if latest is None:
            return None
        if latest.kind == KIND_HTML_BUNDLE:
            return self._save_html_revision(clip_id, latest)
        return self._save_file_revision(clip_id, latest)

    def _save_file_revision(self, clip_id: str, latest: EditableCopyRecord) -> EditableCopyRecord | None:
        if not os.path.isfile(latest.copy_path):
            return None
        current_hash = file_sha256(latest.copy_path)
        if current_hash == latest.copy_hash:
            return None
        revision = latest.revision + 1
        copy_dir = Path(latest.copy_path).parent
        name = _revision_name(latest.original_path, revision)
        copy_path = copy_dir / name
        shutil.copy2(latest.copy_path, copy_path)
        new_hash = file_sha256(copy_path)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at, kind, bundle_dir) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, latest.original_path, str(copy_path), revision,
                latest.original_hash, new_hash, now, now, KIND_FILE, "",
            ),
        )
        self.conn.commit()
        rec = EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=latest.original_path,
            copy_path=str(copy_path), revision=revision,
            original_hash=latest.original_hash, copy_hash=new_hash,
            created_at=now, updated_at=now, kind=KIND_FILE,
        )
        rec._previous_hash = latest.copy_hash  # type: ignore[attr-defined]
        return rec

    def _save_html_revision(self, clip_id: str, latest: EditableCopyRecord) -> EditableCopyRecord | None:
        bundle_dir = Path(latest.bundle_dir or Path(latest.copy_path).parent)
        if not bundle_dir.is_dir() or not Path(latest.copy_path).is_file():
            return None
        meta = load_bundle_meta(bundle_dir)
        if meta is None:
            return None
        changed = bundle_changed_files(bundle_dir, meta)
        if not changed:
            return None
        revision = latest.revision + 1
        new_dir = _revision_bundle_dir(bundle_dir.parent, revision)
        if new_dir.exists():
            raise FileExistsError(str(new_dir))
        shutil.copytree(bundle_dir, new_dir)
        new_html = new_dir / Path(latest.copy_path).name
        new_hash = file_sha256(new_html)
        new_meta = load_bundle_meta(new_dir) or meta
        new_meta.revision = revision
        save_bundle_meta(new_dir, new_meta)
        now = models.now_iso()
        rec_id = models.new_id()
        self.conn.execute(
            "INSERT INTO editable_copies "
            "(id, clip_id, original_path, copy_path, revision, original_hash, "
            "copy_hash, created_at, updated_at, kind, bundle_dir) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec_id, clip_id, latest.original_path, str(new_html), revision,
                latest.original_hash, new_hash, now, now, KIND_HTML_BUNDLE, str(new_dir),
            ),
        )
        self.conn.commit()
        rec = EditableCopyRecord(
            id=rec_id, clip_id=clip_id, original_path=latest.original_path,
            copy_path=str(new_html), revision=revision,
            original_hash=latest.original_hash, copy_hash=new_hash,
            created_at=now, updated_at=now, kind=KIND_HTML_BUNDLE,
            bundle_dir=str(new_dir),
        )
        rec._previous_hash = latest.copy_hash  # type: ignore[attr-defined]
        rec._changed_files = changed  # type: ignore[attr-defined]
        return rec

    def count_distinct_clips(self, *, kind: str | None = None) -> int:
        if kind:
            row = self.conn.execute(
                "SELECT COUNT(DISTINCT clip_id) AS n FROM editable_copies WHERE kind = ?",
                (kind,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(DISTINCT clip_id) AS n FROM editable_copies",
            ).fetchone()
        return int(row["n"]) if row else 0

    def list_latest_records(
        self, *, kind: str | None = None, limit: int = 500,
    ) -> list[EditableCopyRecord]:
        if kind:
            rows = self.conn.execute(
                """
                SELECT e.* FROM editable_copies e
                INNER JOIN (
                    SELECT clip_id, MAX(revision) AS max_rev
                    FROM editable_copies WHERE kind = ?
                    GROUP BY clip_id
                ) latest ON e.clip_id = latest.clip_id AND e.revision = latest.max_rev
                WHERE e.kind = ?
                ORDER BY e.updated_at DESC, e.rowid DESC
                LIMIT ?
                """,
                (kind, kind, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT e.* FROM editable_copies e
                INNER JOIN (
                    SELECT clip_id, MAX(revision) AS max_rev
                    FROM editable_copies
                    GROUP BY clip_id
                ) latest ON e.clip_id = latest.clip_id AND e.revision = latest.max_rev
                ORDER BY e.updated_at DESC, e.rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def delete_copy_record(self, copy_id: str) -> EditableCopyRecord | None:
        row = self.conn.execute(
            "SELECT * FROM editable_copies WHERE id = ?", (copy_id,),
        ).fetchone()
        if not row:
            return None
        rec = _row_to_record(row)
        if rec.kind == KIND_HTML_BUNDLE and rec.bundle_dir:
            bundle = Path(rec.bundle_dir)
            if bundle.is_dir():
                shutil.rmtree(bundle, ignore_errors=True)
        else:
            copy_path = Path(rec.copy_path)
            if copy_path.is_file():
                copy_path.unlink()
        self.conn.execute("DELETE FROM editable_copies WHERE id = ?", (copy_id,))
        self.conn.commit()
        return rec


def _row_to_record(row: sqlite3.Row) -> EditableCopyRecord:
    keys = row.keys()
    return EditableCopyRecord(
        id=row["id"],
        clip_id=row["clip_id"],
        original_path=row["original_path"],
        copy_path=row["copy_path"],
        revision=int(row["revision"]),
        original_hash=row["original_hash"] or "",
        copy_hash=row["copy_hash"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        kind=row["kind"] if "kind" in keys else KIND_FILE,
        bundle_dir=row["bundle_dir"] if "bundle_dir" in keys else "",
    )


def open_copy_path(copy_path: str) -> bool:
    """Open a copied file with the OS default handler (browser for HTML)."""
    path = Path(copy_path)
    if not path.is_file():
        return False
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    except OSError:
        return False


def edit_copy_source(copy_path: str) -> bool:
    """Open copied HTML source in a plain editor (Notepad on Windows)."""
    path = Path(copy_path)
    if not path.is_file():
        return False
    try:
        subprocess.run(["notepad.exe", str(path)], check=False)
        return True
    except OSError:
        return open_copy_path(copy_path)


def html_bundle_summary(clip_id: str, store: EditableCopyStore) -> dict | None:
    rec = store.latest_for_clip(clip_id)
    if rec is None or rec.kind != KIND_HTML_BUNDLE:
        return None
    meta = load_bundle_meta(rec.bundle_dir) if rec.bundle_dir else None
    if meta is None:
        return None
    return {
        "revision": rec.revision,
        "original_html": rec.original_path,
        "editable_html_copy": rec.copy_path,
        "bundle_dir": rec.bundle_dir,
        "copied_asset_count": len(meta.copied_assets),
        "missing_asset_count": len(meta.missing_assets),
        "remote_asset_count": len(meta.remote_assets),
        "copied_assets": meta.copied_assets[:12],
        "missing_assets": meta.missing_assets[:12],
        "remote_assets": meta.remote_assets[:12],
        "warnings": meta.warnings[:8],
    }
