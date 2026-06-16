import os

from cache_vault.core.storage import FILTER_ALL, FILTER_RECENTLY_REMOVED


def test_removed_clip_goes_to_recently_removed(vault):
    clip = vault.capture("remove me")
    vault.remove_from_history(clip.id)
    assert clip.id not in {c.id for c in vault.list_clips(FILTER_ALL)}
    removed = vault.list_clips(FILTER_RECENTLY_REMOVED)
    assert clip.id in {c.id for c in removed}
    # Content is preserved so it can be restored.
    assert vault.storage.get_clip(clip.id).content == "remove me"


def test_restore_brings_clip_back(vault):
    clip = vault.capture("oops")
    vault.remove_from_history(clip.id)
    vault.restore(clip.id)
    assert clip.id in {c.id for c in vault.list_clips(FILTER_ALL)}
    assert clip.id not in {c.id for c in vault.list_clips(FILTER_RECENTLY_REMOVED)}


def test_permanently_remove_deletes_entry(vault):
    clip = vault.capture("gone for good")
    vault.remove_from_history(clip.id)
    vault.permanently_remove(clip.id)
    assert vault.storage.get_clip(clip.id) is None
    assert clip.id not in {c.id for c in vault.list_clips(FILTER_RECENTLY_REMOVED)}


def test_permanently_remove_does_not_touch_disk(tmp_path, vault):
    real = tmp_path / "keep.txt"
    real.write_text("data", encoding="utf-8")
    clip = vault.capture(str(real), source_app="explorer.exe")
    vault.remove_from_history(clip.id)
    vault.permanently_remove(clip.id)
    assert os.path.exists(real)  # real file untouched


def test_expired_clip_not_in_recently_removed(vault):
    # Sensitive auto-expiry is a different bucket (Expired), not Recently Removed.
    secret = vault.capture("sk-abc123DEF456ghi789JKL0")
    from cache_vault.core import sensitive
    vault.storage.set_expiry(secret.id, sensitive.compute_expiry(-1))
    vault.run_expiry_sweep()
    assert secret.id not in {c.id for c in vault.list_clips(FILTER_RECENTLY_REMOVED)}
