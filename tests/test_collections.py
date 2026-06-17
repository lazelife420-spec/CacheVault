from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage, COLLECTION_PREFIX, FILTER_ALL
from cache_vault.core.vault import Vault


def _vault(path):
    return Vault(storage=VaultStorage(path), settings=Settings())


def test_move_clip_into_collection(vault):
    clip = vault.capture("work note")
    vault.set_collection(clip.id, "Work")
    assert vault.storage.get_clip(clip.id).collection == "Work"
    listed = vault.list_clips(COLLECTION_PREFIX + "Work")
    assert [c.id for c in listed] == [clip.id]


def test_collection_persists_after_restart(tmp_path):
    db = tmp_path / "v.db"
    v1 = _vault(db)
    clip = v1.capture("snippet")
    v1.set_collection(clip.id, "Code")
    v1.close()

    v2 = _vault(db)
    assert v2.storage.get_clip(clip.id).collection == "Code"
    cols = {c["name"]: c["count"] for c in v2.list_collections()}
    assert cols.get("Code") == 1
    v2.close()


def test_list_collections_counts(vault):
    a = vault.capture("a"); b = vault.capture("b"); c = vault.capture("c")
    vault.set_collection(a.id, "Links")
    vault.set_collection(b.id, "Links")
    vault.set_collection(c.id, "Notes")
    cols = {x["name"]: x["count"] for x in vault.list_collections()}
    assert cols == {"Links": 2, "Notes": 1}


def test_remove_from_collection(vault):
    clip = vault.capture("x")
    vault.set_collection(clip.id, "Work")
    vault.set_collection(clip.id, None)
    assert vault.storage.get_clip(clip.id).collection is None
    assert vault.list_collections() == []
