"""Commit 2 (amended): headless tests for the new bulk vault/storage
primitives (restore_many, soft_delete_many, and their Vault wrappers)
that back both visible-mode and matching-wide selection-menu commands.

Atomic contract under test: dedupe/validate ids first, perform every
write inside one transaction, and roll back ALL of it -- not just what
came after the failure point -- if anything raises partway through.
There is no partial-success return value these methods can produce;
either the whole batch commits (BulkMutationResult.succeeded/.skipped)
or the call raises and nothing changed.

No Tk dependency -- these exercise the storage/vault layer directly, the
same layer the Tk-level tests in tests/test_clip_context_menu.py drive
through the real UI.
"""

from __future__ import annotations

import json
import os
from unittest import mock

import pytest

from cache_vault.core.models import Clip
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


def _add_clips(storage, n, prefix="clip"):
    ids = []
    for i in range(n):
        c = Clip(content=f"{prefix} {i}", preview=f"{prefix} {i}")
        storage.add_clip(c)
        ids.append(c.id)
    return ids


# --- storage.restore_many ---------------------------------------------------


def test_restore_many_restores_all_soft_deleted(storage):
    ids = _add_clips(storage, 5)
    for cid in ids:
        storage.soft_delete(cid)

    result = storage.restore_many(ids)

    assert sorted(result.succeeded) == sorted(ids)
    assert result.succeeded_count == 5
    assert result.skipped == ()
    for c in storage.list_clips(None):
        assert c.deleted_at is None


def test_restore_many_dedupes_input(storage):
    ids = _add_clips(storage, 3)
    for cid in ids:
        storage.soft_delete(cid)

    result = storage.restore_many([ids[0], ids[0], ids[1], ids[0]])

    assert result.succeeded == (ids[0], ids[1])  # first-seen order, no repeats


def test_restore_many_skips_already_active_and_nonexistent(storage):
    ids = _add_clips(storage, 3)
    storage.soft_delete(ids[0])
    # ids[1] stays active (never soft-deleted); "ghost" doesn't exist.
    result = storage.restore_many([ids[0], ids[1], "ghost-id"])

    assert result.succeeded == (ids[0],)
    assert set(result.skipped) == {ids[1], "ghost-id"}
    assert result.succeeded_count == 1
    assert result.skipped_count == 2


def test_restore_many_empty_input_is_noop(storage):
    result = storage.restore_many([])
    assert result.succeeded == ()
    assert result.skipped == ()


# --- storage.soft_delete_many ------------------------------------------------


def test_soft_delete_many_moves_all_active(storage):
    ids = _add_clips(storage, 5)

    result = storage.soft_delete_many(ids)

    assert sorted(result.succeeded) == sorted(ids)
    assert result.skipped == ()
    live_ids = {c.id for c in storage.list_clips(None)}
    assert live_ids == set()


def test_soft_delete_many_dedupes_input(storage):
    ids = _add_clips(storage, 3)

    result = storage.soft_delete_many([ids[0], ids[0], ids[2], ids[2], ids[1]])

    assert result.succeeded == (ids[0], ids[2], ids[1])  # first-seen order, no repeats


def test_soft_delete_many_skips_already_removed_and_nonexistent(storage):
    ids = _add_clips(storage, 3)
    storage.soft_delete(ids[0])  # already removed before the bulk call

    result = storage.soft_delete_many([ids[0], ids[1], "ghost-id"])

    assert result.succeeded == (ids[1],)  # ids[0] skipped -- already removed, not double-counted
    assert set(result.skipped) == {ids[0], "ghost-id"}


def test_soft_delete_many_empty_input_is_noop(storage):
    result = storage.soft_delete_many([])
    assert result.succeeded == ()
    assert result.skipped == ()


# --- round trip: soft_delete_many then restore_many -------------------------


def test_soft_delete_many_then_restore_many_round_trip(storage):
    ids = _add_clips(storage, 10)

    moved = storage.soft_delete_many(ids)
    assert moved.succeeded_count == 10
    assert {c.id for c in storage.list_clips(None)} == set()

    restored = storage.restore_many(ids)
    assert restored.succeeded_count == 10
    assert {c.id for c in storage.list_clips(None)} == set(ids)


