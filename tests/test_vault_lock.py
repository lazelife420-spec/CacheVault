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


def test_enabled_lock_starts_locked_even_when_legacy_startup_switch_is_off(tmp_path):
    settings = Settings()
    vault_lock.set_lock_secret(settings, "1234")
    settings.vault_lock_on_startup = False
    settings.save(tmp_path / "settings.json")

    loaded = Settings.load(tmp_path / "settings.json")
    assert loaded.vault_lock_on_startup is True
    assert vault_lock.should_lock_on_startup(loaded) is True
    assert vault_lock.lock_state(loaded) == vault_lock.VaultLockState.LOCKED
    assert vault_lock.lock_state(loaded, unlocked=True) == vault_lock.VaultLockState.UNLOCKED


def test_runtime_locked_state_is_not_overridden_by_disabled_configuration():
    settings = Settings()
    assert vault_lock.get_vault_lock_state(settings) == vault_lock.VaultLockState.DISABLED
    assert vault_lock.get_vault_lock_state(
        settings, runtime_locked=True,
    ) == vault_lock.VaultLockState.LOCKED


def test_enabled_lock_with_missing_or_corrupt_verifier_fails_closed():
    settings = Settings(vault_lock_enabled=True)
    assert vault_lock.lock_config(settings).enabled is True
    assert vault_lock.lock_state(settings) == vault_lock.VaultLockState.LOCKED
    assert vault_lock.lock_state(settings, unlocked=True) == vault_lock.VaultLockState.LOCKED
    assert vault_lock.should_lock_on_startup(settings) is True
    assert vault_lock.verify_secret(settings, "123456", now_ms=1_000) is False

    vault_lock.set_lock_secret(settings, "correct horse")
    settings.vault_lock_salt = "broken"
    assert vault_lock.has_lock_secret(settings) is False
    assert vault_lock.verify_secret(settings, "correct horse", now_ms=2_000) is False


def test_failed_unlock_backoff_matches_android_schedule_and_resets_on_success():
    settings = Settings()
    vault_lock.set_lock_secret(settings, "correct horse")
    for index in range(4):
        assert vault_lock.verify_secret(settings, "wrong", now_ms=1_000 + index) is False
        assert vault_lock.unlock_wait_remaining_ms(settings, now_ms=1_000 + index) == 0

    assert vault_lock.verify_secret(settings, "wrong", now_ms=2_000) is False
    assert vault_lock.unlock_wait_remaining_ms(settings, now_ms=2_000) == 30_000
    assert vault_lock.verify_secret(settings, "correct horse", now_ms=2_100) is False
    assert settings.vault_lock_failures == 5

    for index in range(7):
        assert vault_lock.verify_secret(
            settings, "wrong", now_ms=1_000_000 + index * 600_000,
        ) is False
    assert settings.vault_lock_failures == 12
    last_attempt_at = 1_000_000 + 6 * 600_000
    assert vault_lock.unlock_wait_remaining_ms(settings, now_ms=last_attempt_at) == 120_000
    assert vault_lock.verify_secret(
        settings, "correct horse", now_ms=last_attempt_at + 120_000,
    ) is True
    assert settings.vault_lock_failures == 0
    assert settings.vault_lock_locked_until_ms == 0


def test_failed_unlock_backoff_survives_settings_reload(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    vault_lock.set_lock_secret(settings, "correct horse")
    for index in range(5):
        vault_lock.verify_secret(settings, "wrong", now_ms=1_000 + index)
    settings.save(path)

    loaded = Settings.load(path)
    assert loaded.vault_lock_failures == 5
    assert vault_lock.unlock_wait_remaining_ms(loaded, now_ms=1_005) == 29_999
    assert vault_lock.verify_secret(loaded, "correct horse", now_ms=2_000) is False
    assert loaded.vault_lock_failures == 5


def test_lock_events_are_metadata_only():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    vault_lock.record_lock_event(
        vault.events,
        vault_lock.EVENT_VAULT_UNLOCK_FAILED,
        mode=vault_lock.LOCK_MODE_PIN,
        reason="invalid_credential",
        method="credential",
    )

    event = vault.events.recent(1)[0]
    assert event["event_type"] == vault_lock.EVENT_VAULT_UNLOCK_FAILED
    assert event["clip_id"] is None
    assert event["details"] == {
        "canonical_event": "vault.unlock_failed",
        "platform": "windows",
        "mode": vault_lock.LOCK_MODE_PIN,
        "reason": "invalid_credential",
        "method": "credential",
    }
    assert "123456" not in str(event["details"])
    vault.close()


def test_all_windows_storage_events_expose_the_contract_event_names():
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    expected = {
        vault_lock.EVENT_VAULT_LOCKED: "vault.locked",
        vault_lock.EVENT_VAULT_UNLOCKED: "vault.unlocked",
        vault_lock.EVENT_VAULT_UNLOCK_FAILED: "vault.unlock_failed",
        vault_lock.EVENT_VAULT_LOCK_SETTINGS_CHANGED: "vault.lock_settings_changed",
    }
    for stored_name, canonical_name in expected.items():
        vault_lock.record_lock_event(vault.events, stored_name, mode="pin")
    recent = vault.events.recent(len(expected))
    assert {event["event_type"]: event["details"]["canonical_event"] for event in recent} == expected
    assert all(event["details"]["platform"] == "windows" for event in recent)
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
