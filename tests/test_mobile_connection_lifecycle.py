from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cache_vault.core.mobile.models import (
    DEVICE_STATUS_OFFLINE,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_REVOKED,
    DEVICE_STATUS_WAITING_APPROVAL,
    PairedDevice,
    paired_device_status,
)


def _device(**overrides) -> PairedDevice:
    data = {
        "device_id": "pixel-1",
        "device_name": "Pixel",
        "created_at": "2026-07-01T00:00:00+00:00",
        "token_hash": "abc123",
        "last_seen_at": None,
        "revoked_at": None,
        "app_version": None,
        "platform": "android",
    }
    data.update(overrides)
    return PairedDevice(**data)


def test_paired_device_status_waiting_for_approval_without_last_seen():
    assert paired_device_status(_device()) == DEVICE_STATUS_WAITING_APPROVAL


def test_paired_device_status_online_for_recent_last_seen():
    now = datetime.now(timezone.utc)
    device = _device(last_seen_at=(now - timedelta(seconds=30)).isoformat())
    assert paired_device_status(device, online_window_seconds=120) == DEVICE_STATUS_ONLINE


def test_paired_device_status_offline_for_stale_last_seen():
    now = datetime.now(timezone.utc)
    device = _device(last_seen_at=(now - timedelta(minutes=8)).isoformat())
    assert paired_device_status(device, online_window_seconds=120) == DEVICE_STATUS_OFFLINE


def test_paired_device_status_revoked_wins_over_last_seen():
    now = datetime.now(timezone.utc)
    device = _device(
        last_seen_at=(now - timedelta(seconds=10)).isoformat(),
        revoked_at=now.isoformat(),
    )
    assert paired_device_status(device) == DEVICE_STATUS_REVOKED