# --- Injected-failure integrity: atomic rollback, no misleading state -------


def test_restore_many_injected_failure_rolls_back_everything(storage):
    """A failure on the 3rd of 5 restores must not leave the first 2
    committed -- proving the transaction is genuinely all-or-nothing,
    not "commit what succeeded before the crash"."""
    ids = _add_clips(storage, 5)
    for cid in ids:
        storage.soft_delete(cid)

    real_touch = storage._touch
    calls = {"n": 0}

    def failing_touch(cid):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("injected failure")
        return real_touch(cid)

    storage._touch = failing_touch
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            storage.restore_many(ids)
    finally:
        storage._touch = real_touch

    # No misleading partial state: every clip is still exactly where it
    # was before the call -- soft-deleted, none restored.
    live_ids = {c.id for c in storage.list_clips(None)}
    assert live_ids == set()
    for cid in ids:
        row = storage.conn.execute(
            "SELECT deleted_at FROM clips WHERE id = ?", (cid,)
        ).fetchone()
        assert row["deleted_at"] is not None, f"{cid} should still be soft-deleted after rollback"


class _FailingConnProxy:
    """sqlite3.Connection's own ``.execute`` attribute is read-only (a
    C-extension restriction), so injecting a mid-batch failure requires
    swapping VaultStorage's ``.conn`` attribute (a plain Python
    reference) for a proxy, rather than patching the connection object
    itself."""

    def __init__(self, real_conn, *, fail_sql_prefix: str, fail_after: int):
        self._real = real_conn
        self._fail_sql_prefix = fail_sql_prefix
        self._fail_after = fail_after
        self._matching_calls = 0

    def execute(self, sql, params=()):
        if sql.startswith(self._fail_sql_prefix):
            self._matching_calls += 1
            if self._matching_calls == self._fail_after:
                raise RuntimeError("injected failure")
        return self._real.execute(sql, params)

    def commit(self):
        return self._real.commit()

    def rollback(self):
        return self._real.rollback()


def test_soft_delete_many_injected_failure_rolls_back_everything(storage):
    ids = _add_clips(storage, 6)

    real_conn = storage.conn
    storage.conn = _FailingConnProxy(
        real_conn, fail_sql_prefix="UPDATE clips SET deleted_at", fail_after=4,
    )
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            storage.soft_delete_many(ids)
    finally:
        storage.conn = real_conn

    # Nothing committed: every clip is still active, none soft-deleted.
    live_ids = {c.id for c in storage.list_clips(None)}
    assert live_ids == set(ids)


def test_injected_failure_produces_no_receipt_or_event(storage):
    """The Vault-layer wrapper must never record an event for a batch
    whose storage call raised -- proving "receipt only after a
    successful commit", not "receipt for whatever happened to run"."""
    from cache_vault.core import models

    v = Vault(storage=storage, settings=Settings(capture_paused=True))
    ids = _add_clips(storage, 4)
    for cid in ids:
        storage.soft_delete(cid)
    before_event_count = len(v.events.recent())

    real_touch = storage._touch
    calls = {"n": 0}

    def failing_touch(cid):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected failure")
        return real_touch(cid)

    storage._touch = failing_touch
    try:
        with pytest.raises(RuntimeError):
            v.restore_many(ids)
    finally:
        storage._touch = real_touch

    after_event_count = len(v.events.recent())
    assert after_event_count == before_event_count  # zero new events -- no misleading receipt
    restored_events = [
        e for e in v.events.recent() if e.get("event_type") == models.EVENT_RESTORED
    ]
    assert len(restored_events) == 0


