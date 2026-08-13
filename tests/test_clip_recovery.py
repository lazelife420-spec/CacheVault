"""Focused tests for the freelist decoder and recovery engine.

Covers:
- serial_type_size edge cases
- Header parsing
- Freelist walk consistency
- Record decoding (SQLite cell format)
- validate_row: correct clips pass, malformed ones fail with reasons
- Migration-aware column defaults
- Census accounting (no silent drops)
- Corroboration logic
"""
from __future__ import annotations

import json
import pytest
import sqlite3
import struct
import tempfile
from pathlib import Path
from unittest import mock

from cache_vault.core import clip_recovery as cr, models


# ------------------------------------------------------------------
# serial_type_size
# ------------------------------------------------------------------
class TestSerialTypeSize:
    def test_nulls_and_constants(self):
        assert cr.serial_type_size(0) == 0
        assert cr.serial_type_size(8) == 0
        assert cr.serial_type_size(9) == 0
        assert cr.serial_type_size(10) == 0
        assert cr.serial_type_size(11) == 0

    def test_small_ints(self):
        assert cr.serial_type_size(1) == 1
        assert cr.serial_type_size(2) == 2
        assert cr.serial_type_size(3) == 3
        assert cr.serial_type_size(4) == 4

    def test_big_ints(self):
        assert cr.serial_type_size(5) == 6
        assert cr.serial_type_size(6) == 8
        assert cr.serial_type_size(7) == 8

    def test_blob_and_text_even(self):
        assert cr.serial_type_size(12) == 0  # blob length 0
        assert cr.serial_type_size(14) == 1  # blob length 1
        assert cr.serial_type_size(24) == 6  # blob length 6

    def test_blob_odd(self):
        assert cr.serial_type_size(13) == 0   # text length 0
        assert cr.serial_type_size(15) == 1   # text length 1
        assert cr.serial_type_size(25) == 6   # text length 6


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
class TestHeader:
    def test_valid_header(self):
        raw = make_db(page_count=2)
        h = cr.read_header(raw)
        assert h.page_size == 4096
        assert h.page_count == 2
        assert h.freelist_head == 0
        assert h.freelist_count == 0

    def test_rejects_non_sqlite(self):
        with pytest.raises(ValueError, match="not a SQLite"):
            cr.read_header(b"x" * 200)

    def test_missing_header(self):
        with pytest.raises(ValueError, match="not a SQLite"):
            cr.read_header(b"\x00" * 100)

    def test_page_size_one_maps_to_65536(self):
        raw = bytearray(make_db(page_count=1))
        struct.pack_into(">H", raw, 16, 1)  # set page_size=1
        h = cr.read_header(bytes(raw))
        assert h.page_size == 65536


# ------------------------------------------------------------------
# Freelist walk
# ------------------------------------------------------------------
class TestFreelistWalk:
    def test_empty_freelist(self):
        raw = make_db(page_specs={})
        h = cr.read_header(raw)
        scan = cr.scan_freelist(raw, h)
        assert scan.consistent is True
        assert scan.total == 0

    def test_single_trunk_no_leaves(self):
        trunk = bytearray(4096)
        struct.pack_into(">I", trunk, 0, 0)   # next = 0
        struct.pack_into(">I", trunk, 4, 0)   # n_leaves = 0
        raw = make_db(page_specs={2: bytes(trunk)}, freelist_head=2, freelist_count=1)
        h = cr.read_header(raw)
        scan = cr.scan_freelist(raw, h)
        assert scan.consistent is True
        assert scan.trunk_pages == [2]
        assert scan.leaf_pages == []

    def test_trunk_with_leaves(self):
        trunk = bytearray(4096)
        struct.pack_into(">I", trunk, 0, 0)   # next = 0
        struct.pack_into(">I", trunk, 4, 3)   # n_leaves = 3
        struct.pack_into(">I", trunk, 8, 10)
        struct.pack_into(">I", trunk, 12, 20)
        struct.pack_into(">I", trunk, 16, 30)
        raw = make_db(page_specs={2: bytes(trunk)}, freelist_head=2, freelist_count=4, page_count=31)
        h = cr.read_header(raw)
        scan = cr.scan_freelist(raw, h)
        assert scan.consistent is True
        assert scan.trunk_pages == [2]
        assert scan.leaf_pages == [10, 20, 30]

    def test_cycle_detected(self):
        trunk = bytearray(4096)
        struct.pack_into(">I", trunk, 0, 2)   # next = self (cycle at page 2)
        struct.pack_into(">I", trunk, 4, 0)
        raw = make_db(page_specs={2: bytes(trunk)}, freelist_head=2, freelist_count=100)
        h = cr.read_header(raw)
        scan = cr.scan_freelist(raw, h)
        assert scan.trunk_pages == [2]  # enters, detects cycle, stops


