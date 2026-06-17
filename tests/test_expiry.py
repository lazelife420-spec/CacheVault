from cache_vault.core import models, sensitive
from cache_vault.core.storage import FILTER_EXPIRED, FILTER_SENSITIVE


def test_sensitive_clip_is_masked_and_gets_expiry(vault):
    vault.settings.block_sensitive_auto_capture = False
    clip = vault.capture("sk-abc123DEF456ghi789JKL0")
    assert clip is not None
    assert clip.is_sensitive
    # The stored preview must not contain the secret.
    assert "abc123" not in clip.preview
    # Expiry is ON by default → a future expires_at was set.
    assert clip.expires_at is not None


def test_expiry_scrubs_content_and_logs_without_secret(vault):
    vault.settings.block_sensitive_auto_capture = False
    secret = "sk-abc123DEF456ghi789JKL0"
    clip = vault.capture(secret)
    # Force expiry into the past, then sweep.
    past = sensitive.compute_expiry(-1)  # 1 minute ago
    vault.storage.set_expiry(clip.id, past)
    n = vault.run_expiry_sweep()
    assert n == 1

    scrubbed = vault.storage.get_clip(clip.id)
    assert scrubbed.content == ""          # secret is gone
    assert scrubbed.deleted_at is not None

    # It now appears under Expired, not under live Sensitive.
    assert vault.list_clips(FILTER_SENSITIVE) == []
    expired = vault.list_clips(FILTER_EXPIRED)
    assert [c.id for c in expired] == [clip.id]

    # The event log recorded the expiry but never the secret.
    events = vault.events.recent()
    types = [e["event_type"] for e in events]
    assert models.EVENT_EXPIRED in types
    blob = str(events)
    assert secret not in blob
    assert "abc123" not in blob


def test_manual_expire_now(vault):
    clip = vault.capture("https://example.com/keep-or-not")
    vault.expire_now(clip.id)
    assert vault.storage.get_clip(clip.id).content == ""


def test_clear_sensitive_removes_all_live_secrets(vault):
    vault.settings.block_sensitive_auto_capture = False
    vault.capture("sk-aaa111BBB222ccc333DDD4")
    vault.capture("plain harmless text")
    vault.capture("password=supersecretvalue")
    cleared = vault.clear_sensitive()
    assert cleared == 2
    assert vault.list_clips(FILTER_SENSITIVE) == []


def test_capture_paused_blocks(vault):
    vault.settings.capture_paused = True
    assert vault.capture("anything") is None


def test_consecutive_duplicate_not_recaptured(vault):
    a = vault.capture("repeat me")
    b = vault.capture("repeat me")
    assert a is not None
    assert b is None  # consecutive identical copy ignored


def test_excluded_app_not_captured(vault):
    vault.settings.excluded_apps = ["KeePass.exe"]
    assert vault.capture("secret from pw manager", source_app="KeePass.exe") is None
