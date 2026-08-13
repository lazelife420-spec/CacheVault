"""Clear All Clips: the supported, recoverable way to empty the vault.

The capability under test exists so that emptying the vault never
requires manual SQLite work. The regression these tests defend is
specifically "the vault was emptied and then CacheVault could no longer
save new clips": every path here proves capture still works afterwards,
and that nothing outside ``clips.deleted_at`` was touched.

Mostly Tk-free -- the menu matrix is pure logic and the mutation is a
storage/vault concern. The two shell-level tests read the dispatch source
so they hold on a headless runner.
"""

from __future__ import annotations

import inspect
from unittest import mock

import pytest

from cache_vault.core import models
from cache_vault.core import sidebar_menu_context as smc
from cache_vault.core import storage as S
from cache_vault.core.models import Clip
from cache_vault.core.search import SearchQuery
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


def _ctx(item_count=0, active=True, row_key=None):
    key = row_key or S.FILTER_ALL
    return smc.build_sidebar_invocation_context(
        key,
        active_key=key if active else S.FILTER_FAVORITES,
        collection_name=None,
        visible_selected_ids=(),
        matching=None,
        item_count=item_count,
    )


def _cmd(commands, key):
    for c in commands:
        if c.key == key:
            return c
    return None


def _all_ids(storage):
    ids = []
    with storage.clip_id_snapshot(SearchQuery(filter_name=S.FILTER_ALL)) as (count, batches):
        for batch in batches:
            ids.extend(batch)
    return ids


# --- STEP 2: the control exists and states an exact count -------------------


def test_clear_all_clips_command_exists_in_all_clips_menu():
    cmds = smc.sidebar_command_matrix(_ctx(item_count=7))
    cmd = _cmd(cmds, smc.CMD_CLEAR_ALL_CLIPS)
    assert cmd is not None
    assert cmd.enabled


def test_clear_all_clips_label_states_exact_count_and_destination():
    cmd = _cmd(smc.sidebar_command_matrix(_ctx(item_count=2052)), smc.CMD_CLEAR_ALL_CLIPS)
    assert "2052" in cmd.label
    # Never just "Clear all" -- the label must say where the clips go.
    assert "Recently Removed" in cmd.label


def test_clear_all_clips_label_is_singular_for_one_clip():
    cmd = _cmd(smc.sidebar_command_matrix(_ctx(item_count=1)), smc.CMD_CLEAR_ALL_CLIPS)
    assert "1 clip " in cmd.label and "clips" not in cmd.label


def test_clear_all_clips_disabled_with_no_items():
    cmd = _cmd(smc.sidebar_command_matrix(_ctx(item_count=0)), smc.CMD_CLEAR_ALL_CLIPS)
    assert cmd is not None
    assert not cmd.enabled
    assert cmd.reason == "no items"


def test_clear_all_clips_enabled_even_when_row_not_active():
    """View-wide and id-re-resolving, like Restore all / Empty collection."""
    cmd = _cmd(
        smc.sidebar_command_matrix(_ctx(item_count=5, active=False)),
        smc.CMD_CLEAR_ALL_CLIPS,
    )
    assert cmd.enabled


def test_clear_all_clips_absent_from_other_sidebar_rows():
    for key in (S.FILTER_FAVORITES, S.FILTER_RECENTLY_REMOVED, S.FILTER_SCREENSHOTS):
        cmds = smc.sidebar_command_matrix(_ctx(item_count=5, row_key=key))
        assert _cmd(cmds, smc.CMD_CLEAR_ALL_CLIPS) is None, key


def test_clear_all_clips_is_not_labelled_like_permanent_deletion():
    """It must not read as irreversible -- that wording belongs only to
    the Recently Removed permanent command."""
    cmd = _cmd(smc.sidebar_command_matrix(_ctx(item_count=3)), smc.CMD_CLEAR_ALL_CLIPS)
    lowered = cmd.label.lower()
    assert "permanent" not in lowered
    assert "delete" not in lowered


# --- STEP 4: moves everything, preserves every other invariant -------------


def test_clear_all_clips_moves_every_active_clip(vault):
    ids = _add_clips(vault.storage, 12)

    result = vault.clear_all_clips(ids)

    assert result.succeeded_count == 12
    assert result.skipped_count == 0
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 0