def test_injected_failure_never_touches_external_files(tmp_path, monkeypatch):
    """A failed bulk mutation must not have written/deleted any file --
    these primitives only ever touch clips.deleted_at (restore_many also
    touches clips.updated_at via _touch), never clip_assets or anything
    on disk. Injects the failure into restore_many (the path that
    actually calls _touch) and asserts the isolated LOCALAPPDATA root
    this test controls is untouched, both on failure and in general."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    v = Vault(storage=VaultStorage(":memory:"), settings=Settings(capture_paused=True))
    try:
        clips = [v.capture(f"note {i}", force=True) for i in range(3)]
        ids = [c.id for c in clips]
        for cid in ids:
            v.storage.soft_delete(cid)
        files_before = list(tmp_path.rglob("*"))

        real_touch = v.storage._touch
        v.storage._touch = lambda cid: (_ for _ in ()).throw(RuntimeError("injected"))
        try:
            with pytest.raises(RuntimeError):
                v.storage.restore_many(ids)
        finally:
            v.storage._touch = real_touch

        files_after = list(tmp_path.rglob("*"))
        assert files_before == files_after
    finally:
        v.close()


# --- Vault wrappers: dedup + event recording (successful path) -------------


def _vault():
    return Vault(storage=VaultStorage(":memory:"), settings=Settings(capture_paused=True))


def test_vault_restore_many_records_one_event_per_restored_clip():
    from cache_vault.core import models

    v = _vault()
    try:
        clips = [v.capture(f"note {i}", force=True) for i in range(4)]
        ids = [c.id for c in clips]
        for cid in ids:
            v.remove_from_history(cid)

        result = v.restore_many(ids + [ids[0]])  # duplicate id in the input

        assert sorted(result.succeeded) == sorted(ids)  # deduplicated
        restored_events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_RESTORED
        ]
        assert len(restored_events) == 4  # exactly one event per unique clip, not 5
    finally:
        v.close()


def test_vault_remove_from_history_many_records_one_event_per_moved_clip():
    from cache_vault.core import models

    v = _vault()
    try:
        clips = [v.capture(f"note {i}", force=True) for i in range(4)]
        ids = [c.id for c in clips]

        result = v.remove_from_history_many(ids + [ids[0], ids[1]])  # duplicates

        assert sorted(result.succeeded) == sorted(ids)
        deleted_events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_DELETED
        ]
        assert len(deleted_events) == 4  # not 6
    finally:
        v.close()


def test_vault_remove_from_history_many_never_touches_external_files(tmp_path, monkeypatch):
    """Bulk soft-delete must remain DB-only -- no filesystem interaction
    for a plain text clip (nothing to touch), confirmed by asserting no
    new files appear under the isolated LOCALAPPDATA root this test
    controls."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    v = _vault()
    try:
        clips = [v.capture(f"note {i}", force=True) for i in range(3)]
        ids = [c.id for c in clips]
        files_before = list(tmp_path.rglob("*"))

        v.remove_from_history_many(ids)

        files_after = list(tmp_path.rglob("*"))
        assert files_before == files_after
    finally:
        v.close()


# --- storage.clear_collection / Vault.empty_collection -----------------------


def test_clear_collection_removes_only_target_collection_labels(storage):
    ids = _add_clips(storage, 5)
    for cid in ids[:3]:
        storage.set_collection(cid, "Work")
    for cid in ids[3:]:
        storage.set_collection(cid, "Personal")

    result = storage.clear_collection("Work")

    assert sorted(result.succeeded) == sorted(ids[:3])
    assert result.skipped == ()
    work_clips = {c.id for c in storage.list_clips("col:Work")}
    personal_clips = {c.id for c in storage.list_clips("col:Personal")}
    assert work_clips == set()
    assert personal_clips == set(ids[3:])
    assert all(c.collection is None for c in storage.list_clips(None) if c.id in ids[:3])


def test_clear_collection_dedupes_input(storage):
    ids = _add_clips(storage, 3)
    for cid in ids:
        storage.set_collection(cid, "Work")

    result = storage.clear_collection("Work", [ids[0], ids[0], ids[1], ids[0]])

    assert result.succeeded == (ids[0], ids[1])
    assert result.succeeded_count == 2
    clips_by_id = {c.id: c for c in storage.list_clips(None)}
    assert clips_by_id[ids[0]].collection is None
    assert clips_by_id[ids[1]].collection is None
    assert clips_by_id[ids[2]].collection == "Work"


def test_clear_collection_skips_non_members_and_nonexistent(storage):
    ids = _add_clips(storage, 4)
    for cid in ids[:2]:
        storage.set_collection(cid, "Work")
    for cid in ids[2:]:
        storage.set_collection(cid, "Personal")

    result = storage.clear_collection("Work", [ids[0], ids[2], "ghost-id"])

    assert result.succeeded == (ids[0],)
    assert set(result.skipped) == {ids[2], "ghost-id"}


