"""History pruning — favorites survive, pruned clips go to Recently Removed."""

from cache_vault.core.settings import Settings
from cache_vault.core.storage import (
    VaultStorage, FILTER_ALL, FILTER_FAVORITES, FILTER_RECENTLY_REMOVED,
)
from cache_vault.core.vault import Vault


def _vault(path, *, max_clips: int = 3):
    settings = Settings(history_max_clips=max_clips)
    return Vault(storage=VaultStorage(path), settings=settings)


def test_history_prune_moves_oldest_to_recently_removed(tmp_path):
    db = tmp_path / "v.db"
    v = _vault(db, max_clips=3)
    a = v.capture("first")
    b = v.capture("second")
    c = v.capture("third")
    d = v.capture("fourth")  # triggers prune of oldest (a)
    v.close()

    s = VaultStorage(db)
    assert s.get_clip(a.id).deleted_at is not None
    assert s.get_clip(b.id).deleted_at is None
    assert len(s.list_clips(FILTER_ALL)) == 3
    assert a.id in {x.id for x in s.list_clips(FILTER_RECENTLY_REMOVED)}
    s.close()


def test_favorites_survive_history_pruning(tmp_path):
    db = tmp_path / "v.db"
    v = _vault(db, max_clips=2)
    fav = v.capture("keep me")
    v.set_favorite(fav.id, True)
    v.capture("second")
    v.capture("third")  # should prune non-favorite oldest, not the favorite
    v.close()

    s = VaultStorage(db)
    assert s.get_clip(fav.id).deleted_at is None
    assert fav.id in {c.id for c in s.list_clips(FILTER_FAVORITES)}
    s.close()


def test_prune_zero_is_unlimited(vault):
    for i in range(5):
        vault.capture(f"clip {i}")
    pruned = vault.storage.prune_history(0)
    assert pruned == []
    assert len(vault.list_clips(FILTER_ALL)) == 5
