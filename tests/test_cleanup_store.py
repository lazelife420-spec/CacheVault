"""Stage B tests: Vault Cleanup Suggestions decision persistence."""

from __future__ import annotations

from cache_vault.core import cleanup_store as cs_store
from cache_vault.core.storage import VaultStorage


def test_keep_forever_suppresses_regardless_of_scan_generation(storage):
    cs_store.record_decision(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
        fingerprint="clip-1", clip_id="clip-1", decision=cs_store.DECISION_KEEP_FOREVER,
        rule_version=1,
    )
    assert cs_store.is_suppressed(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
        fingerprint="clip-1", clip_id="clip-1", current_scan_generation="scan-2",
    )


def test_keep_only_suppresses_current_scan_generation(storage):
    cs_store.record_decision(
        storage, category="repeated_text", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-a", decision=cs_store.DECISION_KEEP, rule_version=1,
        scan_generation="scan-1",
    )
    assert cs_store.is_suppressed(
        storage, category="repeated_text", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-a", current_scan_generation="scan-1",
    )
    # A new scan run (different generation) is NOT suppressed by an old "keep".
    assert not cs_store.is_suppressed(
        storage, category="repeated_text", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-a", current_scan_generation="scan-2",
    )


def test_ignore_group_invalidated_when_fingerprint_changes(storage):
    """Simulates a duplicate group gaining a new member: the caller
    recomputes the fingerprint (proven in cleanup_suggestions.py's own
    test_duplicate_group_membership_changes_fingerprint), and the old
    "ignored" decision simply doesn't match the new fingerprint anymore.
    """
    cs_store.record_decision(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-before", decision=cs_store.DECISION_IGNORED, rule_version=1,
    )
    assert cs_store.is_suppressed(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-before",
    )
    # membership changed -> new fingerprint -> no longer suppressed
    assert not cs_store.is_suppressed(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_GROUP,
        fingerprint="fp-after",
    )


def test_no_decision_means_not_suppressed(storage):
    assert not cs_store.is_suppressed(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-x",
    )


def test_removed_is_historical_not_a_suppression(storage):
    cs_store.record_removed(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
        fingerprint="clip-2", clip_id="clip-2", rule_version=1,
    )
    assert not cs_store.is_suppressed(
        storage, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
        fingerprint="clip-2", clip_id="clip-2",
    )


def test_clear_decision_removes_keep_forever(storage):
    cs_store.record_decision(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-3",
        clip_id="clip-3", decision=cs_store.DECISION_KEEP_FOREVER, rule_version=1,
    )
    cs_store.clear_decision(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-3",
        clip_id="clip-3",
    )
    assert not cs_store.is_suppressed(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-3",
    )


def test_re_recording_a_decision_upserts_not_duplicates(storage):
    cs_store.record_decision(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-4",
        clip_id="clip-4", decision=cs_store.DECISION_KEEP, rule_version=1, scan_generation="s1",
    )
    cs_store.record_decision(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-4",
        clip_id="clip-4", decision=cs_store.DECISION_KEEP_FOREVER, rule_version=1,
    )
    rows = storage.conn.execute(
        "SELECT COUNT(*) FROM clip_cleanup_decisions WHERE clip_id = 'clip-4'"
    ).fetchone()[0]
    assert rows == 1
    assert cs_store.is_suppressed(
        storage, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="clip-4",
        clip_id="clip-4", current_scan_generation="anything",
    )  # now keep_forever, not the old scan-tied keep


def test_item_and_group_scope_do_not_collide_on_same_fingerprint(storage):
    """A group fingerprint and an item fingerprint could theoretically be
    equal strings by coincidence -- scope must keep them independent.
    """
    cs_store.record_decision(
        storage, category="repeated_text", scope=cs_store.SCOPE_GROUP,
        fingerprint="shared-fp", decision=cs_store.DECISION_IGNORED, rule_version=1,
    )
    assert not cs_store.is_suppressed(
        storage, category="repeated_text", scope=cs_store.SCOPE_ITEM,
        fingerprint="shared-fp", clip_id="some-clip",
    )


def test_decision_persists_across_restart(tmp_path):
    """Keep forever must survive an app restart -- a fresh VaultStorage
    opened against the same on-disk database must see the same decision.
    """
    db_path = tmp_path / "vault.db"
    s1 = VaultStorage(str(db_path))
    cs_store.record_decision(
        s1, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
        fingerprint="clip-5", clip_id="clip-5", decision=cs_store.DECISION_KEEP_FOREVER,
        rule_version=1,
    )
    s1.close()

    s2 = VaultStorage(str(db_path))
    try:
        assert cs_store.is_suppressed(
            s2, category="exact_duplicate_screenshot", scope=cs_store.SCOPE_ITEM,
            fingerprint="clip-5", clip_id="clip-5",
        )
    finally:
        s2.close()


def test_migration_creates_table_on_pre_existing_database(tmp_path):
    """A database created before this feature existed must gain the new
    table transparently on next open (CREATE TABLE IF NOT EXISTS via the
    shared _SCHEMA executescript), without losing existing data.
    """
    db_path = tmp_path / "old_vault.db"
    s1 = VaultStorage(str(db_path))
    from cache_vault.core.models import Clip

    s1.add_clip(Clip(content="pre-existing clip", content_hash="abc"))
    s1.close()

    # Reopening runs the same _SCHEMA executescript again -- must not error
    # and must not disturb the pre-existing clip.
    s2 = VaultStorage(str(db_path))
    try:
        clips = s2.list_clips()
        assert len(clips) == 1
        assert clips[0].content == "pre-existing clip"
        cs_store.record_decision(
            s2, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="new-clip",
            clip_id="new-clip", decision=cs_store.DECISION_KEEP_FOREVER, rule_version=1,
        )
        assert cs_store.is_suppressed(
            s2, category="tiny_image", scope=cs_store.SCOPE_ITEM, fingerprint="new-clip",
            clip_id="new-clip",
        )
    finally:
        s2.close()
