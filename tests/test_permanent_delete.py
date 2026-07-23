"""Commit 5: headless tests for staged permanent deletion from Recently
Removed -- ``storage.hard_delete_many``, ``cache_vault.core.permanent_delete``,
and ``Vault.permanently_delete_many``.

Atomic/staged contract under test: a real filesystem move and a SQLite
commit cannot be made a single atomic operation, so the pipeline runs as
three explicit stages (preflight plan -> stage into quarantine -> commit
DB -> purge quarantine) with an all-or-nothing rollback at every stage
boundary. No Tk dependency -- menu/dialog/keyboard behavior is covered in
tests/test_sidebar_context.py and tests/test_sidebar_menu_context.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from cache_vault.core import image_assets, models
from cache_vault.core import permanent_delete as pd
from cache_vault.core.models import Clip
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _vault():
    return Vault(storage=VaultStorage(":memory:"), settings=Settings(capture_paused=True))


def _add_clips(storage, n, prefix="clip"):
    ids = []
    for i in range(n):
        c = Clip(content=f"{prefix} {i}", preview=f"{prefix} {i}")
        storage.add_clip(c)
        ids.append(c.id)
    return ids


def _add_managed_asset(storage, clip_id, data=b"\x89PNG fake-png-bytes-0123456789"):
    chash = models.bytes_hash(data)
    clip = storage.get_clip(clip_id)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip_id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip_id, "png"), width=1, height=1,
    )
    storage.save_clip_asset(record, data)
    return record, data


# --- storage.hard_delete_many (DB-only bulk mutation) --------------------------


def test_hard_delete_many_deletes_only_soft_deleted(storage):
    ids = _add_clips(storage, 3)
    for cid in ids:
        storage.soft_delete(cid)

    result = storage.hard_delete_many(ids)

    assert sorted(result.succeeded) == sorted(ids)
    assert result.skipped == ()
    assert storage.list_clips(None) == []
    for cid in ids:
        assert storage.get_clip(cid) is None


def test_hard_delete_many_dedupes_input(storage):
    ids = _add_clips(storage, 2)
    for cid in ids:
        storage.soft_delete(cid)

    result = storage.hard_delete_many([ids[0], ids[0], ids[1], ids[0]])

    assert result.succeeded == (ids[0], ids[1])
    assert result.succeeded_count == 2


def test_hard_delete_many_skips_active_and_nonexistent(storage):
    ids = _add_clips(storage, 2)
    storage.soft_delete(ids[0])
    # ids[1] stays active (never soft-deleted); "ghost" doesn't exist.
    result = storage.hard_delete_many([ids[0], ids[1], "ghost-id"])

    assert result.succeeded == (ids[0],)
    assert set(result.skipped) == {ids[1], "ghost-id"}
    assert storage.get_clip(ids[1]) is not None  # untouched, still active


class _FailingDeleteConnProxy:
    def __init__(self, real_conn, *, fail_after: int):
        self._real = real_conn
        self._n = 0
        self._fail_after = fail_after

    def execute(self, sql, params=()):
        if sql.startswith("DELETE FROM clips WHERE id"):
            self._n += 1
            if self._n == self._fail_after:
                raise RuntimeError("injected failure")
        return self._real.execute(sql, params)

    def commit(self):
        return self._real.commit()

    def rollback(self):
        return self._real.rollback()


def test_hard_delete_many_injected_failure_rolls_back_everything(storage):
    ids = _add_clips(storage, 4)
    for cid in ids:
        storage.soft_delete(cid)

    real_conn = storage.conn
    storage.conn = _FailingDeleteConnProxy(real_conn, fail_after=3)
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            storage.hard_delete_many(ids)
    finally:
        storage.conn = real_conn

    for cid in ids:
        clip = storage.get_clip(cid)
        assert clip is not None
        assert clip.deleted_at is not None


# --- build_deletion_plan (read-only preflight) ---------------------------------


def test_build_deletion_plan_separates_eligible_and_skipped(storage):
    ids = _add_clips(storage, 3)
    storage.soft_delete(ids[0])
    storage.soft_delete(ids[1])
    # ids[2] stays active.

    plan = pd.build_deletion_plan(storage, [ids[0], ids[1], ids[2], "ghost"])

    assert set(plan.eligible_ids) == {ids[0], ids[1]}
    assert plan.skipped[ids[2]] == "not_in_recently_removed"
    assert plan.skipped["ghost"] == "missing"


def test_build_deletion_plan_computes_planned_bytes_and_asset_count(storage, assets_home):
    ids = _add_clips(storage, 2)
    _record, data = _add_managed_asset(storage, ids[0])
    for cid in ids:
        storage.soft_delete(cid)

    plan = pd.build_deletion_plan(storage, ids)

    assert plan.asset_count == 1
    assert plan.planned_bytes == len(data)
    assert ids[1] not in plan.asset_rows


def test_build_deletion_plan_never_touches_path_only_clip_asset_lookup(storage, tmp_path):
    """A path-only clip has no clip_assets row at all -- the plan must
    never resolve or reference its external file path, only whatever
    (nonexistent) clip_assets row belongs to its id.
    """
    external = tmp_path / "external.txt"
    external.write_text("hello")
    clip = Clip(content=str(external), classification=models.CLASS_PATH)
    storage.add_clip(clip)
    storage.soft_delete(clip.id)

    plan = pd.build_deletion_plan(storage, [clip.id])

    assert plan.eligible_ids == (clip.id,)
    assert clip.id not in plan.asset_rows
    assert clip.id not in plan.managed_paths
    assert plan.planned_bytes == 0


def test_build_deletion_plan_duplicate_ids_deduped_before_counting(storage):
    ids = _add_clips(storage, 1)
    storage.soft_delete(ids[0])

    plan = pd.build_deletion_plan(storage, [ids[0], ids[0], ids[0]])

    assert plan.requested_ids == (ids[0],)
    assert plan.eligible_ids == (ids[0],)


# --- image_assets.resolve_managed_path (filesystem boundary) -------------------


def test_resolve_managed_path_accepts_normal_storage_name(assets_home):
    name = image_assets.make_storage_name("clip123", "png")
    image_assets.write_asset_file(name, b"x")
    path = image_assets.resolve_managed_path(name)
    assert path is not None
    assert path.is_file()
    assert path.parent == image_assets.assets_dir().resolve()


def test_resolve_managed_path_rejects_traversal(assets_home):
    assert image_assets.resolve_managed_path("../outside.png") is None
    assert image_assets.resolve_managed_path("..\\outside.png") is None
    assert image_assets.resolve_managed_path("sub/dir.png") is None


def test_resolve_managed_path_rejects_absolute_path(assets_home, tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    assert image_assets.resolve_managed_path(str(outside)) is None


def test_resolve_managed_path_rejects_empty_or_missing_name(assets_home):
    assert image_assets.resolve_managed_path("") is None
    assert image_assets.resolve_managed_path(None) is None


def test_resolve_managed_path_rejects_symlink_escape(assets_home, tmp_path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    target = outside_dir / "real.png"
    target.write_bytes(b"secret-data-outside-the-managed-root")

    link = image_assets.assets_dir() / "escape.png"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation not permitted in this environment")

    assert image_assets.resolve_managed_path("escape.png") is None


def test_build_deletion_plan_excludes_clip_with_unsafe_asset_path(storage, assets_home):
    """If a clip_assets row's storage_name somehow resolves outside the
    managed root, the whole clip is excluded from the plan rather than
    deleting its database row while leaving an asset we refuse to touch
    dangling -- see the module docstring for the rationale.
    """
    ids = _add_clips(storage, 1)
    storage.soft_delete(ids[0])
    data = b"unsafe"
    chash = models.bytes_hash(data)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=ids[0], mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=models.now_iso(), original_name=None,
        storage_name="../escape.png", width=1, height=1,
    )
    storage.conn.execute(
        """INSERT INTO clip_assets (
            asset_id, clip_id, mime_type, file_ext, size_bytes, sha256,
            created_at, original_name, storage_name, width, height
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (record.asset_id, record.clip_id, record.mime_type, record.file_ext,
         record.size_bytes, record.sha256, record.created_at,
         record.original_name, record.storage_name, record.width, record.height),
    )
    storage.conn.commit()

    plan = pd.build_deletion_plan(storage, ids)

    assert plan.eligible_ids == ()
    assert plan.skipped[ids[0]] == "unsafe_asset_path"