# ------------------------------------------------------------------
# Record decoding
# ------------------------------------------------------------------
class TestDecodeRecord:
    def test_null_value(self):
        # Use the real encoder: [None] → serial=0, no body
        payload = _encode_sqlite_record([None])
        vals = cr.decode_record(payload)
        assert vals == [None]

    def test_integer_small(self):
        # header_len=2, serial=1 (1-byte int), value=42
        payload = b"\x02\x01\x2A"
        vals = cr.decode_record(payload)
        assert vals == [42]

    def test_integer_big(self):
        # header_len=2, serial=6 (8-byte int), value=0x1234567890AB
        payload = b"\x02\x06" + struct.pack(">q", 0x1234567890AB)
        vals = cr.decode_record(payload)
        assert vals == [0x1234567890AB]

    def test_float(self):
        # header_len=2, serial=7, float=3.14
        payload = b"\x02\x07" + struct.pack(">d", 3.14)
        vals = cr.decode_record(payload)
        assert abs(vals[0] - 3.14) < 0.0001

    def test_text(self):
        # header_len=2, serial=odd (text), value="hello"
        data = b"hello"
        serial = 12 + len(data) * 2 + 1  # text
        payload = b"\x02" + bytes([serial]) + data
        vals = cr.decode_record(payload)
        assert vals == ["hello"]

    def test_blob(self):
        # header_len=2, serial=even (blob), value=b"\xDE\xAD"
        data = b"\xDE\xAD"
        serial = 12 + len(data) * 2  # blob
        payload = b"\x02" + bytes([serial]) + data
        vals = cr.decode_record(payload)
        assert vals == [data]

    def test_false_true(self):
        # false(8), true(9)
        payload = b"\x03\x08\x09"
        vals = cr.decode_record(payload)
        assert vals == [0, 1]

    def test_multiple_values(self):
        # null, 42, "hi"
        payload = _encode_sqlite_record([None, 42, "hi"])
        vals = cr.decode_record(payload)
        assert vals == [None, 42, "hi"]

    def test_rejects_truncated(self):
        # header_len=16 but only 2 bytes total → second serial type read fails
        assert cr.decode_record(b"\x10\x00") is None
        # header_len=2 with a serial that needs body bytes, but body is missing
        assert cr.decode_record(b"\x02\x04") is None
        # only 1 byte total — can't read header len at all
        assert cr.decode_record(b"\x10") is None

    def test_rejects_invalid_utf8(self):
        # text serial with invalid UTF-8 bytes
        data = b"\xFF\xFE"
        serial = 12 + len(data) * 2 + 1
        payload = b"\x02" + bytes([serial]) + data
        assert cr.decode_record(payload) is None

    def test_rejects_truncated_body(self):
        # serial=5 (6-byte int) but only 2 bytes available
        payload = b"\x02\x05\xAB\xCD"
        assert cr.decode_record(payload) is None


