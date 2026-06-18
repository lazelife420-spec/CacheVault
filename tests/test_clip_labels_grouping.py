from __future__ import annotations

from types import SimpleNamespace
from cache_vault.core import clip_metadata, grouping


def _clip(**kwargs):
    data = {
        "content_type": "image/png",
        "classification": "screenshot",
        "source_app": "Chrome.exe",
        "capture_mode": "snipping_tool",
        "created_at": "2026-06-18T09:48:12",
        "id": "a1b2c3d4e5",
        "is_pinned": False,
        "duplicate_of": None,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_labels_for_clip_basic():
    clip = _clip()
    labels = clip_metadata.labels_for_clip(clip)
    assert 'Screenshot' in labels
    assert 'Chrome' in labels or 'Browser' in labels


def test_time_buckets():
    c1 = _clip(created_at='2026-06-18T09:48:12')
    assert clip_metadata._time_bucket(c1.created_at) in ('Today','Yesterday','This Week','Older')


def test_group_by_date_and_source():
    c1 = _clip(created_at='2026-06-18T09:48:12', source_app='Chrome.exe', id='a')
    c2 = _clip(created_at='2026-06-17T08:00:00', source_app='SnippingTool.exe', id='b')
    groups = grouping.group_clips([c1,c2], 'date')
    assert any(k in ('Today','Yesterday','This Week','Older') for k in groups.keys())
    groups2 = grouping.group_clips([c1,c2], 'source')
    assert 'Chrome.exe' in groups2 or 'SnippingTool.exe' in groups2