# --- stage_managed_files / purge_staged_files (quarantine pipeline) ------------


def test_stage_managed_files_moves_into_quarantine(storage, assets_home):
    ids = _add_clips(storage, 1)
    record, data = _add_managed_asset(storage, ids[0])
    storage.soft_delete(ids[0])
    plan = pd.build_deletion_plan(storage, ids)
    original_path = image_assets.assets_dir() / record.storage_name

    staging = pd.stage_managed_files(plan)

    assert staging.ok
    assert not original_path.exists()
    assert staging.staged[ids[0]].is_file()
    assert staging.staged[ids[0]].read_bytes() == data
    assert staging.originals[ids[0]] == original_path.resolve()


def test_stage_managed_files_failure_restores_already_staged(storage, assets_home):
    ids = _add_clips(storage, 3)
    records = []
    for i, cid in enumerate(ids):
        rec, _data = _add_managed_asset(storage, cid, data=f"data-{i}".encode())
        records.append(rec)
        storage.soft_delete(cid)
    plan = pd.build_deletion_plan(storage, ids)

    # Remove the second clip's file out from under the plan so staging
    # fails partway through -- the first clip's file must already be in
    # quarantine at that point, proving rollback genuinely moves it back.
    (image_assets.assets_dir() / records[1].storage_name).unlink()

    staging = pd.stage_managed_files(plan)

    assert not staging.ok
    assert records[1].clip_id in staging.failed
    for i, rec in enumerate(records):
        if i == 1:
            continue
        assert (image_assets.assets_dir() / rec.storage_name).is_file()
    assert staging.staged == {}