# ------------------------------------------------------------------
# validate_row
# ------------------------------------------------------------------
class TestValidateRow:
    def _make_row(self, **overrides):
        """Build a complete 29-column row dict with valid defaults."""
        base = {
            "id": "a" * 32,
            "created_at": "2024-06-15T10:30:00+00:00",
            "updated_at": "2024-06-15T10:30:00+00:00",
            "content_hash": "b" * 32,
            "content_type": models.CONTENT_TEXT,
            "content": "test content",
            "preview": "test content",
            "source_app": "test.exe",
            "source_window": "Test Window",
            "classification": models.CLASS_PLAIN,
            "tags": json.dumps(["tag1", "tag2"]),
            "is_pinned": 0,
            "is_kept": 0,
            "is_sensitive": 0,
            "expires_at": None,
            "deleted_at": None,
            "duplicate_of": None,
            "collection": None,
            "title": None,
            "source_url": None,
            "normalized_hash": None,
            "size_bytes": 0,
            "last_used_at": None,
            "use_count": 0,
            "copied_count": 0,
            "safe_id": "default",
            "safe_name": "Default Safe",
            "capture_mode": models.CAPTURE_AUTO,
            "is_saved_to_phone": 0,
        }
        base.update(overrides)
        return list(base.values())

    def test_valid_row_passes(self):
        row, reasons, defaulted = cr.validate_row(self._make_row())
        assert row is not None
        assert reasons == []
        assert defaulted == []

    def test_bad_id_rejected(self):
        row, reasons, defaulted = cr.validate_row(self._make_row(id="not-hex"))
        assert row is None
        assert "id_shape_invalid" in reasons

    def test_wrong_column_count(self):
        row, reasons, defaulted = cr.validate_row(["x"] * 10)
        assert row is None
        assert "below_min" in reasons[0]

    def test_exceeds_max_columns(self):
        row, reasons, defaulted = cr.validate_row(["x"] * 100)
        assert row is None
        assert "exceeds" in reasons[0]

    def test_bad_content_type(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(content_type="pdf"))
        assert row is not None
        assert "content_type_unknown" in reasons

    def test_bad_classification(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(classification="pdf"))
        assert row is not None
        assert "classification_unknown" in reasons

    def test_bad_capture_mode(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(capture_mode="telepathy"))
        assert row is not None
        assert "capture_mode_unknown" in reasons

    def test_bad_timestamp(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(created_at="not-a-date"))
        assert row is not None
        assert "created_at_invalid" in reasons

    def test_implausible_timestamp(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(created_at="2001-01-01T00:00:00+00:00"))
        assert row is not None
        assert "created_at_invalid" in reasons

    def test_non_boolean_flags(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(is_pinned=42))
        assert row is not None
        assert "is_pinned_not_boolean" in reasons

    def test_negative_size_bytes(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(size_bytes=-1))
        assert row is not None
        assert "size_bytes_invalid" in reasons

    def test_tags_not_json(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(tags="not-json"))
        assert row is not None
        assert "tags_not_json" in reasons

    def test_tags_not_list(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(tags='"not a list"'))
        assert row is not None
        assert "tags_not_list" in reasons

    def test_duplicate_of_self(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(duplicate_of="a" * 32))
        assert row is not None
        assert "duplicate_of_self" in reasons

    def test_image_with_link_classification(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(content_type=models.CONTENT_IMAGE,
                           classification=models.CLASS_LINK))
        assert row is not None
        assert "image_content_type_conflicts_classification" in reasons

    def test_source_app_with_control_chars(self):
        row, reasons, defaulted = cr.validate_row(
            self._make_row(source_app="bad\x00app"))
        assert row is not None
        assert "source_app_implausible" in reasons

    # Migration-aware tests

    def test_28_columns_with_defaults(self):
        """Pre-migration row: 28 columns, defaults fill capture_mode(28)."""
        vals = self._make_row()
        vals_28 = vals[:28]
        assert len(vals_28) == 28
        row, reasons, defaulted = cr.validate_row(vals_28)
        assert row is not None
        assert reasons == []
        assert "is_saved_to_phone" in defaulted
        assert row["is_saved_to_phone"] == 0  # declared default

    def test_25_columns_with_defaults(self):
        """Pre-migration row: 25 columns."""
        vals = self._make_row()
        vals_25 = vals[:25]
        row, reasons, defaulted = cr.validate_row(vals_25)
        assert row is not None
        assert row["safe_id"] == "default"
        assert row["safe_name"] == "Default Safe"
        assert row["capture_mode"] == "auto"
        assert row["is_saved_to_phone"] == 0

    def test_18_columns_still_passes(self):
        """Original shipped schema (18 col) gets extended defaults."""
        vals = self._make_row()
        vals_18 = vals[:18]
        row, reasons, defaulted = cr.validate_row(vals_18)
        assert row is not None
        assert len(defaulted) == 11  # 29 - 18
        assert "title" in defaulted
        assert "source_url" in defaulted

    def test_17_columns_rejected(self):
        """Below the original shipped schema (18)."""
        vals = self._make_row()
        vals_17 = vals[:17]
        row, reasons, defaulted = cr.validate_row(vals_17)
        assert row is None
        assert "below_min=18" in reasons[0]