def test_cleared_clips_land_in_recently_removed(vault):
    ids = _add_clips(vault.storage, 6)

    vault.clear_all_clips(ids)

    rr = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED))
    assert rr == 6


def test_cleared_clips_are_restorable(vault):
    ids = _add_clips(vault.storage, 5)
    vault.clear_all_clips(ids)

    restored = vault.restore_many(ids)

    assert restored.succeeded_count == 5
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 5


def test_clear_all_clips_leaves_no_active_favorites_but_keeps_the_flag(vault):
    ids = _add_clips(vault.storage, 4)
    vault.set_favorite(ids[0], True)
    vault.set_favorite(ids[1], True)
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_FAVORITES)) == 2

    vault.clear_all_clips(ids)

    # No dangling active favorites...
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_FAVORITES)) == 0
    # ...but the flag itself survives, so restoring brings the favorite back.
    assert vault.storage.get_clip(ids[0]).is_pinned
    vault.restore(ids[0])
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_FAVORITES)) == 1


def test_clear_all_clips_leaves_no_active_collection_members_but_keeps_labels(vault):
    ids = _add_clips(vault.storage, 3)
    vault.set_collection(ids[0], "Work")
    vault.set_collection(ids[1], "Work")

    vault.clear_all_clips(ids)

    q = SearchQuery(filter_name=f"{S.COLLECTION_PREFIX}Work", collection="Work")
    assert vault.storage.count_clips(q) == 0
    assert vault.storage.list_collections() == []
    # Label preserved for a clean restore.
    assert vault.storage.get_clip(ids[0]).collection == "Work"


def test_clear_all_clips_never_touches_clip_assets_or_files(vault):
    from cache_vault.core import image_assets

    clip = Clip(
        content="[Image 4x4]", preview="[Image 4x4]",
        content_type=models.CONTENT_IMAGE, classification=models.CLASS_IMAGE,
    )
    vault.storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png",
        file_ext="png", size_bytes=4, sha256="deadbeef",
        created_at=models.now_iso(), original_name="shot.png",
        storage_name=f"{clip.id}.png", width=4, height=4,
    )
    vault.storage.save_clip_asset(record, b"\x89PNG")

    vault.clear_all_clips([clip.id])

    # Row intact, file intact -- soft delete owns neither.
    assert vault.storage.has_clip_asset(clip.id)
    assert vault.storage.load_clip_asset_bytes(clip.id)[0] == b"\x89PNG"


def test_clear_all_clips_skips_already_removed_ids(vault):
    ids = _add_clips(vault.storage, 4)
    vault.storage.soft_delete(ids[0])

    result = vault.clear_all_clips(ids)

    assert result.succeeded_count == 3
    assert result.skipped == (ids[0],)


def test_clear_all_clips_with_no_ids_is_a_no_op(vault):
    _add_clips(vault.storage, 2)
    result = vault.clear_all_clips([])
    assert result.succeeded_count == 0
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 2


def test_sensitive_clip_with_expiry_lands_in_expired_not_recently_removed(vault):
    """Documents pre-existing semantics inherited from
    remove_from_history: Recently Removed is defined as
    ``deleted_at IS NOT NULL AND expires_at IS NULL``, so a clip that
    already carried an expiry shows up under Expired instead. It is still
    recoverable and its content is intact -- this is not a Clear All
    behaviour, it is how every removal in this codebase already works.
    """
    plain = Clip(content="plain one", preview="plain one")
    vault.storage.add_clip(plain)
    expiring = Clip(content="secret", preview="secret", expires_at=models.now_iso())
    vault.storage.add_clip(expiring)

    vault.clear_all_clips([plain.id, expiring.id])

    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 0
    assert vault.storage.count_clips(
        SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 1
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_EXPIRED)) == 1
    assert vault.storage.get_clip(expiring.id).content == "secret"


# --- The actual regression: capture must still work afterwards -------------


def test_text_capture_still_works_after_clear_all(vault):
    ids = _add_clips(vault.storage, 5)
    vault.clear_all_clips(ids)

    clip = vault.capture("brand new clip after clearing", force=True)

    assert clip is not None
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 1
    assert vault.storage.get_clip(clip.id).content == "brand new clip after clearing"


