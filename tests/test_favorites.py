import os

from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage, FILTER_FAVORITES, FILTER_ALL
from cache_vault.core.vault import Vault


def _vault(path):
    return Vault(storage=VaultStorage(path), settings=Settings())


def test_favorite_persists_after_restart(tmp_path):
    db = tmp_path / "v.db"
    v1 = _vault(db)
    clip = v1.capture("keep me", source_app="t")
    v1.set_favorite(clip.id, True)
    v1.close()

    v2 = _vault(db)
    reloaded = v2.storage.get_clip(clip.id)
    assert reloaded is not None
    assert reloaded.is_pinned is True
    v2.close()


def test_unfavorite_persists_after_restart(tmp_path):
    db = tmp_path / "v.db"
    v1 = _vault(db)
    clip = v1.capture("toggle me", source_app="t")
    v1.set_favorite(clip.id, True)
    v1.set_favorite(clip.id, False)
    v1.close()

    v2 = _vault(db)
    assert v2.storage.get_clip(clip.id).is_pinned is False
    v2.close()


def test_favorites_appear_above_normal(vault):
    a = vault.capture("first normal")
    b = vault.capture("second normal")
    fav = vault.capture("favorite me")
    vault.set_favorite(fav.id, True)
    listed = vault.list_clips(FILTER_ALL)
    assert listed[0].id == fav.id  # favorite floats to the top
    assert {c.id for c in listed[1:]} == {a.id, b.id}


def test_favorites_filter_shows_only_favorites(vault):
    vault.capture("normal")
    fav = vault.capture("fav")
    vault.set_favorite(fav.id, True)
    favs = vault.list_clips(FILTER_FAVORITES)
    assert [c.id for c in favs] == [fav.id]


def test_favorites_survive_sensitive_expiry(vault):
    fav = vault.capture("important favorite")
    vault.set_favorite(fav.id, True)
    vault.run_expiry_sweep()  # no expiry on this clip — should remain
    assert fav.id in {c.id for c in vault.list_clips(FILTER_FAVORITES)}


def test_remove_from_history_does_not_touch_disk(tmp_path, vault):
    real = tmp_path / "real_file.txt"
    real.write_text("important data", encoding="utf-8")
    clip = vault.capture(str(real), source_app="explorer.exe")
    vault.remove_from_history(clip.id)
    # The clip is gone from history...
    assert clip.id not in {c.id for c in vault.list_clips(FILTER_ALL)}
    # ...but the real file is untouched.
    assert os.path.exists(real)
    assert real.read_text(encoding="utf-8") == "important data"
