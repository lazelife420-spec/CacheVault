"""Vault Cleanup Suggestions v1 -- decision-suppression lifecycle tests.

These prove the actual promise the feature makes: a saved decision changes
THE NEXT SCAN'S RESULT (groups, counts, bytes), not just a database row.
test_cleanup_store.py only proves decisions reach the database; these tests
run the same record_decision path the real UI uses, then run a real
cleanup_suggestions.run_scan()/find_* call and assert on its output --
catching exactly the gap a GUI walkthrough of draft PR #67 found: nothing
in the scan/display pipeline ever consulted a saved decision.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from PIL import Image

from cache_vault.core import cleanup_suggestions as cs
from cache_vault.core import image_assets, models
from cache_vault.core.cleanup_store import (
    DECISION_IGNORED,
    DECISION_KEEP,
    DECISION_KEEP_FOREVER,
    SCOPE_ITEM,
    record_decision,
)
from cache_vault.core.models import Clip
from cache_vault.core.storage import VaultStorage

# Older than cleanup_suggestions.RECENT_PROTECTION_MINUTES (15) so clips
# built here aren't caught by apply_cleanup_selection's mutation-time
# recency re-check (these tests are about suppression, not recency).
_NOT_RECENT_ISO = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _test_png(color=(255, 0, 0)) -> bytes:
    # 100x100 -- deliberately NOT tiny (<64px), so duplicate-screenshot
    # tests don't also trip the tiny-image detector and double-count in
    # total_reviewable_items.
    buf = BytesIO()
    Image.new("RGB", (100, 100), color).save(buf, format="PNG")
    return buf.getvalue()


def _add_image_clip(storage: VaultStorage, *, data: bytes, width=100, height=100, is_pinned=False) -> Clip:
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash, content_type=models.CONTENT_IMAGE,
        content="[Screenshot PNG]", preview="Screenshot",
        classification=models.CLASS_IMAGE, source_app="test.exe", is_pinned=is_pinned,
        created_at=_NOT_RECENT_ISO, last_used_at=_NOT_RECENT_ISO,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=width, height=height,
    )
    storage.save_clip_asset(record, data)
    return clip


def _keep_forever(storage, *, category, clip_id):
    record_decision(
        storage, category=category, scope=SCOPE_ITEM, fingerprint=clip_id,
        clip_id=clip_id, decision=DECISION_KEEP_FOREVER, rule_version=cs.RULE_VERSION,
    )


# --- Keep forever: survives rescan and restart --------------------------------


def test_keep_forever_absent_from_next_scan(storage, assets_home):
    data = _test_png()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)

    result = cs.run_scan(storage)
    assert len(result.duplicate_screenshot_groups) == 1
    assert result.duplicate_screenshot_groups[0].count == 2

    non_keeper_id = a.id if a.id != result.duplicate_screenshot_groups[0].recommended_keeper_id else b.id
    _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=non_keeper_id)

    rescanned = cs.run_scan(storage)
    # Only 1 unsuppressed copy (the keeper) remains -- no longer a duplicate.
    assert rescanned.duplicate_screenshot_groups == []
    assert rescanned.total_reviewable_items == 0


def test_keep_forever_survives_database_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    db_path = tmp_path / "vault.db"
    s1 = VaultStorage(str(db_path))
    data = _test_png()
    a = _add_image_clip(s1, data=data)
    b = _add_image_clip(s1, data=data)
    result = cs.run_scan(s1)
    non_keeper_id = a.id if a.id != result.duplicate_screenshot_groups[0].recommended_keeper_id else b.id
    _keep_forever(s1, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=non_keeper_id)
    s1.close()

    s2 = VaultStorage(str(db_path))
    rescanned = cs.run_scan(s2)
    assert rescanned.duplicate_screenshot_groups == []
    s2.close()


# --- Keep: temporary, tied to the scan generation it was recorded under -------


def test_keep_suppresses_only_within_same_scan_generation(storage, assets_home):
    data = _test_png()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)

    result = cs.run_scan(storage)
    generation = result.scan_generation
    non_keeper_id = a.id if a.id != result.duplicate_screenshot_groups[0].recommended_keeper_id else b.id
    record_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
        fingerprint=non_keeper_id, clip_id=non_keeper_id, decision=DECISION_KEEP,
        rule_version=cs.RULE_VERSION, scan_generation=generation,
    )

    # A quiet rescan reusing the SAME generation (what the UI does right
    # after a "Keep" click) still suppresses it.
    quiet_rescan = cs.run_scan(storage, scan_generation=generation)
    assert quiet_rescan.duplicate_screenshot_groups == []

    # A genuinely fresh scan (new generation, what "Scan vault" always
    # does) is NOT suppressed by an old "keep" -- it must reappear.
    fresh_rescan = cs.run_scan(storage)
    assert fresh_rescan.scan_generation != generation
    assert len(fresh_rescan.duplicate_screenshot_groups) == 1
    assert fresh_rescan.duplicate_screenshot_groups[0].count == 2


# --- Partial vs fully suppressed groups ----------------------------------------


def test_partial_group_suppression_recomputes_count_and_bytes(storage, assets_home):
    data = _test_png()
    clips = [_add_image_clip(storage, data=data) for _ in range(3)]

    result = cs.run_scan(storage)
    group = result.duplicate_screenshot_groups[0]
    assert group.count == 3
    non_keeper_ids = [c.id for c in clips if c.id != group.recommended_keeper_id]
    _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=non_keeper_ids[0])

    rescanned = cs.run_scan(storage)
    assert len(rescanned.duplicate_screenshot_groups) == 1
    surviving = rescanned.duplicate_screenshot_groups[0]
    assert surviving.count == 2
    assert surviving.recommended_keeper_id == group.recommended_keeper_id
    # Bytes recalculated from the 2 surviving items, not the original 3.
    assert surviving.redundant_bytes == len(data)  # 1 non-keeper item remains
    assert rescanned.redundant_bytes_identified == len(data)


def test_fully_suppressed_group_disappears(storage, assets_home):
    data = _test_png()
    clips = [_add_image_clip(storage, data=data) for _ in range(3)]

    result = cs.run_scan(storage)
    group = result.duplicate_screenshot_groups[0]
    for c in clips:
        if c.id != group.recommended_keeper_id:
            _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=c.id)

    rescanned = cs.run_scan(storage)
    assert rescanned.duplicate_screenshot_groups == []
    assert rescanned.total_groups == 0
    assert rescanned.redundant_bytes_identified == 0


def test_repeated_text_partial_suppression(storage):
    from tests.test_cleanup_suggestions import _add_text_clip  # noqa: PLC0415

    body = "repeated body" * 5
    clips = [_add_text_clip(storage, content=body) for _ in range(3)]
    result = cs.run_scan(storage)
    group = result.repeated_text_groups[0]
    assert group.count == 3
    non_keeper = [c for c in clips if c.id != group.recommended_keeper_id][0]
    _keep_forever(storage, category=cs.CATEGORY_REPEATED_TEXT, clip_id=non_keeper.id)

    rescanned = cs.run_scan(storage)
    assert len(rescanned.repeated_text_groups) == 1
    assert rescanned.repeated_text_groups[0].count == 2


# --- Ignore: category-specific, not global -------------------------------------


def test_ignore_is_scoped_to_its_own_category_only(storage, assets_home):
    """A decision recorded under one category must never suppress the same
    clip in a different category -- the natural key includes category.
    """
    data = _test_png(color=(10, 200, 30))
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)

    result = cs.run_scan(storage)
    non_keeper_id = a.id if a.id != result.duplicate_screenshot_groups[0].recommended_keeper_id else b.id
    record_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
        fingerprint=non_keeper_id, clip_id=non_keeper_id, decision=DECISION_IGNORED,
        rule_version=cs.RULE_VERSION,
    )

    rescanned = cs.run_scan(storage)
    assert rescanned.duplicate_screenshot_groups == []
    # The largest-assets category (visibility only) is a DIFFERENT category
    # for the very same clip -- must not be suppressed by the duplicate-
    # screenshot decision.
    largest_ids = {it.clip.id for it in rescanned.largest_assets}
    assert non_keeper_id in largest_ids


def test_decision_never_suppresses_an_unrelated_clip_with_matching_bytes(storage, assets_home):
    """Identity is the clip's own id, never the shared asset hash -- a
    'keep forever' on one duplicate copy must not silently protect some
    OTHER, later clip that happens to share the same image bytes.
    """
    data = _test_png()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)
    result = cs.run_scan(storage)
    non_keeper_id = a.id if a.id != result.duplicate_screenshot_groups[0].recommended_keeper_id else b.id
    _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=non_keeper_id)

    # A brand new clip with byte-identical content, captured later.
    c = _add_image_clip(storage, data=data)
    rescanned = cs.run_scan(storage)
    assert len(rescanned.duplicate_screenshot_groups) == 1
    surviving_ids = {it.clip.id for it in rescanned.duplicate_screenshot_groups[0].items}
    assert c.id in surviving_ids
    assert non_keeper_id not in surviving_ids


# --- Mutation and restore interaction with suppression -------------------------


def test_moving_unrelated_items_does_not_erase_a_suppression_decision(storage, assets_home):
    from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection
    from cache_vault.core.events import EventLog

    data_kept = _test_png(color=(1, 2, 3))
    kept_a = _add_image_clip(storage, data=data_kept)
    kept_b = _add_image_clip(storage, data=data_kept)
    result = cs.run_scan(storage)
    kept_group = result.duplicate_screenshot_groups[0]
    kept_non_keeper = kept_a.id if kept_a.id != kept_group.recommended_keeper_id else kept_b.id
    _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=kept_non_keeper)

    data_other = _test_png(color=(200, 100, 50))
    other_a = _add_image_clip(storage, data=data_other)
    other_b = _add_image_clip(storage, data=data_other)

    events = EventLog(storage)
    result2 = cs.run_scan(storage)
    other_group = next(
        g for g in result2.duplicate_screenshot_groups
        if {it.clip.id for it in g.items} == {other_a.id, other_b.id}
    )
    apply_cleanup_selection(
        storage, events,
        selections=[CleanupSelection(
            category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
            fingerprint=other_group.preselectable_ids[0], clip_ids=other_group.preselectable_ids,
        )],
        rule_version=cs.RULE_VERSION,
    )

    rescanned = cs.run_scan(storage)
    # The unrelated group's move must not have touched the kept decision.
    assert rescanned.duplicate_screenshot_groups == []  # kept group still fully suppressed
    assert kept_non_keeper not in {
        it.clip.id for g in rescanned.duplicate_screenshot_groups for it in g.items
    }


def test_restore_does_not_clear_keep_forever(storage, assets_home):
    """Documents actual current behavior: storage.restore() only clears
    deleted_at and never touches clip_cleanup_decisions, so a 'keep
    forever' recorded before a move survives being moved and restored.
    """
    from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection
    from cache_vault.core.events import EventLog

    data = _test_png()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)
    c = _add_image_clip(storage, data=data)
    result = cs.run_scan(storage)
    group = result.duplicate_screenshot_groups[0]
    non_keeper_ids = [x.id for x in (a, b, c) if x.id != group.recommended_keeper_id]
    _keep_forever(storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, clip_id=non_keeper_ids[0])

    events = EventLog(storage)
    apply_cleanup_selection(
        storage, events,
        selections=[CleanupSelection(
            category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
            fingerprint=non_keeper_ids[1], clip_ids=[non_keeper_ids[1]],
        )],
        rule_version=cs.RULE_VERSION,
    )
    storage.restore(non_keeper_ids[1])

    rescanned = cs.run_scan(storage)
    assert len(rescanned.duplicate_screenshot_groups) == 1
    surviving_ids = {it.clip.id for it in rescanned.duplicate_screenshot_groups[0].items}
    # The restored clip is back and live...
    assert non_keeper_ids[1] in surviving_ids
    # ...but the OTHER clip's "keep forever" from before any of this
    # happened is untouched and still suppresses it.
    assert non_keeper_ids[0] not in surviving_ids


def test_scan_totals_refresh_after_move_and_restore(storage, assets_home):
    from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection
    from cache_vault.core.events import EventLog

    data = _test_png()
    clips = [_add_image_clip(storage, data=data) for _ in range(3)]
    result = cs.run_scan(storage)
    assert result.total_reviewable_items == 3
    group = result.duplicate_screenshot_groups[0]
    victim = group.preselectable_ids[0]

    events = EventLog(storage)
    apply_cleanup_selection(
        storage, events,
        selections=[CleanupSelection(
            category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
            fingerprint=victim, clip_ids=[victim],
        )],
        rule_version=cs.RULE_VERSION,
    )
    after_move = cs.run_scan(storage)
    assert after_move.total_reviewable_items == 2

    storage.restore(victim)
    after_restore = cs.run_scan(storage)
    assert after_restore.total_reviewable_items == 3