def test_purge_staged_files_removes_only_listed_ids(storage, assets_home):
    ids = _add_clips(storage, 2)
    _rec0, data0 = _add_managed_asset(storage, ids[0], data=b"aaa-data")
    _rec1, _data1 = _add_managed_asset(storage, ids[1], data=b"bbb-data")
    for cid in ids:
        storage.soft_delete(cid)
    plan = pd.build_deletion_plan(storage, ids)
    staging = pd.stage_managed_files(plan)
    assert staging.ok

    purge = pd.purge_staged_files(staging, [ids[0]])

    assert purge.purged == {ids[0]: len(data0)}
    assert purge.deferred == {}
    assert not staging.staged[ids[0]].exists()
    assert staging.staged[ids[1]].is_file()  # untouched -- not in the purge list


def test_purge_staged_files_partial_failure_defers_without_miscounting(storage, assets_home):
    ids = _add_clips(storage, 2)
    _rec0, data0 = _add_managed_asset(storage, ids[0], data=b"data-one")
    rec1, _data1 = _add_managed_asset(storage, ids[1], data=b"data-two")
    for cid in ids:
        storage.soft_delete(cid)
    plan = pd.build_deletion_plan(storage, ids)
    staging = pd.stage_managed_files(plan)

    real_unlink = Path.unlink

    def failing_unlink(self, *a, **kw):
        if self.name == rec1.storage_name:
            raise OSError("simulated purge failure")
        return real_unlink(self, *a, **kw)

    with mock.patch.object(Path, "unlink", failing_unlink):
        purge = pd.purge_staged_files(staging, ids)

    assert purge.purged == {ids[0]: len(data0)}
    assert set(purge.deferred) == {ids[1]}
    assert staging.staged[ids[1]].is_file()  # left in quarantine for retry


def test_unstage_files_restores_only_requested_ids(storage, assets_home):
    ids = _add_clips(storage, 2)
    _rec0, _data0 = _add_managed_asset(storage, ids[0])
    _rec1, _data1 = _add_managed_asset(storage, ids[1])
    for cid in ids:
        storage.soft_delete(cid)
    plan = pd.build_deletion_plan(storage, ids)
    staging = pd.stage_managed_files(plan)
    original0 = staging.originals[ids[0]]
    original1 = staging.originals[ids[1]]

    pd.unstage_files(staging, [ids[0]])

    assert original0.is_file()  # restored
    assert not original1.is_file()  # still quarantined


# --- Vault.permanently_delete_many: full pipeline ------------------------------


def test_permanently_delete_many_managed_file_deleted_and_bytes_reclaimed(assets_home):
    v = _vault()
    try:
        clip = v.capture("removed clip", force=True)
        _record, data = _add_managed_asset(v.storage, clip.id)
        v.storage.soft_delete(clip.id)

        result = v.permanently_delete_many([clip.id], confirmation_mode="selected")

        assert result.deleted_ids == (clip.id,)
        assert result.managed_assets_deleted == 1
        assert result.disk_bytes_reclaimed == len(data)
        assert result.complete
        assert v.storage.get_clip(clip.id) is None
        assert v.storage.get_asset_record(clip.id) is None
    finally:
        v.close()