def test_clear_collection_preserves_favorite_pinned_and_content(storage):
    ids = _add_clips(storage, 3)
    for cid in ids:
        storage.set_collection(cid, "Work")
        storage.set_pinned(cid, True)
    content_before = {cid: storage.get_clip(cid).content for cid in ids}

    result = storage.clear_collection("Work")

    assert result.succeeded_count == 3
    for cid in ids:
        clip = storage.get_clip(cid)
        assert clip.collection is None
        assert clip.is_pinned is True
        assert clip.content == content_before[cid]
        assert clip.deleted_at is None


def test_clear_collection_injected_failure_rolls_back_everything(storage):
    ids = _add_clips(storage, 5)
    for cid in ids:
        storage.set_collection(cid, "Work")

    real_conn = storage.conn
    storage.conn = _FailingConnProxy(
        real_conn, fail_sql_prefix="UPDATE clips SET collection", fail_after=3,
    )
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            storage.clear_collection("Work")
    finally:
        storage.conn = real_conn

    # Every clip must still belong to Work; no partial clear occurred.
    work_clips = {c.id for c in storage.list_clips("col:Work")}
    assert work_clips == set(ids)


def test_vault_empty_collection_records_receipt_and_event():
    from cache_vault.core import models

    v = _vault()
    try:
        clips = [v.capture(f"note {i}", force=True) for i in range(3)]
        ids = [c.id for c in clips]
        for cid in ids:
            v.set_collection(cid, "Work")
        before_events = len(v.events.recent())

        result = v.empty_collection("Work", ids)

        assert result.succeeded_count == 3
        assert {c.collection for c in v.storage.list_clips(None)} == {None}
        after_events = v.events.recent()
        emptied = [e for e in after_events if e.get("event_type") == models.EVENT_EMPTIED_COLLECTION]
        assert len(emptied) == 1
        details = emptied[0]["details"]
        assert details["collection_name"] == "Work"
        assert details["membership_removed"] == 3
        assert details["skipped_count"] == 0
        assert details["clips_deleted"] == 0
        assert details["assets_deleted"] == 0
        assert details["disk_bytes_reclaimed"] == 0
    finally:
        v.close()


def test_vault_empty_collection_empty_or_zero_membership_produces_no_receipt():
    from cache_vault.core import models

    v = _vault()
    try:
        before_events = len(v.events.recent())
        result = v.empty_collection("Work", [])
        assert result.succeeded_count == 0
        after_events = len(v.events.recent())
        assert after_events == before_events

        # Nonexistent collection also produces no receipt.
        result2 = v.empty_collection("Missing")
        assert result2.succeeded_count == 0
        assert len(v.events.recent()) == before_events
    finally:
        v.close()


def test_vault_empty_collection_injected_failure_produces_no_receipt(storage):
    from cache_vault.core import models

    v = Vault(storage=storage, settings=Settings(capture_paused=True))
    ids = _add_clips(storage, 4)
    for cid in ids:
        v.set_collection(cid, "Work")
    before_events = len(v.events.recent())

    real_conn = storage.conn
    storage.conn = _FailingConnProxy(
        real_conn, fail_sql_prefix="UPDATE clips SET collection", fail_after=2,
    )
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            v.empty_collection("Work")
    finally:
        storage.conn = real_conn

    # No partial labels were cleared and no misleading receipt/event was recorded.
    after_events = [e for e in v.events.recent() if e.get("event_type") == models.EVENT_EMPTIED_COLLECTION]
    assert len(after_events) == 0
    work_clips = {c.id for c in storage.list_clips("col:Work")}
    assert work_clips == set(ids)


