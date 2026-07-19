"""Stage C tests: Vault Cleanup Suggestions mutation + receipt layer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from cache_vault.core import cleanup_store as cs_store
from cache_vault.core import image_assets, models
from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection
from cache_vault.core.events import EventLog
from cache_vault.core.models import Clip

# Older than cleanup_suggestions.RECENT_PROTECTION_MINUTES (15) so clips
# built for mutation tests aren't accidentally caught by the "recently
# captured/used" protection apply_cleanup_selection now re-checks at
# mutation time (see cache_vault/core/cleanup_actions.py). Scan-time
# recency behavior itself is covered separately in
# tests/test_cleanup_suggestions.py.
_NOT_RECENT_IISO = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _events(storage):
    return EventLog(storage)


def _add_text_clip(storage, *, content, is_pinned=False, created_at=_NOT_RECENT_IISO):
    clip = Clip(
        content_hash=models.content_hash(content),
        content_type=models.CONTENT_TEXT,
        content=content,
        preview=content[:50],
        is_pinned=is_pinned,
        created_at=created_at,
        last_used_at=created_at,
    )
    storage.add_clip(clip)
    return clip


def test_moves_unprotected_selection_to_recently_removed(storage, assets_home):
    a = _add_text_clip(storage, content="dup a")
    b = _add_text_clip(storage, content="dup a")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp1", clip_ids=[b.id],
    )
    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel], rule_version=1,
    )
    assert result.moved_clip_ids == [b.id]
    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert b.id not in reloaded  # no longer live
    assert a.id in reloaded  # untouched


def test_protected_item_never_moved_even_if_selected(storage, assets_home):
    fav = _add_text_clip(storage, content="protected", is_pinned=True)
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp2", clip_ids=[fav.id],
    )
    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel], rule_version=1,
    )
    assert result.moved_clip_ids == []
    assert result.skipped_protected == [fav.id]
    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert fav.id in reloaded
    assert reloaded[fav.id].deleted_at is None


def test_duplicate_clip_ids_do_not_inflate_moved_or_receipt_counts(storage, assets_home, tmp_path, monkeypatch):
    """Issue #68 regression: a selection containing the same clip_id more
    than once -- whether repeated within one CleanupSelection.clip_ids or
    split across two different selections -- must move/count/receipt that
    clip exactly once, not once per occurrence.

    Behaviorally proves the production mutation path actually calls the
    real shared core.selection.dedupe_preserve_order symbol (a spy that
    wraps the real implementation, so the logic under test is unchanged)
    rather than asserting on source text, which breaks under any
    harmless refactor (renaming a local, reformatting, moving the call)
    without the underlying behavior changing at all.
    """
    from cache_vault.core import cleanup_actions, selection as selection_module

    calls = []
    real = selection_module.dedupe_preserve_order

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(cleanup_actions, "dedupe_preserve_order", spy)

    a = _add_text_clip(storage, content="dup a")
    b = _add_text_clip(storage, content="dup b")

    # a.id appears 3 times across two selections; b.id appears once.
    sel1 = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp-dup-1",
        clip_ids=[a.id, a.id, b.id],
    )
    sel2 = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp-dup-2",
        clip_ids=[a.id],
    )

    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel1, sel2], rule_version=1,
    )

    assert len(calls) == 1  # dedup runs exactly once, up front -- not per-item

    # moved_clip_ids/moved_count must list a.id exactly once, not 3 times.
    assert sorted(result.moved_clip_ids) == sorted([a.id, b.id])
    assert result.moved_count == 2
    assert result.skipped_protected == []
    assert result.skipped_missing == []

    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert a.id not in reloaded
    assert b.id not in reloaded

    # The written receipt must reflect the deduplicated counts too --
    # moved_count and the item list, not the raw (duplicated) input size.
    assert result.receipt_path is not None
    receipt = json.loads(Path(result.receipt_path).read_text())
    assert receipt["moved_count"] == 2
    assert len(receipt["items"]) == 2
    assert sorted(item["clip_id"] for item in receipt["items"]) == sorted([a.id, b.id])


def test_duplicate_clip_ids_dont_double_count_bytes_moved(storage, assets_home):
    """The same duplicate-id defense must also protect bytes_moved -- an
    id repeated in the input must not double-add its asset size."""
    buf = BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    data = buf.getvalue()
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash, content_type=models.CONTENT_IMAGE,
        content="[Screenshot PNG]", preview="Screenshot",
        classification=models.CLASS_IMAGE, size_bytes=len(data),
        created_at=_NOT_RECENT_IISO, last_used_at=_NOT_RECENT_IISO,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png",
        file_ext="png", size_bytes=len(data), sha256=chash,
        created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"),
        width=8, height=8,
    )
    storage.save_clip_asset(record, data)

    sel = CleanupSelection(
        category="exact_duplicate_screenshot", scope="item", fingerprint="fp-bytes",
        clip_ids=[clip.id, clip.id, clip.id],
    )
    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel], rule_version=1,
    )
    assert result.moved_count == 1
    assert result.bytes_moved == len(data)  # not 3x


def test_missing_clip_id_reported_not_crashed(storage, assets_home):
    sel = CleanupSelection(
        category="tiny_image", scope="item", fingerprint="ghost", clip_ids=["does-not-exist"],
    )
    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel], rule_version=1,
    )
    assert result.moved_clip_ids == []
    assert result.skipped_missing == ["does-not-exist"]


def test_cancellation_before_mutation_moves_nothing(storage, assets_home):
    clip = _add_text_clip(storage, content="will not move")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp3", clip_ids=[clip.id],
    )
    result = apply_cleanup_selection(
        storage, _events(storage), selections=[sel], rule_version=1,
        cancel_check=lambda: True,
    )
    assert result.cancelled is True
    assert result.moved_clip_ids == []
    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert reloaded[clip.id].deleted_at is None


def test_exception_mid_mutation_rolls_back_atomically(storage, assets_home, monkeypatch):
    a = _add_text_clip(storage, content="one")
    b = _add_text_clip(storage, content="two")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp4", clip_ids=[a.id, b.id],
    )

    # cleanup_actions calls models.now_iso() once per UPDATE inside the
    # mutation loop -- fail it on the second call so the first clip's
    # UPDATE has already been issued (but not yet committed) when the
    # exception hits, proving the whole loop rolls back together rather
    # than leaving a partial commit.
    import cache_vault.core.cleanup_actions as cleanup_actions_mod

    real_now_iso = models.now_iso
    call_count = {"n": 0}

    def flaky_now_iso():
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated failure mid-transaction")
        return real_now_iso()

    monkeypatch.setattr(cleanup_actions_mod.models, "now_iso", flaky_now_iso)

    with pytest.raises(RuntimeError):
        apply_cleanup_selection(
            storage, _events(storage), selections=[sel], rule_version=1,
        )

    monkeypatch.undo()
    reloaded = {c.id: c for c in storage.list_clips(None)}
    # All-or-nothing: the first clip's UPDATE was issued before the failure,
    # but the whole transaction must roll back -- neither clip ends up moved.
    assert reloaded[a.id].deleted_at is None
    assert reloaded[b.id].deleted_at is None


def test_restore_after_cleanup_undoes_the_move(storage, assets_home):
    clip = _add_text_clip(storage, content="restorable")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp5", clip_ids=[clip.id],
    )
    apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)
    assert storage.list_clips(None) == []  # moved out of live history

    storage.restore(clip.id)
    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert clip.id in reloaded
    assert reloaded[clip.id].deleted_at is None


def test_moved_clips_recorded_as_removed_decision(storage, assets_home):
    clip = _add_text_clip(storage, content="tracked")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp6", clip_ids=[clip.id],
    )
    apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)
    decision = cs_store.get_decision(
        storage, category="repeated_text", scope="group", fingerprint="fp6", clip_id=clip.id,
    )
    assert decision is not None
    assert decision.decision == cs_store.DECISION_REMOVED


def test_receipt_written_with_zero_disk_reclaimed(storage, assets_home):
    clip = _add_text_clip(storage, content="receipt me")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp7", clip_ids=[clip.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.receipt_path is not None
    payload = json.loads(open(result.receipt_path, encoding="utf-8").read())
    assert payload["disk_bytes_reclaimed"] == 0
    assert payload["permanent_deletions"] == 0
    assert payload["destination"] == "recently_removed"
    assert payload["moved_count"] == 1


def test_receipt_never_includes_full_clip_content(storage, assets_home):
    sensitive_text = "sk-super-secret-api-key-do-not-leak-this-value"
    a = Clip(content_hash=models.content_hash(sensitive_text), content=sensitive_text, preview="secret",
             created_at=_NOT_RECENT_IISO, last_used_at=_NOT_RECENT_IISO)
    b = Clip(content_hash=models.content_hash(sensitive_text), content=sensitive_text, preview="secret",
             created_at=_NOT_RECENT_IISO, last_used_at=_NOT_RECENT_IISO)
    storage.add_clip(a)
    storage.add_clip(b)
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp8", clip_ids=[b.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    raw = open(result.receipt_path, encoding="utf-8").read()
    assert sensitive_text not in raw

    events = storage.conn.execute("SELECT details FROM events WHERE event_type = ?",
                                   (models.EVENT_CLEANUP_APPLIED,)).fetchall()
    assert events
    for row in events:
        assert sensitive_text not in row["details"]


def test_receipt_registered_in_events_for_receipt_ledger(storage, assets_home):
    clip = _add_text_clip(storage, content="ledger visible")
    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp9", clip_ids=[clip.id],
    )
    apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    row = storage.conn.execute(
        "SELECT event_type FROM events WHERE event_type = ?", (models.EVENT_CLEANUP_APPLIED,)
    ).fetchone()
    assert row is not None

    from cache_vault.ui.receipt_ledger import ACTION_LABELS
    assert models.EVENT_CLEANUP_APPLIED in ACTION_LABELS


def test_apply_never_touches_asset_file_bytes(storage, assets_home):
    """Moving a screenshot to Recently Removed must not delete or modify
    its on-disk asset file -- only hard_delete (untouched by this feature)
    does that.
    """
    buf = BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buf, format="PNG")
    data = buf.getvalue()
    chash = models.bytes_hash(data)
    clip = Clip(content_hash=chash, content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE,
                created_at=_NOT_RECENT_IISO, last_used_at=_NOT_RECENT_IISO)
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=4, height=4,
    )
    storage.save_clip_asset(record, data)
    asset_path = image_assets.assets_dir() / record.storage_name
    before = asset_path.read_bytes()

    sel = CleanupSelection(
        category="exact_duplicate_screenshot", scope="group", fingerprint="fp10", clip_ids=[clip.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_clip_ids == [clip.id]
    assert asset_path.is_file()
    assert asset_path.read_bytes() == before
    assert result.bytes_moved == len(data)


# --- mutation-time protection revalidation (TOCTOU) ----------------------------


def test_item_marked_recently_used_after_scan_is_excluded_at_mutation_time(storage, assets_home):
    """Time-of-check/time-of-use regression for a real finding from
    independent review of draft PR #67: a clip unprotected when the review
    screen was populated, but touched again (re-copied, edited, etc.)
    before the user confirms the move, must not be silently moved anyway.
    """
    clip = _add_text_clip(storage, content="will become recently used")
    # Simulate "scan saw it as unprotected" by not doing anything special --
    # _NOT_RECENT_IISO already makes it eligible. Now simulate the race:
    # something touches the clip *after* that point but *before* the
    # mutation call, exactly like re-copying it in another window while the
    # confirm dialog is still open.
    storage.conn.execute(
        "UPDATE clips SET last_used_at = ? WHERE id = ?", (models.now_iso(), clip.id),
    )
    storage.conn.commit()

    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp-toctou", clip_ids=[clip.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_clip_ids == []
    assert result.skipped_protected == [clip.id]
    reloaded = {c.id: c for c in storage.list_clips(None)}
    assert clip.id in reloaded
    assert reloaded[clip.id].deleted_at is None


def test_keep_forever_recorded_after_scan_is_excluded_at_mutation_time(storage, assets_home):
    """A "keep forever" decision recorded in another window after the
    review screen was populated must still block the move, even though the
    stale selection still names the clip.
    """
    clip = _add_text_clip(storage, content="will be kept forever mid-flight")
    cs_store.record_decision(
        storage, category="repeated_text", scope=cs_store.SCOPE_ITEM, fingerprint=clip.id,
        clip_id=clip.id, decision=cs_store.DECISION_KEEP_FOREVER, rule_version=1,
    )

    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp-kf-toctou", clip_ids=[clip.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_clip_ids == []
    assert result.skipped_protected == [clip.id]


# --- keeper defense-in-depth at the mutation layer ------------------------------


def _add_image_clip(storage, *, data, width=100, height=100):
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash, content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE,
        content="[Screenshot PNG]", preview="Screenshot",
        created_at=_NOT_RECENT_IISO, last_used_at=_NOT_RECENT_IISO,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=width, height=height,
    )
    storage.save_clip_asset(record, data)
    return clip


def test_selecting_every_duplicate_copy_still_leaves_one_keeper(storage, assets_home):
    """Bypasses the UI entirely: calls apply_cleanup_selection directly
    with a crafted selection naming EVERY live copy of a duplicate group
    (something the review dialog's disabled keeper checkbox would never
    produce, but nothing at the mutation layer previously guarded against
    -- a real gap confirmed by independent review of draft PR #67).
    """
    buf = BytesIO()
    Image.new("RGB", (100, 100), (5, 6, 7)).save(buf, format="PNG")
    data = buf.getvalue()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)
    c = _add_image_clip(storage, data=data)

    sel = CleanupSelection(
        category="exact_duplicate_screenshot", scope="group", fingerprint="fp-all-copies",
        clip_ids=[a.id, b.id, c.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_count == 2
    assert len(result.skipped_protected) == 1
    kept_id = result.skipped_protected[0]
    assert kept_id in {a.id, b.id, c.id}

    reloaded = {c2.id: c2 for c2 in storage.list_clips(None)}
    assert kept_id in reloaded
    assert reloaded[kept_id].deleted_at is None
    # The other two really did move.
    for cid in {a.id, b.id, c.id} - {kept_id}:
        assert cid not in reloaded


def test_keeper_defense_does_not_affect_partial_group_selections(storage, assets_home):
    """A selection that leaves at least one copy unselected must move
    normally -- the keeper guard only engages when a selection would
    remove every live copy.
    """
    buf = BytesIO()
    Image.new("RGB", (100, 100), (9, 9, 9)).save(buf, format="PNG")
    data = buf.getvalue()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)
    c = _add_image_clip(storage, data=data)

    sel = CleanupSelection(
        category="exact_duplicate_screenshot", scope="group", fingerprint="fp-partial",
        clip_ids=[a.id, b.id],  # c.id deliberately left out
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_count == 2
    assert result.skipped_protected == []


def test_selecting_every_repeated_text_copy_still_leaves_one_keeper(storage, assets_home):
    """Mirrors test_selecting_every_duplicate_copy_still_leaves_one_keeper
    for the OTHER grouped category: an earlier version of the keeper guard
    covered exact_duplicate_screenshot only, leaving repeated_text groups
    (which share the identical recommended_keeper_id / disabled-checkbox
    design) exposed to the same "wipe every copy" gap -- caught live by a
    follow-up narrow re-review of draft PR #67 (a crafted all-3-selected
    call moved all 3, zero survivors, skipped_protected empty).
    """
    body = "repeated body for the keeper defense test" * 3
    a = _add_text_clip(storage, content=body)
    b = _add_text_clip(storage, content=body)
    c = _add_text_clip(storage, content=body)

    sel = CleanupSelection(
        category="repeated_text", scope="group", fingerprint="fp-all-text-copies",
        clip_ids=[a.id, b.id, c.id],
    )
    result = apply_cleanup_selection(storage, _events(storage), selections=[sel], rule_version=1)

    assert result.moved_count == 2
    assert len(result.skipped_protected) == 1
    kept_id = result.skipped_protected[0]
    assert kept_id in {a.id, b.id, c.id}

    reloaded = {c2.id: c2 for c2 in storage.list_clips(None)}
    assert kept_id in reloaded
    assert reloaded[kept_id].deleted_at is None
    for cid in {a.id, b.id, c.id} - {kept_id}:
        assert cid not in reloaded