def test_permanently_delete_many_external_path_only_file_byte_identical(tmp_path, assets_home):
    external_dir = tmp_path / "outside_vault"
    external_dir.mkdir()
    external = external_dir / "doc.txt"
    external.write_text("external content that must never change", encoding="utf-8")
    sha_before = models.bytes_hash(external.read_bytes())
    size_before = external.stat().st_size
    mtime_before = external.stat().st_mtime_ns

    v = _vault()
    try:
        clip = Clip(content=str(external), classification=models.CLASS_PATH)
        v.storage.add_clip(clip)
        v.storage.soft_delete(clip.id)

        with mock.patch("os.remove", wraps=os.remove) as os_remove, \
             mock.patch("os.unlink", wraps=os.unlink) as os_unlink, \
             mock.patch("cache_vault.core.image_assets.delete_asset_file") as delete_asset_file, \
             mock.patch("cache_vault.core.image_assets.write_asset_file") as write_asset_file:
            result = v.permanently_delete_many([clip.id], confirmation_mode="selected")

        os_remove.assert_not_called()
        os_unlink.assert_not_called()
        delete_asset_file.assert_not_called()
        write_asset_file.assert_not_called()

        assert result.deleted_ids == (clip.id,)
        assert v.storage.get_clip(clip.id) is None  # the clip's DB row is gone...
        assert external.is_file()  # ...but the external file is completely untouched
        assert models.bytes_hash(external.read_bytes()) == sha_before
        assert external.stat().st_size == size_before
        assert external.stat().st_mtime_ns == mtime_before
    finally:
        v.close()


def test_permanently_delete_many_database_failure_restores_staged_files_and_raises(assets_home):
    storage = VaultStorage(":memory:")
    v = Vault(storage=storage, settings=Settings(capture_paused=True))
    try:
        ids = _add_clips(storage, 2)
        rec0, data0 = _add_managed_asset(storage, ids[0])
        for cid in ids:
            storage.soft_delete(cid)
        original_path = image_assets.assets_dir() / rec0.storage_name

        with mock.patch.object(
            storage, "hard_delete_many", side_effect=RuntimeError("injected db failure"),
        ):
            with pytest.raises(RuntimeError, match="injected db failure"):
                v.permanently_delete_many(ids, confirmation_mode="selected")

        # Every staged file restored to its original location; DB untouched.
        assert original_path.is_file()
        assert original_path.read_bytes() == data0
        for cid in ids:
            clip = storage.get_clip(cid)
            assert clip is not None
            assert clip.deleted_at is not None

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert events == []
    finally:
        v.close()


def test_permanently_delete_many_partial_purge_reports_deferred_and_stays_partial(assets_home):
    v = _vault()
    try:
        clip1 = v.capture("clip one", force=True)
        clip2 = v.capture("clip two", force=True)
        _rec1, data1 = _add_managed_asset(v.storage, clip1.id, data=b"data-one")
        rec2, _data2 = _add_managed_asset(v.storage, clip2.id, data=b"data-two")
        v.storage.soft_delete(clip1.id)
        v.storage.soft_delete(clip2.id)

        real_unlink = Path.unlink

        def failing_unlink(self, *a, **kw):
            if self.name == rec2.storage_name:
                raise OSError("simulated purge failure")
            return real_unlink(self, *a, **kw)

        with mock.patch.object(Path, "unlink", failing_unlink):
            result = v.permanently_delete_many([clip1.id, clip2.id], confirmation_mode="delete_all")

        # The database change already committed for BOTH clips -- a purge
        # failure never rolls back an already-committed deletion.
        assert set(result.deleted_ids) == {clip1.id, clip2.id}
        assert v.storage.get_clip(clip1.id) is None
        assert v.storage.get_clip(clip2.id) is None

        assert result.managed_assets_deleted == 1
        assert result.disk_bytes_reclaimed == len(data1)
        assert result.managed_files_deferred == 1
        assert not result.complete

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert len(events) == 1
        details = events[0]["details"]
        assert details["result"] == "partial"
        assert details["disk_bytes_reclaimed"] == len(data1)
        assert details["managed_files_deferred"] == 1
    finally:
        v.close()


