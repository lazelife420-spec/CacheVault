"""Focused tests for D2 image/grid polish formatting and metadata logic."""

from datetime import datetime, timedelta, timezone

from cache_vault.core import clip_metadata, models


# Timestamps are stored in UTC and rendered in local time, so every expected
# clock string below is derived via astimezone() rather than hard-coded. These
# assertions therefore hold in any host timezone, including UTC.


def test_human_timestamp_today():
    now = datetime.now(timezone.utc)
    iso = now.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Today ·" in result
    assert now.astimezone().strftime("%I:%M %p").lstrip("0") in result


def test_human_timestamp_yesterday():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    iso = yesterday.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Yesterday ·" in result
    assert yesterday.astimezone().strftime("%I:%M %p").lstrip("0") in result


def test_human_timestamp_older_this_year():
    dt = datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc)
    local = dt.astimezone()
    result = clip_metadata.human_timestamp(dt.isoformat())
    expected = f"{local.strftime('%b %d')} · {local.strftime('%I:%M %p').lstrip('0')}"
    assert expected in result


def test_human_timestamp_previous_year():
    dt = datetime(2025, 12, 12, 9, 0, tzinfo=timezone.utc)
    local = dt.astimezone()
    result = clip_metadata.human_timestamp(dt.isoformat())
    expected = (
        f"{local.strftime('%b %d, %Y')} · {local.strftime('%I:%M %p').lstrip('0')}"
    )
    assert expected in result


def test_date_group_header_today():
    iso = datetime.now(timezone.utc).isoformat()
    assert clip_metadata.date_group_header(iso) == "Today"


def test_date_group_header_yesterday():
    iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert clip_metadata.date_group_header(iso) == "Yesterday"


def test_status_badges_logic():
    class MockClip:
        def __init__(self, clip_id, capture_mode, content_hash):
            self.id = clip_id
            self.capture_mode = capture_mode
            self.content_hash = content_hash
            self.is_saved_to_phone = False

    class MockStorage:
        def has_clip_asset(self, clip_id):
            return clip_id == "has_asset"

    storage = MockStorage()

    clip1 = MockClip("has_asset", models.CAPTURE_AUTO, "hash1")
    badges1 = clip_metadata.status_badges(clip1, storage)
    assert "On PC" in badges1
    assert "Proof Recorded" in badges1
    assert "From Phone" not in badges1

    clip2 = MockClip("no_asset", models.CAPTURE_MOBILE_SHARE, "hash2")
    badges2 = clip_metadata.status_badges(clip2, storage)
    assert "From Phone" in badges2
    assert "Proof Recorded" in badges2
    assert "On PC" not in badges2
    assert "Saved to Phone" not in badges2


def test_empty_list_state_logic():
    assert clip_metadata.human_timestamp("") == "—"
    assert clip_metadata.date_group_header("") == "Older"
