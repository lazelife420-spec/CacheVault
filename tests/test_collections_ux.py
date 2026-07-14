"""
Stream 2 — Collections UX tests.

Verifies:
- Moving a clip to a collection updates the sidebar count
- Renaming a collection updates all clips within it
- Clearing a collection removes the association but keeps clips
- Filter by collection works after move
"""

from __future__ import annotations

import pytest


def test_move_to_collection_and_list(vault):
    """A clip moved to a collection is retrievable via collection filter."""
    clip = vault.capture("collections-test-content", source_app="TestApp")
    vault.storage.set_collection(clip.id, "Work")

    clips = vault.list_clips("col:Work")
    assert any(c.id == clip.id for c in clips)


def test_sidebar_collection_count_after_move(vault):
    """After moving clips into a collection, list_collections reflects the new count."""
    clip1 = vault.capture("item alpha for work", source_app="A")
    clip2 = vault.capture("item beta for work", source_app="B")
    vault.storage.set_collection(clip1.id, "Research")
    vault.storage.set_collection(clip2.id, "Research")

    cols = vault.list_collections()
    research = next((c for c in cols if c["name"] == "Research"), None)
    assert research is not None
    assert research["count"] == 2


def test_remove_from_collection_clears_col(vault):
    """Clearing collection on a clip removes it from the collection filter."""
    clip = vault.capture("going into notes", source_app="TestApp")
    vault.storage.set_collection(clip.id, "Notes")

    # Verify it's in there
    assert any(c.id == clip.id for c in vault.list_clips("col:Notes"))

    # Clear
    vault.storage.set_collection(clip.id, None)

    # Should not be in the collection anymore
    assert not any(c.id == clip.id for c in vault.list_clips("col:Notes"))

    # But the clip itself must still exist in the vault
    db_clip = vault.storage.get_clip(clip.id)
    assert db_clip is not None
    assert db_clip.collection is None


def test_rename_collection_renames_all_clips(vault):
    """Renaming a collection must update every clip that was in it."""
    ids = []
    for i in range(3):
        clip = vault.capture(f"rename-me-{i}", source_app="TestApp")
        vault.storage.set_collection(clip.id, "OldName")
        ids.append(clip.id)

    # Simulate rename by updating all clips
    clips = vault.list_clips("col:OldName")
    for clip in clips:
        vault.storage.set_collection(clip.id, "NewName")

    # Old collection must be gone
    assert vault.list_clips("col:OldName") == []

    # New collection must have all 3
    renamed = vault.list_clips("col:NewName")
    renamed_ids = {c.id for c in renamed}
    for cid in ids:
        assert cid in renamed_ids


def test_collection_persists_after_list_clips_reload(vault):
    """Collection assignment must persist across storage reads."""
    clip = vault.capture("persistent collection member", source_app="TestApp")
    vault.storage.set_collection(clip.id, "Persistent")

    # Re-fetch from storage
    db_clip = vault.storage.get_clip(clip.id)
    assert db_clip is not None
    assert db_clip.collection == "Persistent"


def test_multiple_collections_independent(vault):
    """Clips in different collections must not bleed into each other."""
    clip_a = vault.capture("in alpha collection", source_app="TestApp")
    clip_b = vault.capture("in beta collection", source_app="TestApp")
    vault.storage.set_collection(clip_a.id, "Alpha")
    vault.storage.set_collection(clip_b.id, "Beta")

    alpha_clips = {c.id for c in vault.list_clips("col:Alpha")}
    beta_clips = {c.id for c in vault.list_clips("col:Beta")}

    assert clip_a.id in alpha_clips
    assert clip_b.id not in alpha_clips
    assert clip_b.id in beta_clips
    assert clip_a.id not in beta_clips


def test_list_collections_excludes_deleted_clips(vault):
    """Collections count must only include live clips (not Recently Removed)."""
    clip = vault.capture("will be removed", source_app="TestApp")
    vault.storage.set_collection(clip.id, "Transient")

    cols_before = {c["name"]: c["count"] for c in vault.list_collections()}
    assert cols_before.get("Transient", 0) == 1

    vault.remove_from_history(clip.id)

    cols_after = vault.list_collections()
    transient = next((c for c in cols_after if c["name"] == "Transient"), None)
    # Either absent or count 0 — the deleted clip must not be counted
    assert transient is None or transient["count"] == 0