def test_permanently_delete_many_duplicate_ids_do_not_inflate_counts(assets_home):
    v = _vault()
    try:
        clip = v.capture("dup test", force=True)
        v.storage.soft_delete(clip.id)

        result = v.permanently_delete_many([clip.id, clip.id, clip.id], confirmation_mode="selected")

        assert result.requested_count == 1
        assert result.deleted_count == 1
        assert result.deleted_ids == (clip.id,)

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert len(events) == 1
        assert events[0]["details"]["clip_id_count"] == 1
    finally:
        v.close()


def test_permanently_delete_many_restored_between_plan_and_commit_is_skipped(assets_home):
    """The exact race the storage-layer re-check guards against: a clip
    is eligible when the plan is built, but gets restored by something
    else before the database transaction actually runs. It must survive,
    not be deleted -- and its managed file must be moved back out of
    quarantine, not left stranded there.
    """
    v = _vault()
    try:
        clip = v.capture("raced clip", force=True)
        record, data = _add_managed_asset(v.storage, clip.id)
        v.storage.soft_delete(clip.id)

        real_hard_delete_many = v.storage.hard_delete_many

        def racy_hard_delete_many(clip_ids):
            v.storage.restore(clip.id)
            return real_hard_delete_many(clip_ids)

        with mock.patch.object(v.storage, "hard_delete_many", side_effect=racy_hard_delete_many):
            result = v.permanently_delete_many([clip.id], confirmation_mode="selected")

        assert result.deleted_ids == ()
        assert result.skipped[clip.id] == "restored_before_commit"
        reloaded = v.storage.get_clip(clip.id)
        assert reloaded is not None
        assert reloaded.deleted_at is None  # genuinely restored, not deleted

        asset_path = image_assets.assets_dir() / record.storage_name
        assert asset_path.is_file()
        assert asset_path.read_bytes() == data
    finally:
        v.close()


def test_permanently_delete_many_missing_before_execution_is_skipped_honestly(assets_home):
    v = _vault()
    try:
        clip = v.capture("will vanish", force=True)
        v.storage.soft_delete(clip.id)
        v.storage.conn.execute("DELETE FROM clips WHERE id = ?", (clip.id,))
        v.storage.conn.commit()

        result = v.permanently_delete_many([clip.id], confirmation_mode="selected")

        assert result.deleted_ids == ()
        assert result.skipped[clip.id] == "missing"
    finally:
        v.close()


def test_permanently_delete_many_no_eligible_ids_produces_no_receipt(assets_home):
    v = _vault()
    try:
        clip = v.capture("still active", force=True)  # never soft-deleted

        before = len(v.events.recent())
        result = v.permanently_delete_many([clip.id], confirmation_mode="selected")

        assert result.deleted_ids == ()
        assert result.skipped[clip.id] == "not_in_recently_removed"
        assert len(v.events.recent()) == before
        assert v.storage.get_clip(clip.id) is not None  # completely untouched
    finally:
        v.close()


def test_permanently_delete_many_receipt_bounded_and_no_full_content(assets_home):
    secret_text = "SENSITIVE-CLIPBOARD-MARKER-71ab9c"
    v = _vault()
    try:
        clip = v.capture(secret_text, force=True)
        v.storage.soft_delete(clip.id)

        result = v.permanently_delete_many([clip.id], confirmation_mode="selected")
        assert result.deleted_ids == (clip.id,)

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert len(events) == 1
        details = events[0]["details"]
        import json
        serialized = json.dumps(details)
        assert secret_text not in serialized
        assert details["action"] == models.ACTION_PERMANENT_DELETE_BATCH
        assert details["source_context"] == "recently_removed"
        assert details["clip_ids"] == [clip.id]
        assert details["deleted_count"] == 1
        assert details["clip_id_count"] == 1
    finally:
        v.close()


def test_permanently_delete_many_distinguishes_selected_vs_delete_all_mode(assets_home):
    v = _vault()
    try:
        clip_a = v.capture("a", force=True)
        clip_b = v.capture("b", force=True)
        v.storage.soft_delete(clip_a.id)
        v.storage.soft_delete(clip_b.id)

        v.permanently_delete_many([clip_a.id], confirmation_mode="selected")
        v.permanently_delete_many([clip_b.id], confirmation_mode="delete_all")

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        modes = {e["details"]["confirmation_mode"] for e in events}
        assert modes == {"selected", "delete_all"}
    finally:
        v.close()


