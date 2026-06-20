"""Smart folder grouping — deterministic filters and receipts."""

from __future__ import annotations

from cache_vault.core import models, smart_folders
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


def _seed_vault() -> Vault:
    vault = Vault(storage=VaultStorage(":memory:"))
    vault.capture("hello plain text", source_app="Notepad", force=True)
    vault.capture(
        "https://example.com/docs",
        source_app="Chrome",
        force=True,
    )
    vault.capture(
        "def main():\n    return 42\n",
        source_app="Cursor",
        force=True,
    )
    vault.storage.conn.execute(
        "UPDATE clips SET capture_mode = ?, use_count = 0 WHERE content LIKE 'hello%'",
        (models.CAPTURE_MOBILE_SHARE,),
    )
    vault.storage.conn.commit()
    return vault


def test_smart_folder_nav_has_eight_entries():
    assert len(smart_folders.SMART_FOLDER_NAV) == 8
    keys = [k for k, _ in smart_folders.SMART_FOLDER_NAV]
    assert all(k.startswith(smart_folders.SMART_PREFIX) for k in keys)


def test_list_clips_by_smart_folder():
    vault = _seed_vault()
    mobile = vault.list_clips(smart_folders.filter_key("mobile_share"))
    assert len(mobile) == 1
    urls = vault.list_clips(smart_folders.filter_key("url"))
    assert len(urls) == 1
    code = vault.list_clips(smart_folders.filter_key("code"))
    assert len(code) == 1


def test_counts_include_smart_folders():
    vault = _seed_vault()
    counts = vault.counts()
    assert counts[smart_folders.filter_key("mobile_share")] == 1
    assert counts[smart_folders.filter_key("url")] == 1


def test_folder_receipt_has_timestamp_and_count():
    receipt = smart_folders.folder_receipt("recent", 5)
    assert receipt["count"] == 5
    assert receipt["generated_at"]
    assert receipt["label"] == "Recent"
    assert receipt["receipt_type"] == "smart_folder_snapshot"


def test_all_folder_receipts_bundle():
    vault = _seed_vault()
    bundle = smart_folders.all_folder_receipts(vault.storage)
    assert bundle["receipt_type"] == "smart_folder_bundle"
    assert len(bundle["folders"]) == 8
    assert bundle["generated_at"]


def test_export_collection_name_for_smart_filter():
    key = smart_folders.filter_key("code")
    assert smart_folders.export_collection_name(key) == "Smart Folder — Code"
