from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import tempfile

from cache_vault.core import image_assets


def _clip(**kwargs):
    data = {
        "content_type": "image/png",
        "classification": "screenshot",
        "source_app": "Chrome.exe",
        "capture_mode": "snipping_tool",
        "created_at": "2026-06-18T09:48:12",
        "id": "a1b2c3d4e5",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_make_smart_filename_basic():
    clip = _clip()
    name = image_assets.make_smart_filename(clip)
    assert name.endswith('.png')
    assert 'cachevault' in name.lower()
    assert 'chrome' in name.lower()
    assert '2026-06-18' in name


def test_make_smart_filename_missing_metadata():
    clip = _clip(source_app=None, created_at=None, id=None)
    name = image_assets.make_smart_filename(clip)
    # Missing some metadata should still produce a valid-looking filename.
    assert name.endswith('.png')
    assert 'cachevault' in name.lower()


def test_next_available_path_collision(tmp_path):
    p = tmp_path / 'CacheVault_screenshot_test_2026-06-18_094812_abcd12.png'
    p.write_bytes(b'1')
    p2 = image_assets.next_available_path(p)
    assert p2 != p
    p2.write_bytes(b'2')
    p3 = image_assets.next_available_path(p)
    assert p3 != p and p3 != p2