def test_receipt_ledger_shows_partial_not_success_for_partial_result():
    """A partial final-purge result must render as Partial in the
    Stamped Receipts UI, never silently as Success -- _infer_result
    previously had no case for "partial"/"complete" and would have
    fallen through to the default "Success".
    """
    from cache_vault.ui.receipt_ledger import _infer_result

    assert _infer_result(models.ACTION_PERMANENT_DELETE_BATCH, {"result": "partial"}) == "Partial"
    assert _infer_result(models.ACTION_PERMANENT_DELETE_BATCH, {"result": "complete"}) == "Success"


def test_permanently_delete_many_existing_restore_operations_unaffected(assets_home):
    """Restore (soft_delete_many/restore_many) must keep working exactly
    as before -- this feature only adds a new terminal action, it must
    not change what restoring means.
    """
    v = _vault()
    try:
        clip = v.capture("restorable", force=True)
        v.storage.soft_delete(clip.id)

        result = v.restore_many([clip.id])

        assert result.succeeded == (clip.id,)
        reloaded = v.storage.get_clip(clip.id)
        assert reloaded.deleted_at is None
    finally:
        v.close()


# --- Corrective commit: unify permanent deletion, quarantine recovery ---------
# Closes the bypass a prior checkpoint review found: the single-item
# "Permanently Remove" path used to call storage.hard_delete directly,
# skipping every safety guarantee the staged pipeline provides.


def test_no_production_caller_of_storage_hard_delete_directly():
    """Source/call-graph regression: nothing under cache_vault/ may call
    ``.hard_delete(`` (the unstaged, single-id primitive) except the
    method's own definition in storage.py and the bulk atomic
    ``hard_delete_many`` name (which contains the substring but is a
    different, safe method). Every real permanent-deletion caller must
    go through ``hard_delete_many``/``permanently_delete_many`` instead.
    """
    root = Path(__file__).parents[1] / "cache_vault"
    import re
    offenders = []
    call_re = re.compile(r"\.hard_delete\(")
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if call_re.search(line):
                # storage.py's own `def hard_delete(self, clip_id):` is the
                # definition, not a call -- everything else matching is a
                # real caller and must not exist.
                if path.name == "storage.py" and line.strip().startswith("def hard_delete("):
                    continue
                offenders.append(f"{path.relative_to(root.parent)}:{lineno}: {line.strip()}")
    assert offenders == [], f"direct storage.hard_delete callers found: {offenders}"


def test_permanently_remove_docstring_describes_managed_vs_external():
    """The stale docstring the checkpoint review flagged ("Never touches
    real files") must be gone, replaced with an accurate description:
    managed CacheVault assets may be removed, external originals never
    are.
    """
    src = (Path(__file__).parents[1] / "cache_vault" / "core" / "vault.py").read_text(encoding="utf-8")
    start = src.index("def permanently_remove(")
    end = src.index("\n    def ", start + 1)
    body = src[start:end]
    assert "Never touches real files" not in body
    assert "managed" in body.lower()
    assert "external" in body.lower()


def test_permanently_remove_is_compatibility_wrapper_routing_through_pipeline(assets_home):
    """Vault.permanently_remove(clip_id) must behave identically to
    permanently_delete_many([clip_id], confirmation_mode="selected") --
    same staging, same receipt, same result type -- not a separate
    unstaged implementation.
    """
    v = _vault()
    try:
        clip = v.capture("legacy single-item wrapper", force=True)
        record, data = _add_managed_asset(v.storage, clip.id)
        v.storage.soft_delete(clip.id)

        result = v.permanently_remove(clip.id)

        assert result.deleted_ids == (clip.id,)
        assert result.managed_assets_deleted == 1
        assert result.disk_bytes_reclaimed == len(data)
        assert v.storage.get_clip(clip.id) is None
        assert v.storage.get_asset_record(clip.id) is None

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert len(events) == 1
        assert events[0]["details"]["confirmation_mode"] == "selected"
        # The old single-item-only event must never fire from the new path.
        legacy_events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENTLY_REMOVED
        ]
        assert legacy_events == []
    finally:
        v.close()


def test_permanently_remove_external_path_only_file_byte_identical(tmp_path, assets_home):
    """The single-item compatibility wrapper must give a path-only clip
    the exact same external-file protection as the bulk pipeline.
    """
    external_dir = tmp_path / "outside_vault"
    external_dir.mkdir()
    external = external_dir / "doc.txt"
    external.write_text("must never change", encoding="utf-8")
    sha_before = models.bytes_hash(external.read_bytes())

    v = _vault()
    try:
        clip = Clip(content=str(external), classification=models.CLASS_PATH)
        v.storage.add_clip(clip)
        v.storage.soft_delete(clip.id)

        result = v.permanently_remove(clip.id)

        assert result.deleted_ids == (clip.id,)
        assert external.is_file()
        assert models.bytes_hash(external.read_bytes()) == sha_before
    finally:
        v.close()


