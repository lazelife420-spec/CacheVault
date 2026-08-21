"""Canonical image fingerprint tests for clipboard custody.

The Windows CF_DIB path discards alpha and normalizes pixel data, so the
source PNG encoding and the captured PNG bytes can differ. These tests prove
that the shared :func:`cache_vault.core.image_assets.canonical_image_fingerprint`
produces matching writer and monitor hashes regardless of encoding.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image

import cache_vault.core.clipboard as clipmod
from cache_vault.core import image_assets, models
from cache_vault.core.clipboard import ClipboardMonitor
from cache_vault.core.clipboard_custody import (
    DEFAULT_FALLBACK_TTL_S,
    EVENT_FALLBACK_LATENCY_S,
    EVENT_FALLBACK_MARGIN_S,
    ClipboardWriteSuppressor,
    ClipboardWriter,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _make_png(mode: str = "RGB", size: tuple[int, int] = (8, 8), color=None) -> bytes:
    if color is None:
        color = (255, 0, 0) if mode in ("RGB", "RGBA") else 255
    img = Image.new(mode, size, color)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _reencode(png_bytes: bytes, **params) -> bytes:
    with Image.open(io.BytesIO(png_bytes)) as img:
        out = io.BytesIO()
        img.save(out, "PNG", **params)
        return out.getvalue()


def test_two_differently_encoded_pngs_with_identical_pixels():
    png1 = _make_png()
    png2 = _reencode(png1, compress_level=9, optimize=True)
    assert png1 != png2
    fp1 = image_assets.canonical_image_fingerprint(png1)
    fp2 = image_assets.canonical_image_fingerprint(png2)
    assert fp1 and fp2
    assert fp1 == fp2


def test_different_pixels_with_equal_dimensions_differ():
    red = _make_png(color=(255, 0, 0))
    green = _make_png(color=(0, 255, 0))
    fp1 = image_assets.canonical_image_fingerprint(red)
    fp2 = image_assets.canonical_image_fingerprint(green)
    assert fp1 and fp2
    assert fp1 != fp2


def test_source_png_matches_dib_roundtrip():
    png = _make_png()
    dib = image_assets.png_to_dib(png)
    captured, _w, _h = image_assets.dib_to_png(dib)
    assert image_assets.canonical_image_fingerprint(png) == image_assets.canonical_image_fingerprint(captured)


def test_translucent_rgba_and_opaque_captured_follow_cf_dib():
    """Alpha is discarded by CF_DIB; the RGB values are preserved."""
    img = Image.new("RGBA", (4, 4), (128, 64, 32, 128))
    out = io.BytesIO()
    img.save(out, "PNG")
    png = out.getvalue()

    dib = image_assets.png_to_dib(png)
    captured, _w, _h = image_assets.dib_to_png(dib)
    fp_source = image_assets.canonical_image_fingerprint(png)
    fp_captured = image_assets.canonical_image_fingerprint(captured)
    assert fp_source and fp_captured
    assert fp_source == fp_captured


def test_text_and_image_fingerprints_cannot_cross_match():
    text = "hello"
    png = _make_png()
    s = ClipboardWriteSuppressor()
    token = s.begin(
        operation="op",
        content_type=models.CONTENT_IMAGE,
        fingerprint=image_assets.canonical_image_fingerprint(png),
    )
    s.commit(token, sequence=1)
    assert s.should_suppress(content_type=models.CONTENT_TEXT, fingerprint=text, sequence=1) is False
    assert (
        s.should_suppress(
            content_type=models.CONTENT_IMAGE,
            fingerprint=image_assets.canonical_image_fingerprint(png),
            sequence=1,
        )
        is True
    )


class FakeImageClipboard:
    """Stand-in for the Windows clipboard when exercising image custody."""

    def __init__(self, get_sequence=None) -> None:
        self.captured: tuple[bytes, int, int] | None = None
        self.seq: int | None = None
        self._get_sequence = get_sequence

    def write_image(self, png: bytes) -> bool:
        if self._get_sequence is not None:
            self.seq = self._get_sequence()
        dib = image_assets.png_to_dib(png)
        self.captured = image_assets.dib_to_png(dib)
        return True

    def read_image(self) -> tuple[bytes, int, int] | None:
        return self.captured

    def current_sequence(self) -> int | None:
        return self.seq


def _image_monitor_fixture(monkeypatch, get_sequence=None, clock=None):
    fake = FakeImageClipboard(get_sequence=get_sequence)
    monkeypatch.setattr(clipmod, "_read_clipboard_image", fake.read_image)
    monkeypatch.setattr(
        clipmod,
        "_foreground_source",
        lambda: {"source_app": "python.exe", "source_window": "external"},
    )
    suppressor = ClipboardWriteSuppressor(clock=clock or FakeClock())
    captures: list[dict] = []
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=fake.current_sequence,
    )
    monitor._running = True
    writer = ClipboardWriter(
        suppressor,
        set_image=fake.write_image,
        get_sequence=fake.current_sequence,
    )
    return SimpleNamespace(
        fake=fake,
        suppressor=suppressor,
        monitor=monitor,
        writer=writer,
        captures=captures,
    )


def test_no_sequence_image_self_write_suppresses(monkeypatch):
    h = _image_monitor_fixture(monkeypatch, get_sequence=None)
    png = _make_png()

    assert h.writer.write_image(png, operation="copy_image") is True
    h.monitor._emit()
    assert h.captures == []

    clock = h.suppressor._clock
    clock.advance(DEFAULT_FALLBACK_TTL_S + 0.01)
    # Simulate an external application putting a different image on the clipboard.
    different_png = _make_png(color=(0, 0, 255))
    h.fake.captured = image_assets.dib_to_png(image_assets.png_to_dib(different_png))
    h.monitor._emit()
    assert len(h.captures) == 1


def test_later_genuine_image_copy_with_sequence_is_capturable(monkeypatch):
    seq_counter = [0]

    def next_seq():
        seq_counter[0] += 1
        return seq_counter[0]

    h = _image_monitor_fixture(monkeypatch, get_sequence=next_seq)
    png = _make_png()

    assert h.writer.write_image(png, operation="copy_image") is True
    h.monitor._emit()
    assert h.captures == []
    assert len(h.suppressor) == 0

    # A later identical image copy gets a new sequence and is captured.
    h.fake.captured = image_assets.dib_to_png(image_assets.png_to_dib(png))
    h.fake.seq = next_seq()
    h.suppressor._clock.advance(0.1)
    h.monitor._emit()
    assert len(h.captures) == 1
    assert h.captures[0].get("clipboard_sequence") == 2


def test_runtime_event_listener_fallback_resizes_custody_window(monkeypatch):
    """A failed Win32 listener must use the polling fallback lifetime."""
    monkeypatch.setattr(clipmod, "_HAS_WIN32", True)
    monkeypatch.setattr(clipmod, "_read_clipboard_text", lambda: None)
    suppressor = ClipboardWriteSuppressor()
    monitor = ClipboardMonitor(lambda _payload: None, suppressor=suppressor)

    assert suppressor._fallback_ttl == (
        EVENT_FALLBACK_LATENCY_S + EVENT_FALLBACK_MARGIN_S
    )
    monitor._running = False
    monitor._run_poll_loop()
    assert suppressor._fallback_ttl == DEFAULT_FALLBACK_TTL_S
