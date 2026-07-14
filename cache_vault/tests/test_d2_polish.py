"""Focused tests for D2 Image/Grid polish formatting and metadata logic."""

import pytest
from datetime import datetime, timedelta, timezone
from cache_vault.core import clip_metadata, models

def test_human_timestamp_today():
    now = datetime.now(timezone.utc)
    iso = now.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Today ·" in result
    assert now.strftime("%I:%M %p").lstrip("0") in result

def test_human_timestamp_yesterday():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    iso = yesterday.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Yesterday ·" in result
    assert yesterday.strftime("%I:%M %p").lstrip("0") in result

def test_human_timestamp_older_this_year():
    # Fixed date earlier this year (assuming today is Jun 28, 2026)
    dt = datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc)
    iso = dt.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Jun 01 · 10:30 AM" in result

def test_human_timestamp_previous_year():
    dt = datetime(2025, 12, 12, 9, 0, tzinfo=timezone.utc)
    iso = dt.isoformat()
    result = clip_metadata.human_timestamp(iso)
    assert "Dec 12, 2025 · 9:00 AM" in result

def test_date_group_header_today():
    iso = datetime.now(timezone.utc).isoformat()
    assert clip_metadata.date_group_header(iso) == "Today"

def test_date_group_header_yesterday():
    iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert clip_metadata.date_group_header(iso) == "Yesterday"

def test_status_badges_logic():
    class MockClip:
        def __init__(self, id, capture_mode, content_hash):
            self.id = id
            self.capture_mode = capture_mode
            self.content_hash = content_hash

    class MockStorage:
        def has_clip_asset(self, clip_id):
            return clip_id == "has_asset"

    storage = MockStorage()
    
    # On PC badge
    clip1 = MockClip("has_asset", models.CAPTURE_AUTO, "hash1")
    badges1 = clip_metadata.status_badges(clip1, storage)
    assert "On PC" in badges1
    assert "Proof Recorded" in badges1
    assert "From Phone" not in badges1

    # From Phone badge
    clip2 = MockClip("no_asset", models.CAPTURE_MOBILE_SHARE, "hash2")
    badges2 = clip_metadata.status_badges(clip2, storage)
    assert "From Phone" in badges2
    assert "Proof Recorded" in badges2
    assert "On PC" not in badges2

    # No fake Saved to Phone badge
    assert "Saved to Phone" not in badges2

def test_empty_list_state_logic():
    # clip_grid.render already handles empty list without crashing
    # This test just ensures the metadata helper doesn't crash on empty input
    assert clip_metadata.human_timestamp("") == "—"
    assert clip_metadata.date_group_header("") == "Older"