def test_image_capture_still_works_after_clear_all(vault):
    ids = _add_clips(vault.storage, 3)
    vault.clear_all_clips(ids)

    png = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"
    clip = vault.capture_image(png, width=8, height=8, original_name="after.png", force=True)

    assert clip is not None
    assert vault.storage.has_clip_asset(clip.id)
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 1


def test_duplicate_detection_still_works_after_clear_all(vault):
    ids = _add_clips(vault.storage, 2)
    vault.clear_all_clips(ids)

    first = vault.capture("repeated content", force=True)
    again = vault.capture("repeated content", force=True)

    assert first is not None
    # Consecutive identical capture is still collapsed, not duplicated.
    assert again is None


def test_search_and_counts_still_work_after_clear_all(vault):
    ids = _add_clips(vault.storage, 4, prefix="findable")
    vault.clear_all_clips(ids)
    vault.capture("findable needle after clear", force=True)

    hits = vault.storage.list_clips(SearchQuery(filter_name=S.FILTER_ALL, text="needle"))

    assert len(hits) == 1
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 1


def test_clear_all_then_reopen_database_still_captures(tmp_path):
    """Restart safety on a real on-disk database (not ``:memory:``):
    clear, close, reopen the same file, and capture again."""
    db = tmp_path / "cache_vault.db"

    v1 = Vault(storage=VaultStorage(db), settings=Settings())
    try:
        ids = _add_clips(v1.storage, 6)
        v1.clear_all_clips(ids)
        assert v1.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 0
    finally:
        v1.close()

    v2 = Vault(storage=VaultStorage(db), settings=Settings())
    try:
        assert v2.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 0
        assert v2.storage.count_clips(
            SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 6

        clip = v2.capture("captured after restart", force=True)

        assert clip is not None
        assert v2.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 1
    finally:
        v2.close()


# --- STEP 5/6: atomicity and honest receipts ------------------------------


class _FailingConnProxy:
    """See tests/test_bulk_vault_actions.py: sqlite3.Connection.execute is
    read-only, so a mid-batch failure is injected by swapping the
    storage's ``.conn`` reference."""

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


def test_clear_all_clips_failure_leaves_vault_completely_unchanged(vault):
    ids = _add_clips(vault.storage, 8)
    real_conn = vault.storage.conn
    vault.storage.conn = _FailingConnProxy(
        real_conn, fail_sql_prefix="UPDATE clips SET deleted_at", fail_after=5,
    )
    try:
        with pytest.raises(RuntimeError, match="injected failure"):
            vault.clear_all_clips(ids)
    finally:
        vault.storage.conn = real_conn

    # Not half-cleared: every clip is still active.
    assert vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL)) == 8
    assert vault.storage.count_clips(
        SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED)) == 0


def test_clear_all_clips_failure_writes_no_receipt_and_no_events(vault):
    ids = _add_clips(vault.storage, 6)
    before = len(vault.events.recent())
    real_conn = vault.storage.conn
    vault.storage.conn = _FailingConnProxy(
        real_conn, fail_sql_prefix="UPDATE clips SET deleted_at", fail_after=3,
    )
    try:
        with mock.patch(
            "cache_vault.core.clear_all_receipts.write_file_receipt"
        ) as receipt:
            with pytest.raises(RuntimeError):
                vault.clear_all_clips(ids)
    finally:
        vault.storage.conn = real_conn

    receipt.assert_not_called()
    assert len(vault.events.recent()) == before


def test_clear_all_clips_writes_one_summary_receipt(vault):
    ids = _add_clips(vault.storage, 5)

    with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt") as receipt:
        vault.clear_all_clips(ids)

    assert receipt.call_count == 1
    action, body = receipt.call_args[0]
    assert action == models.ACTION_CLEAR_ALL_CLIPS
    assert body["moved_to_recently_removed"] == 5
    assert body["skipped_count"] == 0
    assert body["recoverable"] is True
    assert body["destination"] == "recently_removed"
    assert body["timestamp"]
    # Honest about destroying nothing.
    assert body["clips_deleted"] == 0
    assert body["assets_deleted"] == 0
    assert body["disk_bytes_reclaimed"] == 0


