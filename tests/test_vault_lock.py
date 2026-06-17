from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.core import vault_lock


def test_lock_settings_persist_without_raw_secret(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    vault_lock.set_lock_secret(settings, "123456", mode=vault_lock.LOCK_MODE_PIN)
    settings.vault_lock_on_startup = True
    settings.vault_lock_when_minimized = True
    settings.vault_lock_auto_minutes = 5
    settings.save(path)

    raw = path.read_text(encoding="utf-8")
    assert "123456" not in raw
    assert "vault_lock_hash" in raw

    loaded = Settings.load(path)
    assert loaded.vault_lock_enabled is True
    assert loaded.vault_lock_mode == vault_lock.LOCK_MODE_PIN
    assert loaded.vault_lock_on_startup is True
    assert loaded.vault_lock_when_minimized is True
    assert loaded.vault_lock_auto_minutes == 5
    assert vault_lock.verify_secret(loaded, "123456") is True


def test_invalid_unlock_fails():
    settings = Settings()
    vault_lock.set_lock_secret(settings, "correct horse", mode=vault_lock.LOCK_MODE_PASSPHRASE)

    assert vault_lock.verify_secret(settings, "wrong horse") is False
    assert vault_lock.verify_secret(settings, "correct horse") is True


def test_lock_on_startup_requires_enabled_secret():
    settings = Settings(vault_lock_enabled=True, vault_lock_on_startup=True)
    assert vault_lock.should_lock_on_startup(settings) is False

    vault_lock.set_lock_secret(settings, "1234")
    settings.vault_lock_on_startup = True
    assert vault_lock.should_lock_on_startup(settings) is True


def test_lock_events_are_metadata_only():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    vault_lock.record_lock_event(
        vault.events,
        vault_lock.EVENT_VAULT_UNLOCK_FAILED,
        mode=vault_lock.LOCK_MODE_PIN,
        reason="invalid_unlock",
    )

    event = vault.events.recent(1)[0]
    assert event["event_type"] == vault_lock.EVENT_VAULT_UNLOCK_FAILED
    assert event["clip_id"] is None
    assert event["details"] == {
        "mode": vault_lock.LOCK_MODE_PIN,
        "reason": "invalid_unlock",
    }
    assert "credential" not in str(event["details"]).lower()
    vault.close()


def test_lock_settings_changed_summary_has_no_secret():
    settings = Settings()
    vault_lock.set_lock_secret(settings, "never-log-me")
    summary = vault_lock.safe_lock_settings_summary(settings)

    assert summary["enabled"] is True
    assert summary["has_secret"] is True
    assert "never-log-me" not in str(summary)
    assert "vault_lock_hash" not in str(summary)


def test_no_forbidden_lock_claims():
    ok = (
        "Vault Lock hides your visible app surface. "
        "Safes organize your items. They are not encryption unless encryption is added later."
    )
    assert vault_lock.no_forbidden_lock_claims(ok)
    assert not vault_lock.no_forbidden_lock_claims("encrypted Safes with cloud sync")