# --- Empty Collection: managed-asset, external-file, and Recently Removed ---
# safety proofs (corrective commit -- see commit 4 checkpoint review). These
# close three invariants that were previously only asserted in docstrings/
# comments ("never clip_assets, external files... " in storage.clear_collection)
# rather than proven against a real fixture.


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def test_empty_collection_never_touches_managed_asset_file(assets_home):
    """A clip with a real clip_assets row and on-disk screenshot file must
    come through Empty Collection with both completely untouched --
    clear_collection only ever writes ``clips.collection`` (see its
    docstring); this proves that claim against a real asset instead of
    trusting the comment.
    """
    from cache_vault.core import image_assets, models

    data = b"\x89PNG\r\n\x1a\n" + b"0123456789abcdef" * 4
    chash = models.bytes_hash(data)

    v = _vault()
    try:
        clip = Clip(
            content_hash=chash, content_type=models.CONTENT_IMAGE,
            classification=models.CLASS_IMAGE, content="[Screenshot PNG]", preview="Screenshot",
        )
        v.storage.add_clip(clip)
        record = image_assets.ClipAssetRecord(
            asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
            size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
            storage_name=image_assets.make_storage_name(clip.id, "png"), width=4, height=4,
        )
        v.storage.save_clip_asset(record, data)
        v.set_collection(clip.id, "Collection A")

        asset_path = image_assets.assets_dir() / record.storage_name
        sha_before = models.bytes_hash(asset_path.read_bytes())
        size_before = asset_path.stat().st_size
        mtime_before = asset_path.stat().st_mtime_ns
        row_before = v.storage.get_asset_record(clip.id)

        with mock.patch("os.remove", wraps=os.remove) as os_remove, \
             mock.patch("os.unlink", wraps=os.unlink) as os_unlink, \
             mock.patch("cache_vault.core.image_assets.delete_asset_file") as delete_asset_file, \
             mock.patch("cache_vault.core.image_assets.write_asset_file") as write_asset_file, \
             mock.patch("cache_vault.core.collection_receipts.write_file_receipt") as receipt:
            result = v.empty_collection("Collection A", [clip.id])

        # Filesystem spy: the real production path never calls any function
        # capable of deleting or rewriting the asset file.
        os_remove.assert_not_called()
        os_unlink.assert_not_called()
        delete_asset_file.assert_not_called()
        write_asset_file.assert_not_called()

        assert result.succeeded_count == 1
        reloaded = v.storage.get_clip(clip.id)
        assert reloaded.deleted_at is None  # clip remains active
        assert reloaded.collection is None  # label cleared

        row_after = v.storage.get_asset_record(clip.id)
        assert row_after == row_before  # asset DB row byte-for-byte unchanged

        # Byte-level proof on the managed file itself.
        assert asset_path.is_file()
        assert models.bytes_hash(asset_path.read_bytes()) == sha_before
        assert asset_path.stat().st_size == size_before
        assert asset_path.stat().st_mtime_ns == mtime_before

        receipt.assert_called_once()
        payload = receipt.call_args[0][1]
        assert payload["assets_deleted"] == 0
        assert payload["disk_bytes_reclaimed"] == 0
    finally:
        v.close()


def test_empty_collection_never_touches_external_path_only_file(tmp_path, assets_home):
    """A path-only clip (classification=CLASS_PATH) merely references a
    file the vault never owns -- content is the path string itself, no
    clip_assets row. Empty Collection must clear only the DB label; the
    external file must never be removed, rewritten, or moved.
    """
    from cache_vault.core import models

    external_dir = tmp_path / "outside_vault"
    external_dir.mkdir()
    external_file = external_dir / "external-doc.txt"
    external_file.write_text("external content that must never change", encoding="utf-8")

    sha_before = models.bytes_hash(external_file.read_bytes())
    size_before = external_file.stat().st_size
    mtime_before = external_file.stat().st_mtime_ns

    v = _vault()
    try:
        clip = Clip(content=str(external_file), preview=str(external_file), classification=models.CLASS_PATH)
        v.storage.add_clip(clip)
        v.set_collection(clip.id, "Collection A")
        assert v.storage.has_clip_asset(clip.id) is False

        with mock.patch("os.remove", wraps=os.remove) as os_remove, \
             mock.patch("os.unlink", wraps=os.unlink) as os_unlink, \
             mock.patch("cache_vault.core.image_assets.delete_asset_file") as delete_asset_file, \
             mock.patch("cache_vault.core.image_assets.write_asset_file") as write_asset_file, \
             mock.patch("cache_vault.core.collection_receipts.write_file_receipt") as receipt:
            result = v.empty_collection("Collection A", [clip.id])

        # Filesystem spy: nothing in the real path ever opens the external
        # file for mutation, moves it, or deletes it.
        os_remove.assert_not_called()
        os_unlink.assert_not_called()
        delete_asset_file.assert_not_called()
        write_asset_file.assert_not_called()

        assert result.succeeded_count == 1
        reloaded = v.storage.get_clip(clip.id)
        assert reloaded.collection is None  # label cleared
        assert reloaded.deleted_at is None  # clip remains active
        assert reloaded.content == str(external_file)  # path itself unchanged

        # Byte-level proof on the external file itself.
        assert external_file.is_file()
        assert models.bytes_hash(external_file.read_bytes()) == sha_before
        assert external_file.stat().st_size == size_before
        assert external_file.stat().st_mtime_ns == mtime_before

        receipt.assert_called_once()
        payload = receipt.call_args[0][1]
        assert payload["assets_deleted"] == 0
        assert payload["disk_bytes_reclaimed"] == 0
        assert payload["clips_deleted"] == 0
    finally:
        v.close()


