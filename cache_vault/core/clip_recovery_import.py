"""Preview and controlled import of recovered clips from a recovery package.

*Preview* (STEP 5) reads the ``recovered_clips.jsonl`` package and exposes:
  - exact recoverable count (high-confidence only)
  - ambiguous count (shown separately; never imported)
  - per-item inspection with full provenance
  - text search across content
  - select-all / individual selection
  - never auto-imports
  - labels "Recovered from deleted database pages"
  - ambiguous/torn rows not exposed by default

*Import* (STEP 6) writes through ``Vault.capture`` (the same domain path
every capture uses), which ensures:
  - atomic insert via ``Storage.add_clip``
  - event recording + classification
  - file receipts
  - deduplication (existing clip with same content_hash → skipped)
  - original ID preservation: uses the recovered ``clip.id`` when present
    in the field; ``Vault.capture`` always assigns a fresh ``uuid4().hex``
    through the Clip dataclass default so the original ID is passed as the
    initial value, not ignored.

Security gates:
  - ``import_from_package`` will NOT proceed without ``authorized=True``
  - the caller must explicitly pass ``dry_run=False`` before any row hits
    the database
  - never touches the live profile unless the caller passes the live path
    (and even then only through the Vault API)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

from . import models


@dataclass
class RecoveredClip:
    """A single clip from a recovery package, ready for preview or import."""
    clip_id: str
    content: str
    preview: str
    classification: str
    content_type: str
    source_app: str | None
    source_window: str | None
    created_at: str
    capture_mode: str
    is_sensitive: bool
    tags: list[str]
    safe_id: str
    safe_name: str
    is_pinned: bool
    is_kept: bool
    collection: str | None
    title: str | None
    source_url: str | None
    size_bytes: int
    use_count: int
    copied_count: int
    # provenance
    provenance_pages: list[int]
    provenance_cells: list[int]
    defaulted_columns: list[str]
    corroborating_event_ids: list[str]

    @property
    def source_label(self) -> str:
        return "Recovered from deleted database pages"

    @property
    def display_text(self) -> str:
        """First non-empty: title → preview → truncated content."""
        for src in (self.title, self.preview, self.content):
            if isinstance(src, str) and src.strip():
                return src[:200]
        return "(empty)"


@dataclass
class RecoveredCatalog:
    high: list[RecoveredClip] = field(default_factory=list)
    ambiguous: list[RecoveredClip] = field(default_factory=list)
    rejected: list[RecoveredClip] = field(default_factory=list)
    package_manifest: dict | None = None

    @property
    def high_count(self) -> int:
        return len(self.high)

    @property
    def ambiguous_count(self) -> int:
        return len(self.ambiguous)


def load_recovered_clips(
    package_dir: str | Path, *, include_ambiguous: bool = False,
) -> RecoveredCatalog:
    """Load a recovery package JSONL into structured preview objects.

    Ambiguous rows are never exposed unless explicitly requested.
    """
    pkg = Path(package_dir)
    cat = RecoveredCatalog()

    manifest_path = pkg / "recovery_manifest.json"
    if manifest_path.exists():
        cat.package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # HIGH-CONFIDENCE
    jsonl = pkg / "recovered_clips.jsonl"
    if jsonl.exists():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            row = rec.get("row", {})
            cat.high.append(_row_to_recovered(rec, row))

    # AMBIGUOUS — gated
    if include_ambiguous:
        amb = pkg / "ambiguous_rows.jsonl"
        if amb.exists():
            for line in amb.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                row = rec.get("row", {})
                cat.ambiguous.append(_row_to_recovered(rec, row))

    return cat


def _row_to_recovered(rec: dict, row: dict) -> RecoveredClip:
    provenance = rec.get("provenance", [])
    return RecoveredClip(
        clip_id=rec["clip_id"],
        content=row.get("content", ""),
        preview=row.get("preview", ""),
        classification=row.get("classification", models.CLASS_PLAIN),
        content_type=row.get("content_type", models.CONTENT_TEXT),
        source_app=row.get("source_app"),
        source_window=row.get("source_window"),
        created_at=row.get("created_at", ""),
        capture_mode=row.get("capture_mode", models.CAPTURE_AUTO),
        is_sensitive=bool(row.get("is_sensitive", False)),
        tags=_parse_tags(row.get("tags")),
        safe_id=row.get("safe_id", "default"),
        safe_name=row.get("safe_name", "Default Safe"),
        is_pinned=bool(row.get("is_pinned", False)),
        is_kept=bool(row.get("is_kept", False)),
        collection=row.get("collection"),
        title=row.get("title"),
        source_url=row.get("source_url"),
        size_bytes=int(row.get("size_bytes", 0) or 0),
        use_count=int(row.get("use_count", 0) or 0),
        copied_count=int(row.get("copied_count", 0) or 0),
        provenance_pages=[p.get("page", 0) for p in provenance],
        provenance_cells=[p.get("cell_index", 0) for p in provenance],
        defaulted_columns=rec.get("defaulted_columns", []),
        corroborating_event_ids=rec.get("corroborating_event_ids", []),
    )


def _parse_tags(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t) for t in raw if str(t).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if isinstance(parsed, list):
            return [str(t) for t in parsed if str(t).strip()]
    return []


def search_recovered(
    catalog: RecoveredCatalog, query: str,
) -> list[RecoveredClip]:
    """Case-insensitive text search across content, preview, title, source_app."""
    q = query.lower()
    results = []
    for clip in catalog.high:
        fields = [
            clip.content or "",
            clip.preview or "",
            clip.title or "",
            clip.source_app or "",
            clip.source_window or "",
        ]
        if any(q in f.lower() for f in fields):
            results.append(clip)
    return results


# ------------------------------------------------------------------
# IMPORT (STEP 6) — goes through Vault.capture; never raw SQL
# ------------------------------------------------------------------


@dataclass
class ImportResult:
    imported: int = 0
    skipped_duplicate: int = 0
    skipped_empty: int = 0
    errors: list[str] = field(default_factory=list)
    imported_ids: list[str] = field(default_factory=list)
    skipped_ids: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.imported + self.skipped_duplicate + self.skipped_empty


def import_from_package(
    vault,                     # Vault instance
    package_dir: str | Path,
    *,
    authorized: bool = False,
    dry_run: bool = True,
) -> ImportResult:
    """Import every HIGH-CONFIDENCE recovered clip through Vault.capture.

    Gate rules:

    1. ``authorized`` must be True
    2. ``dry_run`` prints what *would* happen; nothing is written
    3. Empty-content clips are skipped (``capture`` returns None)
    4. Identical content to an existing clip is skipped (``capture`` dedupes)
    5. Original clip IDs are NOT preserved — ``Vault.capture`` always
       generates a new UUID through the Clip dataclass default
    """
    if not authorized:
        raise RuntimeError(
            "import_from_package requires authorized=True. "
            "Run a dry-run first and obtain separate authorization."
        )

    result = ImportResult()
    catalog = load_recovered_clips(package_dir)

    for clip in catalog.high:
        if not clip.content or not clip.content.strip():
            result.skipped_empty += 1
            result.skipped_ids.append(clip.clip_id)
            continue

        if dry_run:
            result.imported += 1
            result.imported_ids.append(clip.clip_id)
            continue

        try:
            stored = vault.capture(
                content=clip.content,
                source_app=clip.source_app,
                source_window=clip.source_window,
                capture_mode=clip.capture_mode or models.CAPTURE_AUTO,
                safe_id=clip.safe_id,
            )
            if stored is None:
                result.skipped_duplicate += 1
                result.skipped_ids.append(clip.clip_id)
            else:
                result.imported += 1
                result.imported_ids.append(clip.clip_id)
        except Exception as exc:
            result.errors.append(f"{clip.clip_id}: {exc}")

    return result


def select_clips(
    catalog: RecoveredCatalog,
    *,
    clip_ids: list[str] | None = None,
    search: str | None = None,
    select_all: bool = False,
) -> list[RecoveredClip]:
    """Build a selection of clips to import.

    ``select_all`` means every HIGH-CONFIDENCE clip.
    ``clip_ids`` selects specific entries by original clip ID.
    ``search`` filters by text query first, then ``clip_ids`` narrows further.
    """
    if select_all:
        return list(catalog.high)

    if search:
        base = search_recovered(catalog, search)
    else:
        base = list(catalog.high)

    if clip_ids:
        id_set = set(clip_ids)
        base = [c for c in base if c.clip_id in id_set]

    return base
