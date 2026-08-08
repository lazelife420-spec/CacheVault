"""Forensic recovery of hard-deleted ``clips`` rows from SQLite freelist pages.

Context: a direct out-of-application ``DELETE FROM clips`` can remove rows that
CacheVault's own deletion pipeline would have kept recoverable. SQLite does not
overwrite the pages it frees (absent ``secure_delete``/``VACUUM``), so the row
images usually survive in the freelist until those pages are reused.

Doctrine, mirroring ``permanent_delete``'s "fail closed, preserve data":

- **Read-only.** Nothing here ever opens a database for writing. The caller
  passes raw bytes; this module never touches a live profile.
- **Never repair.** A field that does not decode to a structurally valid value
  is a *rejection reason*, never something to coerce, default or guess. A
  fabricated clip is worse than a missing one.
- **Three-way outcome.** Every decoded record lands in exactly one of
  HIGH / AMBIGUOUS / REJECTED, and always carries the reasons why.
- **Provenance.** Every candidate records the page, cell index and byte offset
  it came from, so any claim can be re-derived from the source file.

Freed pages are read as-is, so a page may contain a *stale* image of a row that
was later updated. Where several images of one clip id disagree, the candidate
is downgraded rather than silently resolved.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator, Sequence

from . import models

# --- tunables ---------------------------------------------------------------

CLIP_COLUMNS: tuple[str, ...] = (
    "id", "created_at", "updated_at", "content_hash", "content_type",
    "content", "preview", "source_app", "source_window", "classification",
    "tags", "is_pinned", "is_kept", "is_sensitive", "expires_at", "deleted_at",
    "duplicate_of", "collection", "title", "source_url", "normalized_hash",
    "size_bytes", "last_used_at", "use_count", "copied_count", "safe_id",
    "safe_name", "capture_mode", "is_saved_to_phone",
)

#: Declared column defaults, positionally aligned with :data:`CLIP_COLUMNS`.
#:
#: ``Storage._migrate`` grows the table with ``ALTER TABLE clips ADD COLUMN``,
#: which SQLite does **not** backfill into existing row images: a row written
#: before a migration keeps its shorter record and SQLite substitutes the
#: column's declared DEFAULT on read. Recovered short records are therefore
#: completed with these same declared defaults -- this reproduces SQLite's own
#: read semantics for those rows, it is not a repair of damaged data. Which
#: columns were defaulted is always recorded on the candidate.
CLIP_COLUMN_DEFAULTS: tuple = (
    None, None, None, None, None,          # id, created_at, updated_at, content_hash, content_type
    None, None, None, None, None,          # content, preview, source_app, source_window, classification
    None, 0, 0, 0, None,                   # tags, is_pinned, is_kept, is_sensitive, expires_at
    None, None, None, None, None,          # deleted_at, duplicate_of, collection, title, source_url
    None, 0, None, 0, 0,                   # normalized_hash, size_bytes, last_used_at, use_count, copied_count
    "default", "Default Safe", "auto", 0,  # safe_id, safe_name, capture_mode, is_saved_to_phone
)

#: The original shipped schema had 18 columns; anything shorter is another
#: table's record, not a clip.
MIN_CLIP_COLUMNS = 18

CONF_HIGH = "high"
CONF_AMBIGUOUS = "ambiguous"
CONF_REJECTED = "rejected"

#: A clip id is ``uuid.uuid4().hex`` -- exactly 32 lowercase hex characters.
CLIP_ID_RE = re.compile(r"^[0-9a-f]{32}$")

#: No clip can predate the project; allow a day of clock skew on the upper end.
MIN_PLAUSIBLE_TS = datetime(2020, 1, 1, tzinfo=timezone.utc)

MAX_CONTENT_CHARS = 8 * 1024 * 1024
MAX_SHORT_TEXT = 4096
MAX_TAGS = 256

TABLE_LEAF = 0x0D


# --- header / freelist ------------------------------------------------------


@dataclass(frozen=True)
class DbHeader:
    page_size: int
    page_count: int
    freelist_head: int
    freelist_count: int


def read_header(raw: bytes) -> DbHeader:
    if len(raw) < 100 or raw[:16] != b"SQLite format 3\x00":
        raise ValueError("not a SQLite database image")
    page_size = struct.unpack(">H", raw[16:18])[0]
    if page_size == 1:
        page_size = 65536
    return DbHeader(
        page_size=page_size,
        page_count=struct.unpack(">I", raw[28:32])[0],
        freelist_head=struct.unpack(">I", raw[32:36])[0],
        freelist_count=struct.unpack(">I", raw[36:40])[0],
    )


def page_bytes(raw: bytes, header: DbHeader, page_no: int) -> bytes:
    """Return the raw image of 1-based *page_no* (empty if out of range)."""
    if page_no < 1:
        return b""
    off = (page_no - 1) * header.page_size
    return raw[off:off + header.page_size]


@dataclass
class FreelistScan:
    trunk_pages: list[int] = field(default_factory=list)
    leaf_pages: list[int] = field(default_factory=list)
    consistent: bool = False

    @property
    def total(self) -> int:
        return len(self.trunk_pages) + len(self.leaf_pages)


def scan_freelist(raw: bytes, header: DbHeader) -> FreelistScan:
    """Walk the freelist trunk chain and collect every freed page.

    ``consistent`` reports whether the walk found exactly as many pages as the
    file header claims -- a self-check that the traversal is reading real
    freelist structure rather than arbitrary bytes.
    """
    scan = FreelistScan()
    seen: set[int] = set()
    nxt = header.freelist_head
    max_leaves = header.page_size // 4
    while nxt and nxt not in seen and nxt <= header.page_count:
        seen.add(nxt)
        page = page_bytes(raw, header, nxt)
        if len(page) < 8:
            break
        scan.trunk_pages.append(nxt)
        following = struct.unpack(">I", page[0:4])[0]
        n_leaf = struct.unpack(">I", page[4:8])[0]
        if n_leaf > max_leaves:
            break
        for i in range(n_leaf):
            start = 8 + 4 * i
            leaf = struct.unpack(">I", page[start:start + 4])[0]
            if leaf and leaf <= header.page_count:
                scan.leaf_pages.append(leaf)
        nxt = following
    scan.consistent = scan.total == header.freelist_count
    return scan


# --- SQLite record decoding -------------------------------------------------


def read_varint(buf: bytes, off: int) -> tuple[int | None, int]:
    value = 0
    for i in range(9):
        if off + i >= len(buf):
            return None, off
        byte = buf[off + i]
        if i == 8:
            return (value << 8) | byte, off + 9
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, off + i + 1
    return value, off


def serial_type_size(serial: int) -> int:
    """Byte width of a SQLite serial type (0 for the constant/reserved types)."""
    if serial in (0, 8, 9, 10, 11):
        return 0
    if 1 <= serial <= 4:
        return serial
    if serial == 5:
        return 6
    if serial in (6, 7):
        return 8
    return (serial - 12) // 2 if serial % 2 == 0 else (serial - 13) // 2


def decode_record(payload: bytes) -> list | None:
    """Decode a SQLite record body into python values, or None if malformed."""
    header_len, pos = read_varint(payload, 0)
    if header_len is None or not 0 < header_len <= len(payload):
        return None
    serials: list[int] = []
    while pos < header_len:
        serial, pos = read_varint(payload, pos)
        if serial is None:
            return None
        serials.append(serial)
    values: list = []
    cursor = header_len
    for serial in serials:
        size = serial_type_size(serial)
        if cursor + size > len(payload):
            return None
        chunk = payload[cursor:cursor + size]
        if serial == 0:
            values.append(None)
        elif 1 <= serial <= 6:
            values.append(int.from_bytes(chunk, "big", signed=True))
        elif serial == 7:
            values.append(struct.unpack(">d", chunk)[0])
        elif serial == 8:
            values.append(0)
        elif serial == 9:
            values.append(1)
        elif serial >= 12 and serial % 2 == 0:
            values.append(chunk)
        elif serial >= 13:
            try:
                values.append(chunk.decode("utf-8"))
            except UnicodeDecodeError:
                return None  # torn text: never salvage with replacement chars
        else:
            return None
        cursor += size
    return values


@dataclass(frozen=True)
class RecordLocation:
    page: int
    cell_index: int
    cell_offset: int
    payload_end: int


def iter_page_records(
    raw: bytes, header: DbHeader, page_no: int,
) -> Iterator[tuple[RecordLocation, list]]:
    """Yield every decodable table-leaf record still present on *page_no*."""
    page = page_bytes(raw, header, page_no)
    if len(page) < 8 or page[0] != TABLE_LEAF:
        return
    n_cells = struct.unpack(">H", page[3:5])[0]
    if n_cells == 0 or n_cells > header.page_size // 4:
        return
    for index in range(n_cells):
        ptr = 8 + index * 2
        if ptr + 2 > len(page):
            return
        cell_off = struct.unpack(">H", page[ptr:ptr + 2])[0]
        if not 0 < cell_off < len(page):
            continue
        payload_len, pos = read_varint(page, cell_off)
        if payload_len is None or not 0 < payload_len <= header.page_size:
            continue
        _rowid, pos = read_varint(page, pos)
        if _rowid is None:
            continue
        payload = page[pos:pos + payload_len]
        if len(payload) < payload_len:
            continue  # overflow / truncated: refuse rather than partially read
        values = decode_record(payload)
        if values is None:
            continue
        yield RecordLocation(page_no, index, cell_off, pos + payload_len), values


# --- validation -------------------------------------------------------------


def _is_iso_timestamp(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    upper = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)
    return MIN_PLAUSIBLE_TS <= parsed <= upper


def _is_bool_int(value) -> bool:
    return isinstance(value, int) and value in (0, 1)


def _is_clean_short_text(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str) or len(value) > MAX_SHORT_TEXT:
        return False
    return not any(ord(ch) < 32 and ch not in "\t\n\r" for ch in value)


def validate_row(values: Sequence) -> tuple[dict | None, list[str], list[str]]:
    """Structurally validate a decoded record against the ``clips`` schema.

    Returns ``(row_or_None, reasons, defaulted_columns)``. Reasons are always
    populated on failure. The only values ever supplied by this function are
    the table's *declared* defaults for trailing columns a pre-migration row
    predates (see :data:`CLIP_COLUMN_DEFAULTS`); a value that is present but
    malformed is never coerced, only reported.
    """
    reasons: list[str] = []
    defaulted: list[str] = []

    if len(values) > len(CLIP_COLUMNS):
        return None, [f"column_count={len(values)} exceeds={len(CLIP_COLUMNS)}"], []
    if len(values) < MIN_CLIP_COLUMNS:
        return None, [f"column_count={len(values)} below_min={MIN_CLIP_COLUMNS}"], []

    if len(values) < len(CLIP_COLUMNS):
        missing = CLIP_COLUMNS[len(values):]
        values = list(values) + list(CLIP_COLUMN_DEFAULTS[len(values):])
        defaulted = list(missing)

    row = dict(zip(CLIP_COLUMNS, values))

    clip_id = row["id"]
    if not isinstance(clip_id, str) or not CLIP_ID_RE.match(clip_id):
        return None, ["id_shape_invalid"], []

    if not _is_iso_timestamp(row["created_at"]):
        reasons.append("created_at_invalid")
    if not _is_iso_timestamp(row["updated_at"]):
        reasons.append("updated_at_invalid")

    for opt in ("expires_at", "deleted_at", "last_used_at"):
        val = row[opt]
        if val is not None and not _is_iso_timestamp(val):
            reasons.append(f"{opt}_invalid")

    if row["content_type"] not in (models.CONTENT_TEXT, models.CONTENT_IMAGE):
        reasons.append("content_type_unknown")
    if row["classification"] not in models.CLASSIFICATIONS:
        reasons.append("classification_unknown")
    if row["capture_mode"] not in models.CAPTURE_MODES:
        reasons.append("capture_mode_unknown")

    content = row["content"]
    if not isinstance(content, str):
        reasons.append("content_not_text")
    elif len(content) > MAX_CONTENT_CHARS:
        reasons.append("content_too_large")

    if not _is_clean_short_text(row["source_app"]):
        reasons.append("source_app_implausible")
    for opt in ("source_window", "collection", "title", "source_url", "safe_name"):
        if not _is_clean_short_text(row[opt]):
            reasons.append(f"{opt}_implausible")

    for flag in ("is_pinned", "is_kept", "is_sensitive", "is_saved_to_phone"):
        if not _is_bool_int(row[flag]):
            reasons.append(f"{flag}_not_boolean")

    for num in ("size_bytes", "use_count", "copied_count"):
        val = row[num]
        if not isinstance(val, int) or isinstance(val, bool) or val < 0:
            reasons.append(f"{num}_invalid")

    tags = row["tags"]
    if tags is not None:
        if not isinstance(tags, str):
            reasons.append("tags_not_text")
        else:
            try:
                parsed = json.loads(tags)
            except (ValueError, TypeError):
                reasons.append("tags_not_json")
            else:
                if not isinstance(parsed, list) or len(parsed) > MAX_TAGS:
                    reasons.append("tags_not_list")
                elif not all(isinstance(t, str) for t in parsed):
                    reasons.append("tags_not_strings")

    for opt in ("duplicate_of", "content_hash", "normalized_hash"):
        val = row[opt]
        if val is not None and not isinstance(val, str):
            reasons.append(f"{opt}_not_text")
    dup = row["duplicate_of"]
    if isinstance(dup, str) and dup and not CLIP_ID_RE.match(dup):
        reasons.append("duplicate_of_shape_invalid")
    if isinstance(dup, str) and dup == clip_id:
        reasons.append("duplicate_of_self")

    if row["safe_id"] is not None and not _is_clean_short_text(row["safe_id"]):
        reasons.append("safe_id_implausible")

    # impossible combinations
    if (row["content_type"] == models.CONTENT_IMAGE
            and row["classification"] not in (models.CLASS_IMAGE, models.CLASS_PLAIN)):
        reasons.append("image_content_type_conflicts_classification")
    if isinstance(content, str) and isinstance(row["preview"], str):
        if content and not content.strip() and row["preview"].strip():
            reasons.append("preview_without_content")

    return row, reasons, defaulted


# --- candidate assembly -----------------------------------------------------


@dataclass
class Candidate:
    clip_id: str
    row: dict
    locations: list[RecordLocation]
    confidence: str
    reasons: list[str]
    variants: int = 1
    corroborating_events: list[int] = field(default_factory=list)
    #: Trailing columns supplied from the table's declared defaults because the
    #: recovered row predates the migration that added them.
    defaulted_columns: list[str] = field(default_factory=list)


@dataclass
class RecoveryResult:
    header: DbHeader
    freelist: FreelistScan
    pages_scanned: int = 0
    pages_with_leaf_header: int = 0
    records_decoded: int = 0
    high: list[Candidate] = field(default_factory=list)
    ambiguous: list[Candidate] = field(default_factory=list)
    rejected: list[Candidate] = field(default_factory=list)
    #: Records that never reached clip validation, by reason. Kept explicitly
    #: so the difference between "decoded cells" and "candidates" is always
    #: accounted for rather than silently dropped.
    discarded: dict[str, int] = field(default_factory=dict)

    def _discard(self, reason: str) -> None:
        self.discarded[reason] = self.discarded.get(reason, 0) + 1

    @property
    def accounted(self) -> bool:
        """Every decoded cell must land in exactly one bucket."""
        return self.records_decoded == (
            len(self.high) + len(self.ambiguous) + len(self.rejected)
            + sum(self.discarded.values())
        )

    @property
    def counts(self) -> dict:
        return {
            "pages_scanned": self.pages_scanned,
            "pages_with_leaf_header": self.pages_with_leaf_header,
            "records_decoded": self.records_decoded,
            "high": len(self.high),
            "ambiguous": len(self.ambiguous),
            "rejected": len(self.rejected),
            "discarded": dict(self.discarded),
            "discarded_total": sum(self.discarded.values()),
            "fully_accounted": self.accounted,
        }


def _identity(row: dict) -> tuple:
    """Fields that must agree across stale images of the same clip."""
    return (row["created_at"], row["content"], row["content_type"])


def recover_candidates(
    raw: bytes, known_missing_ids: set[str] | None = None,
) -> RecoveryResult:
    """Decode and classify every recoverable ``clips`` row in the freelist."""
    header = read_header(raw)
    freelist = scan_freelist(raw, header)
    result = RecoveryResult(header=header, freelist=freelist)

    by_id: dict[str, list[tuple[RecordLocation, dict, list[str]]]] = {}
    rejects: list[Candidate] = []
    claimed: dict[int, list[tuple[int, int]]] = {}
    defaults_by_id: dict[str, list[str]] = {}

    for page_no in freelist.leaf_pages:
        result.pages_scanned += 1
        page = page_bytes(raw, header, page_no)
        if len(page) >= 1 and page[0] == TABLE_LEAF:
            result.pages_with_leaf_header += 1
        for location, values in iter_page_records(raw, header, page_no):
            result.records_decoded += 1
            row, reasons, defaulted = validate_row(values)
            if row is None:
                # Not a clips row (another table's record, or an unusable id).
                # Recorded rather than dropped so the census always balances.
                result._discard(reasons[0] if reasons else "unclassified")
                continue
            span = (location.cell_offset, location.payload_end)
            overlaps = any(
                span[0] < end and start < span[1]
                for start, end in claimed.get(page_no, [])
            )
            if overlaps:
                reasons = [*reasons, "payload_overlaps_accepted_record"]
            else:
                claimed.setdefault(page_no, []).append(span)

            if known_missing_ids is not None and row["id"] not in known_missing_ids:
                reasons = [*reasons, "id_not_in_known_missing_set"]

            if reasons:
                rejects.append(Candidate(
                    clip_id=row["id"], row=row, locations=[location],
                    confidence=CONF_REJECTED, reasons=reasons,
                    defaulted_columns=defaulted,
                ))
            else:
                by_id.setdefault(row["id"], []).append((location, row, reasons))
                if defaulted:
                    defaults_by_id[row["id"]] = defaulted

    for clip_id, hits in by_id.items():
        identities = {_identity(r) for _, r, _ in hits}
        locations = [loc for loc, _, _ in hits]
        if len(identities) == 1:
            # stale duplicates that agree: keep the most recently updated image
            best = max(hits, key=lambda h: (h[1]["updated_at"] or ""))
            result.high.append(Candidate(
                clip_id=clip_id, row=best[1], locations=locations,
                confidence=CONF_HIGH, reasons=[], variants=len(hits),
                defaulted_columns=defaults_by_id.get(clip_id, []),
            ))
        else:
            best = max(hits, key=lambda h: (h[1]["updated_at"] or ""))
            result.ambiguous.append(Candidate(
                clip_id=clip_id, row=best[1], locations=locations,
                confidence=CONF_AMBIGUOUS,
                reasons=[f"conflicting_row_images={len(identities)}"],
                variants=len(hits),
                defaulted_columns=defaults_by_id.get(clip_id, []),
            ))

    result.rejected = rejects
    return result


# --- event corroboration ----------------------------------------------------


def corroborate(
    candidates: Sequence[Candidate], events_by_clip: dict[str, list[dict]],
) -> dict:
    """Cross-check candidates against surviving event rows.

    Corroboration only ever *raises* confidence in an already-valid candidate;
    it never fills in a missing or invalid field.
    """
    corroborated = 0
    timestamp_agree = 0
    source_agree = 0
    classification_agree = 0
    conflicts: list[str] = []

    for cand in candidates:
        events = events_by_clip.get(cand.clip_id) or []
        if not events:
            continue
        corroborated += 1
        cand.corroborating_events = [e["id"] for e in events][:50]

        captured = next((e for e in events if e["event_type"] == models.EVENT_CAPTURED), None)
        if captured:
            if captured.get("created_at") and cand.row.get("created_at"):
                if captured["created_at"][:19] == cand.row["created_at"][:19]:
                    timestamp_agree += 1
            details = captured.get("details") or {}
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except ValueError:
                    details = {}
            if details.get("source_app") and cand.row.get("source_app"):
                if details["source_app"] == cand.row["source_app"]:
                    source_agree += 1
                else:
                    conflicts.append(f"{cand.clip_id}:source_app")
            if details.get("classification") and cand.row.get("classification"):
                if details["classification"] == cand.row["classification"]:
                    classification_agree += 1
                else:
                    conflicts.append(f"{cand.clip_id}:classification")

    return {
        "candidates": len(candidates),
        "event_corroborated": corroborated,
        "captured_timestamp_agree": timestamp_agree,
        "source_app_agree": source_agree,
        "classification_agree": classification_agree,
        "conflicts": conflicts,
    }