def test_empty_collection_excludes_recently_removed_memberships():
    """Recently Removed is intentionally out of scope for Empty Collection:
    a collection label describes active-vault organization, and a
    soft-deleted clip's stale label is not a live membership. This is
    enforced by clear_collection's own ``deleted_at IS NOT NULL`` re-check
    inside the mutation loop (defense-in-depth against a stale/racy id
    list, not just a query-layer filter callers must remember to apply).
    This test proves that behavior end-to-end through the real
    Vault.empty_collection path, including when the removed clip's id is
    explicitly passed in -- simulating exactly the stale snapshot a racy
    caller could produce.
    """
    from cache_vault.core import models
    from cache_vault.core import storage as S

    v = _vault()
    try:
        active_clip, removed_clip = (v.capture(f"note {i}", force=True) for i in range(2))
        v.set_collection(active_clip.id, "Collection A")
        v.set_collection(removed_clip.id, "Collection A")
        v.storage.soft_delete(removed_clip.id)

        removed_before = v.storage.get_clip(removed_clip.id)
        assert removed_before.deleted_at is not None
        assert removed_before.collection == "Collection A"
        recently_removed_before = v.count_clips(S.FILTER_RECENTLY_REMOVED)

        with mock.patch("cache_vault.core.collection_receipts.write_file_receipt") as receipt:
            result = v.empty_collection("Collection A", [active_clip.id, removed_clip.id])

        assert set(result.succeeded) == {active_clip.id}
        assert set(result.skipped) == {removed_clip.id}

        active_after = v.storage.get_clip(active_clip.id)
        assert active_after.collection is None  # active membership cleared

        removed_after = v.storage.get_clip(removed_clip.id)
        assert removed_after.deleted_at == removed_before.deleted_at  # still soft-deleted, same timestamp
        assert removed_after.collection == "Collection A"  # label untouched
        assert v.count_clips(S.FILTER_RECENTLY_REMOVED) == recently_removed_before  # no restore, no further removal

        receipt.assert_called_once()
        payload = receipt.call_args[0][1]
        assert payload["membership_removed"] == 1
        assert payload["skipped_count"] == 1
    finally:
        v.close()


def test_empty_collection_receipt_excludes_full_clip_content():
    """The receipt/event body carries only ids and counts -- never the
    clip's actual clipboard text -- since receipts are written to disk
    and read back by the receipt ledger UI.
    """
    from cache_vault.core import models

    secret_text = "SENSITIVE-CLIPBOARD-MARKER-93f1b2"
    v = _vault()
    try:
        clip = v.capture(secret_text, force=True)
        v.set_collection(clip.id, "Collection A")

        with mock.patch("cache_vault.core.collection_receipts.write_file_receipt") as receipt:
            result = v.empty_collection("Collection A", [clip.id])

        assert result.succeeded_count == 1
        receipt.assert_called_once()
        payload = receipt.call_args[0][1]
        serialized = json.dumps(payload)
        assert secret_text not in serialized
        assert payload["action"] == models.ACTION_EMPTY_COLLECTION
        assert payload["collection_name"] == "Collection A"
        assert payload["clip_ids"] == [clip.id]  # bounded to ids only, no content

        emptied = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_EMPTIED_COLLECTION
        ]
        assert len(emptied) == 1
        assert secret_text not in json.dumps(emptied[0]["details"])
    finally:
        v.close()