# ------------------------------------------------------------------
# Census accounting
# ------------------------------------------------------------------
class TestCensusAccounting:
    def test_every_decode_accounted(self):
        """With a synthetic DB containing known rows, the census must balance."""
        # Create a 2-page DB with a known clip row, then free the page
        raw, expected = make_synthetic_db_with_freed_clip()
        res = cr.recover_candidates(raw)
        assert res.accounted is True
        assert res.records_decoded == len(res.high) + len(res.ambiguous) + len(res.rejected) + sum(res.discarded.values())

    def test_clip_assets_row_is_discarded(self):
        """A freed 'clip_assets' row (11 cols) is discarded, not silently dropped."""
        raw, _ = make_synthetic_db_with_freed_assets_row()
        res = cr.recover_candidates(raw)
        assert res.accounted is True
        assert res.discarded.get("column_count=11 below_min=18", 0) >= 1


# ------------------------------------------------------------------
# Corroboration
# ------------------------------------------------------------------
class TestCorroboration:
    def test_empty_events(self):
        cand = cr.Candidate(clip_id="a" * 32, confidence=cr.CONF_HIGH, reasons=[],
                            row={"created_at": "", "source_app": "", "classification": ""}, locations=[])
        result = cr.corroborate([cand], {})
        assert result["event_corroborated"] == 0
        assert result["conflicts"] == []

    def test_corroborated(self):
        cand = cr.Candidate(
            clip_id="abc", confidence=cr.CONF_HIGH, reasons=[],
            row={"created_at": "2024-06-15T10:30:00+00:00", "source_app": "test.exe", "classification": "plain"},
            locations=[],
        )
        events = {
            "abc": [
                {
                    "id": 1,
                    "event_type": models.EVENT_CAPTURED,
                    "created_at": "2024-06-15T10:30:00+00:00",
                    "details": json.dumps({"source_app": "test.exe", "classification": "plain"}),
                }
            ]
        }
        result = cr.corroborate([cand], events)
        assert result["event_corroborated"] == 1
        assert result["captured_timestamp_agree"] == 1
        assert result["source_app_agree"] == 1
        assert result["classification_agree"] == 1
        assert result["conflicts"] == []

    def test_source_app_mismatch(self):
        cand = cr.Candidate(
            clip_id="abc", confidence=cr.CONF_HIGH, reasons=[],
            row={"created_at": "", "source_app": "brave.exe", "classification": ""},
            locations=[],
        )
        events = {
            "abc": [
                {
                    "id": 1,
                    "event_type": models.EVENT_CAPTURED,
                    "details": json.dumps({"source_app": "chrome.exe"}),
                }
            ]
        }
        result = cr.corroborate([cand], events)
        assert "abc:source_app" in result["conflicts"]


# ------------------------------------------------------------------
# Synthetic DB builders
# ------------------------------------------------------------------