def test_clear_all_clips_records_bulk_event_plus_per_clip_events(vault):
    ids = _add_clips(vault.storage, 4)

    with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt"):
        vault.clear_all_clips(ids)

    types = [e["event_type"] for e in vault.events.recent(limit=200)]
    assert types.count(models.EVENT_CLEARED_ALL_CLIPS) == 1
    assert types.count(models.EVENT_DELETED) == 4


def test_clear_all_clips_receipt_bounds_clip_ids_but_keeps_exact_count(vault):
    ids = _add_clips(vault.storage, 1005)

    with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt") as receipt:
        vault.clear_all_clips(ids)

    body = receipt.call_args[0][1]
    assert len(body["clip_ids"]) == 1000
    assert body["clip_id_count"] == 1005
    assert body["moved_to_recently_removed"] == 1005


def test_no_receipt_when_nothing_was_moved(vault):
    with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt") as receipt:
        vault.clear_all_clips([])
    receipt.assert_not_called()


def test_clear_all_clips_reuses_the_existing_bulk_move_path(vault):
    """No second implementation: the mutation must go through
    remove_from_history_many, which owns the atomic contract."""
    ids = _add_clips(vault.storage, 3)
    with mock.patch.object(
        vault, "remove_from_history_many", wraps=vault.remove_from_history_many
    ) as spy:
        with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt"):
            vault.clear_all_clips(ids)
    spy.assert_called_once()


def test_clear_all_clips_issues_no_row_deleting_sql(vault):
    """Guards the whole point of the feature: nothing may DELETE rows."""
    ids = _add_clips(vault.storage, 4)
    seen: list[str] = []
    real_conn = vault.storage.conn

    class _Recording:
        def execute(self, sql, params=()):
            seen.append(sql)
            return real_conn.execute(sql, params)

        def commit(self):
            return real_conn.commit()

        def rollback(self):
            return real_conn.rollback()

    vault.storage.conn = _Recording()
    try:
        with mock.patch("cache_vault.core.clear_all_receipts.write_file_receipt"):
            vault.clear_all_clips(ids)
    finally:
        vault.storage.conn = real_conn

    assert seen
    assert not any(sql.strip().upper().startswith("DELETE") for sql in seen)
    assert not any("DROP" in sql.upper() for sql in seen)


# --- STEP 2/5: the shell wiring (source-level, headless-safe) --------------


def test_shell_handler_confirms_before_mutating():
    from cache_vault.ui import shell

    src = inspect.getsource(shell.CacheVaultApp._sidebar_clear_all_clips)
    # The mutation may only happen inside the dialog's confirm callback.
    assert "ClearAllClipsDialog" in src
    mutate_at = src.index("clear_all_clips(ids)")
    confirm_at = src.index("def _run()")
    assert confirm_at < mutate_at, "mutation must live inside the confirm callback"


def test_shell_handler_reresolves_ids_and_ignores_selection():
    from cache_vault.ui import shell

    src = inspect.getsource(shell.CacheVaultApp._sidebar_clear_all_clips)
    assert "clip_id_snapshot" in src
    assert "visible_selected_ids" not in src
    assert "_resolve_sidebar_target_ids" not in src


def test_shell_handler_reports_failure_honestly():
    from cache_vault.ui import shell

    src = inspect.getsource(shell.CacheVaultApp._sidebar_clear_all_clips)
    assert "except Exception" in src
    assert "unchanged" in src


def test_clear_all_clips_is_exempt_from_active_row_guard():
    # Dispatch logic (including the stale-context allowlist) lives in
    # sidebar_actions.dispatch_sidebar_command; shell.py's
    # _dispatch_sidebar_command is now a one-line delegation to it.
    from cache_vault.ui import sidebar_actions

    src = inspect.getsource(sidebar_actions.dispatch_sidebar_command)
    assert "smc.CMD_CLEAR_ALL_CLIPS" in src


def test_dialog_is_single_step_and_states_the_count():
    from cache_vault.ui import dialogs

    src = inspect.getsource(dialogs.ClearAllClipsDialog)
    assert "Move all {total_count} clip" in src or "Move all " in src
    assert "Move All" in src
    assert "Cancel" in src
    # Recoverable action: no typed-phrase gate, and no destructive styling.
    assert "CONFIRM_PHRASE" not in src
    assert "destructive_button" not in src
    # Keyboard focus must not sit on the action button.
    assert "cancel_btn.focus_set()" in src
