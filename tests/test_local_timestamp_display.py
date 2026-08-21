"""Timestamps are stored in UTC and displayed in local time.

Regression guard for the defect where a stored UTC value was formatted without
conversion, so the UI printed UTC clock digits as though they were local (for
example showing "6:42 PM" for an item captured at 11:42 AM local).

Every expected clock string is derived with ``astimezone()`` instead of being
hard-coded, so these tests are valid in any host timezone, including UTC.
"""

from datetime import datetime, timedelta, timezone

from cache_vault.core import clip_metadata, models

STORED_UTC = datetime(2026, 8, 14, 18, 42, 23, tzinfo=timezone.utc)


def _clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


# --- storage side: must remain UTC ------------------------------------------


def test_storage_timestamps_remain_utc():
    parsed = datetime.fromisoformat(models.now_iso())
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


# --- conversion helper ------------------------------------------------------


def test_to_local_preserves_the_absolute_instant():
    local = clip_metadata.to_local(STORED_UTC)
    assert local == STORED_UTC


def test_to_local_adopts_the_host_offset():
    local = clip_metadata.to_local(STORED_UTC)
    assert local.utcoffset() == STORED_UTC.astimezone().utcoffset()
    assert _clock(local) == _clock(STORED_UTC.astimezone())


def test_to_local_is_idempotent():
    once = clip_metadata.to_local(STORED_UTC)
    twice = clip_metadata.to_local(once)
    assert once.isoformat() == twice.isoformat()
    assert once == twice


def test_to_local_leaves_naive_values_untouched():
    naive = datetime(2026, 8, 14, 11, 42, 23)
    result = clip_metadata.to_local(naive)
    assert result == naive
    assert result.tzinfo is None


# --- display side -----------------------------------------------------------


def test_human_timestamp_renders_local_clock_not_utc_digits():
    shown = clip_metadata.human_timestamp(STORED_UTC.isoformat())
    local = STORED_UTC.astimezone()
    assert _clock(local) in shown
    if local.utcoffset() != timedelta(0):
        assert _clock(STORED_UTC) not in shown


def test_format_captured_at_renders_local_clock():
    stored = datetime.now(timezone.utc)
    shown = clip_metadata.format_captured_at(stored.isoformat())
    assert _clock(stored.astimezone()) in shown


def test_stored_non_utc_offset_is_still_converted_to_host_local():
    stored = datetime(2026, 8, 14, 23, 42, tzinfo=timezone(timedelta(hours=5)))
    shown = clip_metadata.human_timestamp(stored.isoformat())
    assert _clock(stored.astimezone()) in shown


def test_date_group_header_buckets_by_local_day():
    assert clip_metadata.date_group_header(datetime.now(timezone.utc).isoformat()) == "Today"


# --- relative helpers are delta-based and must stay timezone-independent ----


def test_relative_age_is_unaffected_by_conversion():
    three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    assert clip_metadata.relative_age(three_hours_ago.isoformat()) == "3 hrs ago"