def _build_sqlite_header(page_size=4096, page_count=1, freelist_head=0, freelist_count=0):
    """Build a valid 100-byte SQLite database header."""
    header = bytearray(100)
    header[0:16] = b"SQLite format 3\x00"
    struct.pack_into(">H", header, 16, page_size if page_size != 65536 else 1)
    header[18] = 1  # write version
    header[19] = 1  # read version
    header[20] = 32  # reserved space
    header[21] = 32  # max embedded payload fraction
    header[22] = 32  # min embedded payload fraction
    header[23] = 32  # leaf payload fraction
    struct.pack_into(">I", header, 28, page_count)
    struct.pack_into(">I", header, 32, freelist_head)
    struct.pack_into(">I", header, 36, freelist_count)
    return bytes(header)


def make_db(page_specs=None, freelist_head=0, freelist_count=0, page_count=None):
    """Build a synthetic SQLite file image.

    *page_specs* is a dict ``{page_no: bytes}`` for explicit page content.
    Pages not listed are zero-filled to 4096 bytes.

    The DB header is embedded in the first 100 bytes of page 1, matching
    SQLite's on-disk layout where page 1 starts at file offset 0.
    """
    if page_specs is None:
        page_specs = {}
    if page_count is None:
        page_count = max(list(page_specs.keys()) or [0]) + 1
    header = _build_sqlite_header(page_count=page_count,
                                   freelist_head=freelist_head,
                                   freelist_count=freelist_count)
    # Page 1: header (100 bytes) + remainder from page_specs (or zeros)
    p1 = bytearray(header)
    p1_user = page_specs.get(1, b"")
    if len(p1_user) > 0:
        # overlay user content after the 100-byte header
        overlay = p1_user[:4096 - 100]
        p1[100:100 + len(overlay)] = overlay
    if len(p1) < 4096:
        p1.extend(b"\x00" * (4096 - len(p1)))
    raw = bytes(p1)

    for i in range(2, page_count + 1):
        page_data = page_specs.get(i, b"\x00" * 4096)
        if len(page_data) < 4096:
            page_data = page_data + b"\x00" * (4096 - len(page_data))
        elif len(page_data) > 4096:
            page_data = page_data[:4096]
        raw += page_data
    return raw


def _encode_varint(value: int) -> bytes:
    """Encode an integer as a SQLite varint."""
    if value < 0:
        value &= 0xFFFFFFFFFFFFFFFF  # unsigned
    buf = bytearray()
    for _ in range(9):
        buf.append((value & 0x7F) | (0x80 if value >= 0x80 else 0x00))
        value >>= 7
        if not value:
            break
    return bytes(buf)


def _encode_sqlite_record(values: list) -> bytes:
    """Encode a list of python values into a SQLite record body."""
    serials = []
    body = bytearray()
    for v in values:
        if v is None:
            serials.append(0)
        elif isinstance(v, bool):
            serials.append(9 if v else 8)
        elif isinstance(v, int):
            uval = v
            if uval < 0:
                uval = (1 << 64) + uval  # two's complement for range checks
            if -128 <= v <= 127:
                serials.append(1)
                body.append(v & 0xFF)
            elif -32768 <= v <= 32767:
                serials.append(2)
                body.extend(struct.pack(">h", v))
            elif -8388608 <= v <= 8388607:
                serials.append(3)
                body.extend(struct.pack(">i", v)[1:])
            elif -2147483648 <= v <= 2147483647:
                serials.append(4)
                body.extend(struct.pack(">i", v))
            elif -140737488355328 <= v <= 140737488355327:
                serials.append(5)
                body.extend(struct.pack(">q", v)[2:])
            else:
                serials.append(6)
                body.extend(struct.pack(">q", v))
        elif isinstance(v, float):
            serials.append(7)
            body.extend(struct.pack(">d", v))
        elif isinstance(v, str):
            data = v.encode("utf-8")
            serials.append(12 + len(data) * 2 + 1)
            body.extend(data)
        elif isinstance(v, bytes):
            serials.append(12 + len(v) * 2)
            body.extend(v)
        else:
            serials.append(0)
    # build header: varints for each serial type
    serials_bytes = b"".join(_encode_varint(s) for s in serials)
    # header length = 1 (for the header-length varint itself) + len(serials_bytes)
    header_len = 1 + len(serials_bytes)
    return _encode_varint(header_len) + serials_bytes + bytes(body)


