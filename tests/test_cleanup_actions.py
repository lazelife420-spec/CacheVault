"""Stage C tests: Vault Cleanup Suggestions mutation + receipt layer."""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from PIL import Image

from cache_vault.core import cleanup_store as cs_store
from cache_vault.core import image_assets, models
from cache_vault.core.cleanup_actions import CleanupSelection, apply_cleanup_selection
from cache_vault.core.events import EventLog
from cache_vault.core.models import Clip


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _events(storage):
    return EventLog(storage)


def _add_text_clip(storage, *, content, is_pinned=False):
    clip = Clip(
        content_hash=models.content_hash(content),
        content_type=models.CONTENT_TEXT,
        content=content,
        preview=content[:50],
        is_pinned=is_pinned,
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
    a = Clip(content_hash=models.content_hash(sensitive_text), content=sensitive_text, preview="secret")
    b = Clip(content_hash=models.content_hash(sensitive_text), content=sensitive_text, preview="secret")
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
    clip = Clip(content_hash=chash, content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE)
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
