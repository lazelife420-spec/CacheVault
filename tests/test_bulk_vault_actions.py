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