def _make_table_leaf_page(cells: list[bytes], page_no=1) -> bytes:
    """Build a minimal table-leaf page with the given cells."""
    page = bytearray(4096)
    page[0] = cr.TABLE_LEAF
    n_cells = len(cells)
    struct.pack_into(">H", page, 3, n_cells)
    cell_offsets = []
    cell_bytes_list = []
    total = 8 + 2 * n_cells
    for cell_body in cells:
        # payload_len varint + rowid varint + record body
        payload_len_enc = _encode_varint(len(cell_body))
        rowid_enc = _encode_varint(1)
        cell = payload_len_enc + rowid_enc + cell_body
        cell_offsets.append(total)
        cell_bytes_list.append(cell)
        total += len(cell)
    for i, off in enumerate(cell_offsets):
        struct.pack_into(">H", page, 8 + 2 * i, off)
        cell = cell_bytes_list[i]
        page[off:off + len(cell)] = cell
    return bytes(page)


def make_synthetic_db_with_freed_clip():
    """Create a DB where page 3 is a freed leaf containing a valid clip row.
    Uses pages 2 (trunk) and 3 (leaf) to avoid the DB header at page 1 offset 0.
    """
    row_values = [
        "a" * 32,                         # id (0)
        "2024-06-15T10:30:00+00:00",     # created_at (1)
        "2024-06-15T10:30:00+00:00",     # updated_at (2)
        "b" * 64,                         # content_hash (3)
        "text",                           # content_type (4)
        "hello world",                    # content (5)
        "hello world",                    # preview (6)
        "test.exe",                       # source_app (7)
        "Test Window",                    # source_window (8)
        "plain",                          # classification (9)
        json.dumps(["tag"]),              # tags (10)
        0, 0, 0,                          # is_pinned (11), is_kept (12), is_sensitive (13)
        None, None, None,                 # expires_at (14), deleted_at (15), duplicate_of (16)
        None, None, None, None, None,     # collection (17), title (18), source_url (19), normalized_hash (20), size_bytes (21)
        None,                             # last_used_at (22)
        0, 0,                             # use_count (23), copied_count (24)
        "default", "Default Safe", "auto", 0,  # safe_id (25), safe_name (26), capture_mode (27), is_saved_to_phone (28)
    ]
    assert len(row_values) == 29, f"Expected 29 columns, got {len(row_values)}"
    rec = _encode_sqlite_record(row_values)
    leaf = _make_table_leaf_page([rec])
    trunk = bytearray(4096)
    struct.pack_into(">I", trunk, 0, 0)   # next = 0
    struct.pack_into(">I", trunk, 4, 1)   # n_leaves = 1
    struct.pack_into(">I", trunk, 8, 3)   # leaf = page 3
    raw = make_db(page_specs={2: bytes(trunk), 3: leaf}, freelist_head=2, freelist_count=2, page_count=3)
    return raw, row_values


def make_synthetic_db_with_freed_assets_row():
    """Create a DB where a freed page contains an 11-column clip_assets row."""
    vals = ["asset_001", "clip_" + "a" * 32, "image/png", "storage_" + "a" * 32, 12345,
            0, None, None, None, None, None]
    rec = _encode_sqlite_record(vals)
    leaf = _make_table_leaf_page([rec])
    trunk = bytearray(4096)
    struct.pack_into(">I", trunk, 0, 0)
    struct.pack_into(">I", trunk, 4, 1)
    struct.pack_into(">I", trunk, 8, 3)
    raw = make_db(page_specs={2: bytes(trunk), 3: leaf}, freelist_head=2, freelist_count=2, page_count=3)
    return raw, vals
