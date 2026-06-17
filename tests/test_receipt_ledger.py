"""Stamped Receipts proof ledger parsing and export."""

from __future__ import annotations

import json

from cache_vault import brand
from cache_vault.core import models
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui.receipt_ledger import (
    export_rows,
    filter_rows,
    format_detail_text,
    humanize_action,
    parse_legacy_line,
    rows_from_events,
    shorten_hash,
)


def test_humanize_action_names():
    assert humanize_action("captured") == "Captured Clip"
    assert humanize_action("copied_again") == "Copied Again"
    assert humanize_action("exported") == "Exported"
    assert humanize_action("get_asset") == "Asset Requested"
    assert humanize_action("weird_unknown_thing") == "Weird Unknown Thing"


def test_shorten_hash():
    h = "e343abcd5339deadbeef"
    assert shorten_hash(h) == "e343…dbeef"
    assert shorten_hash("short") == "short"


def test_parse_legacy_line():
    raw = "2026-06-16 01:52:45 captured e343abcd5339d"
    parsed = parse_legacy_line(raw)
    assert parsed is not None
    assert parsed["event_type"] == "captured"
    assert parsed["_legacy"] is True


def test_legacy_line_does_not_crash_viewer_pipeline():
    raw = "not a valid receipt line at all ???"
    assert parse_legacy_line(raw) is None
    event = parse_legacy_line("2026-06-16 01:52:45 copied_again clip1hash")
    rows = rows_from_events([event])
    assert len(rows) == 1
    assert rows[0].legacy is True


def test_event_rows_from_vault():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    clip = vault.capture("hello receipt test", source_app="test")
    events = vault.events.recent()
    rows = rows_from_events(events, get_clip=vault.storage.get_clip)
    assert len(rows) >= 1
    cap = next(r for r in rows if r.action_raw == models.EVENT_CAPTURED)
    assert cap.action_label == "Captured Clip"
    assert cap.result == "Success"
    assert "…" in shorten_hash(cap.proof_hash) or len(cap.proof_hash) <= 12
    vault.close()


def test_receipt_details_no_sensitive_content():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    vault.settings.block_sensitive_auto_capture = False
    secret = vault.capture("sk-abc123DEF456ghi789JKL0", source_app="test")
    rows = rows_from_events(
        vault.events.recent(), get_clip=vault.storage.get_clip)
    row = next(r for r in rows if r.clip_id == secret.id)
    detail = format_detail_text(row)
    assert "sk-abc123DEF456" not in detail
    assert "sensitive" in (row.preview or "").lower() or row.preview is None
    vault.close()


def test_receipt_details_no_plaintext_tokens():
    event = {
        "id": "evt-1",
        "created_at": "2026-06-16T01:00:00+00:00",
        "event_type": "copy",
        "clip_id": "clip-1",
        "details": {"token": "secret-bearer", "result": "ok"},
    }
    rows = rows_from_events([event])
    detail = format_detail_text(rows[0])
    assert "secret-bearer" not in detail


def test_export_includes_branding():
    from cache_vault.ui.receipt_ledger import ReceiptRow

    row = ReceiptRow(
        receipt_id="r1",
        timestamp="2026-06-16T01:00:00+00:00",
        action_raw="captured",
        action_label="Captured Clip",
        item_label="Text clip",
        content_type="TEXT",
        result="Success",
        proof_hash="abc123def456",
    )
    txt = export_rows([row], "txt")
    assert brand.PRODUCT_NAME in txt
    assert brand.STUDIO_FOOTER in txt
    js = export_rows([row], "json")
    data = json.loads(js)
    assert data["product"] == brand.PRODUCT_NAME
    html = export_rows([row], "html")
    assert brand.PRODUCT_NAME in html


def test_export_json_no_token_field():
    from cache_vault.ui.receipt_ledger import ReceiptRow

    row = ReceiptRow(
        receipt_id="r1",
        timestamp="2026-06-16T01:00:00+00:00",
        action_raw="copy",
        action_label="Copy Requested",
        item_label="Text clip",
        content_type="TEXT",
        result="Success",
        proof_hash="abc",
        details={"token": "hidden"},
    )
    js = export_rows([row], "json")
    assert "hidden" not in js
    assert "token" not in js.lower()


def test_filter_search_by_action():
    from cache_vault.ui.receipt_ledger import ReceiptRow, FILTER_EXPORTS

    rows = [
        ReceiptRow("1", "2026-01-01T00:00:00+00:00", "captured", "Captured Clip",
                   "Text clip", "TEXT", "Success", "hash1"),
        ReceiptRow("2", "2026-01-01T00:00:00+00:00", "exported", "Exported",
                   "Export", "—", "Success", "hash2"),
    ]
    exports = filter_rows(rows, flt=FILTER_EXPORTS)
    assert len(exports) == 1
    assert exports[0].action_raw == "exported"


def test_empty_receipt_filter():
    from cache_vault.ui.receipt_ledger import FILTER_ALL
    assert filter_rows([], flt=FILTER_ALL) == []