def test_permanently_remove_unsafe_managed_path_is_rejected(assets_home):
    """A clip whose asset row resolves outside the managed root must be
    excluded from deletion by the single-item wrapper too -- it's the
    same build_deletion_plan underneath, not a separate check.
    """
    v = _vault()
    try:
        clip = v.capture("unsafe path clip", force=True)
        v.storage.soft_delete(clip.id)
        data = b"unsafe"
        chash = models.bytes_hash(data)
        record = image_assets.ClipAssetRecord(
            asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
            size_bytes=len(data), sha256=chash, created_at=models.now_iso(), original_name=None,
            storage_name="../escape.png", width=1, height=1,
        )
        v.storage.conn.execute(
            """INSERT INTO clip_assets (
                asset_id, clip_id, mime_type, file_ext, size_bytes, sha256,
                created_at, original_name, storage_name, width, height
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (record.asset_id, record.clip_id, record.mime_type, record.file_ext,
             record.size_bytes, record.sha256, record.created_at,
             record.original_name, record.storage_name, record.width, record.height),
        )
        v.storage.conn.commit()

        result = v.permanently_remove(clip.id)

        assert result.deleted_ids == ()
        assert result.skipped[clip.id] == "unsafe_asset_path"
        assert v.storage.get_clip(clip.id) is not None  # untouched, still soft-deleted
    finally:
        v.close()


def test_permanently_remove_database_failure_restores_staged_file(assets_home):
    storage = VaultStorage(":memory:")
    v = Vault(storage=storage, settings=Settings(capture_paused=True))
    try:
        clip = v.capture("db failure single", force=True)
        record, data = _add_managed_asset(storage, clip.id)
        storage.soft_delete(clip.id)
        original_path = image_assets.assets_dir() / record.storage_name

        with mock.patch.object(storage, "hard_delete_many", side_effect=RuntimeError("injected")):
            with pytest.raises(RuntimeError, match="injected"):
                v.permanently_remove(clip.id)

        assert original_path.is_file()
        assert original_path.read_bytes() == data
        reloaded = storage.get_clip(clip.id)
        assert reloaded is not None
        assert reloaded.deleted_at is not None
    finally:
        v.close()


def test_permanently_remove_partial_purge_reports_partial(assets_home):
    v = _vault()
    try:
        clip = v.capture("single item partial purge", force=True)
        _record, data = _add_managed_asset(v.storage, clip.id)
        v.storage.soft_delete(clip.id)

        with mock.patch.object(Path, "unlink", side_effect=OSError("simulated purge failure")):
            result = v.permanently_remove(clip.id)

        assert result.deleted_ids == (clip.id,)  # DB record still deleted
        assert not result.complete
        assert result.managed_files_deferred == 1
        assert result.disk_bytes_reclaimed == 0  # never claimed as reclaimed

        events = [
            e for e in v.events.recent()
            if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
        ]
        assert events[0]["details"]["result"] == "partial"
    finally:
        v.close()


# --- Durable quarantine journal: survives a process restart -------------------


def test_retry_deferred_permanent_deletions_with_no_entries_is_noop(assets_home):
    v = _vault()
    try:
        recovery = v.retry_deferred_permanent_deletions()
        assert recovery.recovered_clip_ids == ()
        assert recovery.still_deferred_clip_ids == ()
        assert recovery.disk_bytes_reclaimed == 0
        assert v.events.recent() == []
    finally:
        v.close()


def test_deferred_journal_entry_has_no_full_content(assets_home):
    """Journal entries carry only bounded identifiers/metadata -- never
    clipboard content -- per the same privacy contract as every other
    receipt in this codebase.
    """
    v = _vault()
    try:
        clip = v.capture("SECRET-MARKER-TEXT-abc123", force=True)
        _record, _data = _add_managed_asset(v.storage, clip.id)
        v.storage.soft_delete(clip.id)

        with mock.patch.object(Path, "unlink", side_effect=OSError("simulated purge failure")):
            v.permanently_delete_many([clip.id], confirmation_mode="selected")

        journal = pd.read_deferred_journal()
        assert len(journal) == 1
        entry = journal[0]
        assert entry["clip_id"] == clip.id
        assert set(entry.keys()) == {
            "entry_id", "clip_id", "asset_id", "quarantine_path", "original_path",
            "size_bytes", "sha256", "reason", "created_at", "retry_status",
        }
        serialized = json.dumps(entry)
        assert "SECRET-MARKER-TEXT-abc123" not in serialized
    finally:
        v.close()


def test_retry_deferred_permanent_deletions_rejects_unsafe_journal_path(assets_home, tmp_path):
    """Even a journal entry itself must not be trusted blindly -- if its
    quarantine_path somehow doesn't resolve inside the managed
    quarantine root, retry must refuse to touch it rather than deleting
    an arbitrary path a corrupted/tampered journal file names.
    """
    outside = tmp_path / "outside_quarantine.png"
    outside.write_bytes(b"must not be touched")

    pd._write_deferred_journal([{
        "entry_id": models.new_id(), "clip_id": "ghost-clip", "asset_id": "ghost-asset",
        "quarantine_path": str(outside), "original_path": str(outside),
        "size_bytes": 20, "sha256": "deadbeef", "reason": "test fixture",
        "created_at": models.now_iso(), "retry_status": "pending",
    }])

    events_stub = _vault()
    try:
        recovery = pd.retry_deferred_permanent_deletions(events_stub.events)
        assert recovery.recovered_clip_ids == ()
        assert recovery.still_deferred_clip_ids == ("ghost-clip",)
        assert outside.is_file()  # never touched
        assert outside.read_bytes() == b"must not be touched"
    finally:
        events_stub.close()


def test_permanently_delete_many_restart_recovers_deferred_purge(tmp_path, monkeypatch):
    """The full restart proof: a deferred purge from one Vault instance
    is discovered and successfully retried by a brand-new instance
    against the same isolated profile, with bytes reported exactly once
    and no external file ever touched.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    db_path = tmp_path / "vault.db"
    external_dir = tmp_path / "outside_vault"
    external_dir.mkdir()
    external = external_dir / "unrelated.txt"
    external.write_text("external content, never touched", encoding="utf-8")
    external_sha_before = models.bytes_hash(external.read_bytes())

    storage1 = VaultStorage(db_path)
    v1 = Vault(storage=storage1, settings=Settings(capture_paused=True))
    clip = v1.capture("will be recovered after restart", force=True)
    record, data = _add_managed_asset(v1.storage, clip.id)
    v1.storage.soft_delete(clip.id)

    with mock.patch.object(Path, "unlink", side_effect=OSError("simulated purge failure")):
        result = v1.permanently_delete_many([clip.id], confirmation_mode="selected")

    # 1 & 2: purge failure simulated, DB record deleted, receipt partial.
    assert result.deleted_ids == (clip.id,)
    assert not result.complete
    events1 = [
        e for e in v1.events.recent()
        if e.get("event_type") == models.EVENT_PERMANENT_DELETE_BATCH
    ]
    assert events1[0]["details"]["result"] == "partial"

    quarantine_path = Path(pd.read_deferred_journal()[0]["quarantine_path"])
    assert quarantine_path.is_file()

    # 3: close the first instance.
    v1.close()

    # 4: open a brand-new instance against the same isolated profile.
    storage2 = VaultStorage(db_path)
    v2 = Vault(storage=storage2, settings=Settings(capture_paused=True))

    # 5: discover the deferred entry via the durable journal alone.
    journal = pd.read_deferred_journal()
    assert len(journal) == 1
    assert journal[0]["clip_id"] == clip.id

    # 6: retry successfully (Path.unlink is no longer mocked here).
    recovery = v2.retry_deferred_permanent_deletions()
    assert recovery.recovered_clip_ids == (clip.id,)

    # 7: quarantined file is gone.
    assert not quarantine_path.exists()

    # 8: recovered bytes reported exactly once.
    assert recovery.disk_bytes_reclaimed == len(data)
    recovery_events = [
        e for e in v2.events.recent()
        if e.get("event_type") == models.EVENT_PERMANENT_DELETE_RECOVERY
    ]
    assert len(recovery_events) == 1
    assert recovery_events[0]["details"]["disk_bytes_reclaimed"] == len(data)
    assert pd.read_deferred_journal() == []  # journal entry consumed, not left to double-count

    # 9: external file never touched, at any point in the whole flow.
    assert external.is_file()
    assert models.bytes_hash(external.read_bytes()) == external_sha_before

    v2.close()
