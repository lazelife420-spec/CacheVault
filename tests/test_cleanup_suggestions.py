"""Stage A tests: the read-only Vault Cleanup Suggestions scan engine.

No UI, no mutation -- these only prove the detectors, managed-asset
boundary, protection rules, and fingerprint stability.
"""

from __future__ import annotations

import pytest

from cache_vault.core import cleanup_suggestions as cs
from cache_vault.core import image_assets, models
from cache_vault.core.models import Clip
from cache_vault.core.storage import VaultStorage


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _add_image_clip(
    storage: VaultStorage,
    *,
    data: bytes,
    width: int,
    height: int,
    is_pinned: bool = False,
    collection: str | None = None,
    created_at: str | None = None,
    last_used_at: str | None = None,
    source_app: str | None = "test.exe",
    write_file: bool = True,
) -> Clip:
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash,
        content_type=models.CONTENT_IMAGE,
        content="[Screenshot PNG]",
        preview="Screenshot",
        classification=models.CLASS_IMAGE,
        source_app=source_app,
        is_pinned=is_pinned,
        collection=collection,
        size_bytes=len(data),
    )
    if created_at:
        clip.created_at = created_at
    if last_used_at:
        clip.last_used_at = last_used_at
    storage.add_clip(clip)

    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(),
        clip_id=clip.id,
        mime_type="image/png",
        file_ext="png",
        size_bytes=len(data),
        sha256=chash,
        created_at=clip.created_at,
        original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"),
        width=width,
        height=height,
    )
    if write_file:
        storage.save_clip_asset(record, data)
    else:
        # Insert the DB row without writing the file -- simulates a
        # missing-asset scenario.
        storage.conn.execute(
            """INSERT INTO clip_assets (
                asset_id, clip_id, mime_type, file_ext, size_bytes, sha256,
                created_at, original_name, storage_name, width, height
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.asset_id, record.clip_id, record.mime_type, record.file_ext,
                record.size_bytes, record.sha256, record.created_at,
                record.original_name, record.storage_name, record.width, record.height,
            ),
        )
        storage.conn.commit()
    return clip


def _add_text_clip(
    storage: VaultStorage,
    *,
    content: str,
    is_pinned: bool = False,
    collection: str | None = None,
    created_at: str | None = None,
) -> Clip:
    clip = Clip(
        content_hash=models.content_hash(content),
        content_type=models.CONTENT_TEXT,
        content=content,
        preview=content[:100],
        classification=models.CLASS_PLAIN,
        is_pinned=is_pinned,
        collection=collection,
        size_bytes=len(content.encode("utf-8")),
    )
    if created_at:
        clip.created_at = created_at
    storage.add_clip(clip)
    return clip


def _add_path_only_image_reference(storage: VaultStorage, *, path: str) -> Clip:
    """A copied file path ending in an image extension -- CacheVault owns no
    bytes for this. Must never appear in any managed-asset category.
    """
    clip = Clip(
        content_hash=models.content_hash(path),
        content_type=models.CONTENT_TEXT,
        content=path,
        preview=path,
        classification=models.CLASS_PATH,
    )
    storage.add_clip(clip)
    return clip


def _tiny_png(color=(255, 0, 0)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


# --- managed-asset boundary ---------------------------------------------------


def test_path_only_image_reference_excluded_from_duplicate_screenshots(storage, assets_home):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\shot.png")

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)

    assert len(groups) == 1
    assert groups[0].count == 2  # the path-only reference never joins the group


def test_path_only_image_reference_excluded_from_tiny_images(storage, assets_home):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\icon.jpg")

    ctx = cs.build_scan_context(storage)
    tiny = cs.find_tiny_images(ctx)

    assert len(tiny) == 1
    assert tiny[0].clip.content_type == models.CONTENT_IMAGE


def test_path_only_image_reference_excluded_from_missing_assets(storage, assets_home):
    # A path-only reference to a file that doesn't exist on disk must NOT be
    # reported as a "missing managed asset" -- CacheVault never owned it.
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\gone.png")

    ctx = cs.build_scan_context(storage)
    missing = cs.find_missing_or_damaged_assets(ctx)

    assert missing == []


def test_path_only_image_reference_excluded_from_largest_assets(storage, assets_home):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\huge.png")

    ctx = cs.build_scan_context(storage)
    largest = cs.find_largest_assets(ctx)

    assert len(largest) == 1
    assert largest[0].clip.content_type == models.CONTENT_IMAGE


def test_path_only_image_reference_excluded_from_repeated_text_uses_own_rule(storage):
    # Path-only image references ARE text clips (classification=path), but
    # they must not be double-counted as "repeated text" duplicates of an
    # unrelated managed image -- Category B only groups clips that aren't
    # managed assets, which a path-only reference correctly is not.
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\a.png")
    _add_path_only_image_reference(storage, path=r"C:\Users\me\Downloads\a.png")

    ctx = cs.build_scan_context(storage)
    groups = cs.find_repeated_text_groups(ctx)

    assert len(groups) == 1  # the two identical path strings DO group as text
    assert groups[0].category == cs.CATEGORY_REPEATED_TEXT


# --- Category A: exact duplicate screenshots ----------------------------------


def test_duplicate_screenshot_grouping_by_exact_hash(storage, assets_home):
    data_a = _tiny_png((255, 0, 0))
    data_b = _tiny_png((0, 255, 0))
    _add_image_clip(storage, data=data_a, width=4, height=4)
    _add_image_clip(storage, data=data_a, width=4, height=4)
    _add_image_clip(storage, data=data_a, width=4, height=4)
    _add_image_clip(storage, data=data_b, width=4, height=4)  # unique, no group

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)

    assert len(groups) == 1
    assert groups[0].count == 3


def test_duplicate_group_never_preselects_every_copy(storage, assets_home):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_image_clip(storage, data=data, width=4, height=4)

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    assert group.recommended_keeper_id is not None
    assert group.recommended_keeper_id not in group.preselectable_ids
    assert len(group.preselectable_ids) < group.count


def test_keeper_order_prefers_favorite(storage, assets_home):
    data = _tiny_png()
    plain = _add_image_clip(storage, data=data, width=4, height=4)
    fav = _add_image_clip(storage, data=data, width=4, height=4, is_pinned=True)

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    assert group.recommended_keeper_id == fav.id
    assert plain.id in group.preselectable_ids


def test_keeper_order_prefers_collection_over_recency(storage, assets_home):
    data = _tiny_png()
    newer_plain = _add_image_clip(storage, data=data, width=4, height=4, created_at="2026-01-02T00:00:00+00:00")
    older_in_collection = _add_image_clip(
        storage, data=data, width=4, height=4, collection="Work", created_at="2026-01-01T00:00:00+00:00",
    )

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    assert group.recommended_keeper_id == older_in_collection.id
    assert newer_plain.id in group.preselectable_ids


def test_protected_copies_never_preselected(storage, assets_home):
    data = _tiny_png()
    plain = _add_image_clip(storage, data=data, width=4, height=4)
    fav = _add_image_clip(storage, data=data, width=4, height=4, is_pinned=True)
    collected = _add_image_clip(storage, data=data, width=4, height=4, collection="Keep")

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    assert fav.id not in group.preselectable_ids
    assert collected.id not in group.preselectable_ids
    assert plain.id in group.preselectable_ids


def test_at_least_one_keeper_always_remains(storage, assets_home):
    data = _tiny_png()
    for _ in range(5):
        _add_image_clip(storage, data=data, width=4, height=4, is_pinned=True)

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    # Even when every copy is protected, exactly one keeper is designated and
    # never appears in the preselectable set.
    assert group.recommended_keeper_id is not None
    assert group.preselectable_ids == []


def test_redundant_bytes_identified_excludes_keeper(storage, assets_home):
    data = _tiny_png()
    size = len(data)
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_image_clip(storage, data=data, width=4, height=4)

    ctx = cs.build_scan_context(storage)
    group = cs.find_duplicate_screenshot_groups(ctx)[0]

    assert group.redundant_bytes == size * 2  # 3 copies, 1 kept, 2 redundant


def test_duplicate_group_membership_changes_fingerprint(storage, assets_home):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=4, height=4)
    _add_image_clip(storage, data=data, width=4, height=4)

    ctx1 = cs.build_scan_context(storage)
    fp_before = cs.find_duplicate_screenshot_groups(ctx1)[0].fingerprint

    _add_image_clip(storage, data=data, width=4, height=4)  # a third copy arrives

    ctx2 = cs.build_scan_context(storage)
    fp_after = cs.find_duplicate_screenshot_groups(ctx2)[0].fingerprint

    assert fp_before != fp_after


# --- Category B: exact repeated text clips ------------------------------------


def test_repeated_text_groups_identical_content(storage):
    _add_text_clip(storage, content="hello world")
    _add_text_clip(storage, content="hello world")
    _add_text_clip(storage, content="something else")

    ctx = cs.build_scan_context(storage)
    groups = cs.find_repeated_text_groups(ctx)

    assert len(groups) == 1
    assert groups[0].count == 2


def test_repeated_text_crlf_lf_treated_as_equivalent(storage):
    _add_text_clip(storage, content="line one\r\nline two")
    _add_text_clip(storage, content="line one\nline two")

    ctx = cs.build_scan_context(storage)
    groups = cs.find_repeated_text_groups(ctx)

    assert len(groups) == 1
    assert groups[0].count == 2


def test_repeated_text_does_not_ignore_arbitrary_whitespace(storage):
    _add_text_clip(storage, content="hello world")
    _add_text_clip(storage, content="hello world ")  # trailing space -- NOT equivalent
    _add_text_clip(storage, content="Hello World")  # different case -- NOT equivalent

    ctx = cs.build_scan_context(storage)
    groups = cs.find_repeated_text_groups(ctx)

    assert groups == []


def test_non_identical_text_never_grouped(storage):
    _add_text_clip(storage, content="the quick brown fox")
    _add_text_clip(storage, content="the quick brown fox jumps")  # similar, not identical

    ctx = cs.build_scan_context(storage)
    groups = cs.find_repeated_text_groups(ctx)

    assert groups == []


def test_repeated_text_protected_never_preselected(storage):
    plain = _add_text_clip(storage, content="dup")
    fav = _add_text_clip(storage, content="dup", is_pinned=True)

    ctx = cs.build_scan_context(storage)
    group = cs.find_repeated_text_groups(ctx)[0]

    assert fav.id not in group.preselectable_ids
    assert plain.id in group.preselectable_ids


# --- Category C: tiny-image threshold -----------------------------------------


@pytest.mark.parametrize(
    "width,height,expected",
    [
        (8, 8, True),
        (37, 29, True),
        (63, 63, True),
        (64, 64, False),   # exactly at threshold -- NOT flagged (strictly below)
        (64, 30, False),   # one dimension at threshold -- NOT flagged
        (100, 30, False),  # only one dimension small -- NOT flagged
    ],
)
def test_tiny_image_threshold_boundary(storage, assets_home, width, height, expected):
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=width, height=height)

    ctx = cs.build_scan_context(storage)
    tiny = cs.find_tiny_images(ctx)

    assert (len(tiny) == 1) == expected


def test_tiny_images_never_preselected_by_default(storage, assets_home):
    # Category C has no preselection concept at all -- it's a bare list.
    data = _tiny_png()
    _add_image_clip(storage, data=data, width=8, height=8)
    ctx = cs.build_scan_context(storage)
    tiny = cs.find_tiny_images(ctx)
    assert len(tiny) == 1
    assert tiny[0].protection.protected is False  # unprotected, but still not auto-selected by the engine


# --- Category D: missing/damaged assets ---------------------------------------


def test_missing_file_detected(storage, assets_home):
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4, write_file=False)

    ctx = cs.build_scan_context(storage)
    missing = cs.find_missing_or_damaged_assets(ctx)

    assert len(missing) == 1
    assert missing[0].clip.id == clip.id
    assert missing[0].asset_missing is True


def test_zero_byte_asset_detected(storage, assets_home):
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    # Overwrite the real file with zero bytes after the fact.
    row = storage.get_asset_record(clip.id)
    (image_assets.assets_dir() / row.storage_name).write_bytes(b"")

    ctx = cs.build_scan_context(storage)
    missing = cs.find_missing_or_damaged_assets(ctx)

    assert len(missing) == 1
    assert missing[0].asset_zero_byte is True


def test_corrupt_asset_detected(storage, assets_home):
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    row = storage.get_asset_record(clip.id)
    (image_assets.assets_dir() / row.storage_name).write_bytes(b"not a real png")

    ctx = cs.build_scan_context(storage)
    missing = cs.find_missing_or_damaged_assets(ctx)

    assert len(missing) == 1
    assert missing[0].asset_undecodable is True


def test_healthy_asset_not_flagged(storage, assets_home):
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    ctx = cs.build_scan_context(storage)
    assert cs.find_missing_or_damaged_assets(ctx) == []


def test_deep_validate_hash_mismatch(storage, assets_home):
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    row = storage.get_asset_record(clip.id)
    (image_assets.assets_dir() / row.storage_name).write_bytes(_tiny_png((0, 0, 255)))

    result = cs.deep_validate_asset(storage, clip.id)

    assert result["status"] == "hash_mismatch"


def test_default_scan_never_rehashes(storage, assets_home, monkeypatch):
    """The default missing/damaged scan must never recompute a SHA-256 over
    asset bytes -- only deep_validate_asset (explicit, user-invoked) does.
    """
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    _add_image_clip(storage, data=_tiny_png((0, 0, 255)), width=4, height=4)

    calls = []
    real_bytes_hash = models.bytes_hash

    def counting_bytes_hash(data):
        calls.append(data)
        return real_bytes_hash(data)

    monkeypatch.setattr(models, "bytes_hash", counting_bytes_hash)
    ctx = cs.build_scan_context(storage)
    cs.find_missing_or_damaged_assets(ctx)
    cs.find_duplicate_screenshot_groups(ctx)

    assert calls == []


def test_editable_copy_lookup_is_a_single_bulk_query_not_n_plus_one(storage, assets_home):
    """Regression for a real finding from independent review of draft PR
    #67: evaluate_protection/_keeper_sort_key each used to query
    editable_copies once per candidate item (measured at 1230 of 1233 total
    scan statements on a ~1855-clip fixture). run_scan() must issue exactly
    one query for it (_editable_copy_clip_ids), regardless of how many
    duplicate-screenshot items are being keeper-sorted.
    """
    data = _tiny_png()
    for _ in range(5):  # several items -> keeper sort runs _keeper_sort_key per item
        _add_image_clip(storage, data=data, width=4, height=4)

    queries = []

    def on_sql(stmt: str) -> None:
        if "editable_copies" in stmt:
            queries.append(stmt)

    storage.conn.set_trace_callback(on_sql)
    try:
        cs.run_scan(storage)
    finally:
        storage.conn.set_trace_callback(None)

    assert len(queries) == 1, f"expected exactly 1 editable_copies query, got {len(queries)}"


# --- Category E: largest managed assets ---------------------------------------


def test_largest_assets_sorted_descending(storage, assets_home):
    small = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    big_data = _tiny_png() + b"\x00" * 500
    # Recreate as a distinct clip with larger recorded size_bytes.
    big = _add_image_clip(storage, data=big_data, width=4, height=4)

    ctx = cs.build_scan_context(storage)
    largest = cs.find_largest_assets(ctx)

    assert largest[0].clip.id == big.id
    assert largest[-1].clip.id == small.id


def test_largest_assets_respects_limit(storage, assets_home):
    for _ in range(5):
        _add_image_clip(storage, data=_tiny_png(), width=4, height=4)

    ctx = cs.build_scan_context(storage)
    largest = cs.find_largest_assets(ctx, limit=2)

    assert len(largest) == 2


def test_largest_assets_never_preselected():
    # Structural guarantee: SuggestionItem has no selection/keeper concept at
    # all for Category E -- it's a plain list, not a SuggestionGroup.
    assert not hasattr(cs.SuggestionItem, "preselectable_ids")


# --- protection rules ----------------------------------------------------------


def test_notes_protection_not_implemented(storage, assets_home):
    # CacheVault has no notes feature -- confirm the protection evaluator
    # never reports a note-based reason (it would be fabricated).
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    ctx = cs.build_scan_context(storage)
    protection = ctx.protection_for(clip)
    assert not any("note" in r.lower() for r in protection.reasons)


def test_recent_capture_protected_within_window(storage, assets_home):
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    cutoff = (now - timedelta(minutes=cs.RECENT_PROTECTION_MINUTES)).isoformat()
    clip = _add_image_clip(
        storage, data=_tiny_png(), width=4, height=4,
        created_at=now.isoformat(),
    )
    ctx = cs.build_scan_context(storage, recent_cutoff_iso=cutoff)
    protection = ctx.protection_for(clip)
    assert protection.protected is True
    assert "recently" in protection.reasons[0].lower()


def test_old_capture_not_recent_protected(storage, assets_home):
    clip = _add_image_clip(
        storage, data=_tiny_png(), width=4, height=4,
        created_at="2020-01-01T00:00:00+00:00",
    )
    ctx = cs.build_scan_context(storage, recent_cutoff_iso="2026-01-01T00:00:00+00:00")
    protection = ctx.protection_for(clip)
    assert protection.protected is False


# --- cancellation --------------------------------------------------------------


def test_scan_cancelled_between_categories(storage, assets_home):
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)

    calls = {"n": 0}

    def cancel_after_one_category():
        calls["n"] += 1
        return calls["n"] > 1

    result = cs.run_scan(storage, cancel_check=cancel_after_one_category)
    assert result.cancelled is True


def test_scan_not_cancelled_runs_to_completion(storage, assets_home):
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    _add_image_clip(storage, data=_tiny_png(), width=4, height=4)

    result = cs.run_scan(storage)
    assert result.cancelled is False
    assert result.total_groups >= 1


def test_cancellation_never_mutates_anything(storage, assets_home):
    """A cancelled scan is read-only by construction (Stage A performs no
    mutation at all), so cancelling mid-scan must leave every clip live and
    untouched.
    """
    clip = _add_image_clip(storage, data=_tiny_png(), width=4, height=4)
    cs.run_scan(storage, cancel_check=lambda: True)
    reloaded = [c for c in storage.list_clips() if c.id == clip.id]
    assert len(reloaded) == 1
    assert reloaded[0].deleted_at is None


# --- external files are never touched -----------------------------------------


def test_external_file_outside_assets_dir_never_referenced(storage, assets_home, tmp_path):
    external_dir = tmp_path / "not_cachevault"
    external_dir.mkdir()
    external_file = external_dir / "photo.jpg"
    external_file.write_bytes(_tiny_png())

    _add_path_only_image_reference(storage, path=str(external_file))

    ctx = cs.build_scan_context(storage)
    # None of the file-oriented categories should even attempt to look at
    # `external_file` -- proven by every category returning empty/excluding
    # it, and by the file itself still existing untouched afterward.
    assert cs.find_duplicate_screenshot_groups(ctx) == []
    assert cs.find_tiny_images(ctx) == []
    assert cs.find_missing_or_damaged_assets(ctx) == []
    assert cs.find_largest_assets(ctx) == []
    assert external_file.is_file()
    assert external_file.read_bytes() == _tiny_png()
