"""Windows mouse wheel scroll settings — read OS lines and normalize delta."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Callable

WHEEL_DELTA = 120
SPI_GETWHEELSCROLLLINES = 0x0068
SPI_GETWHEELSCROLLCHARS = 0x006C

# Default text/list line height when widget metrics are unavailable.
DEFAULT_LINE_PIXELS = 22


@dataclass(frozen=True)
class ScrollConfig:
    use_windows_settings: bool = True
    multiplier: float = 1.0
    line_pixels: int = DEFAULT_LINE_PIXELS


_config_supplier: Callable[[], ScrollConfig] = lambda: ScrollConfig()
_cached_lines: int | None = None
_cached_chars: int | None = None


def set_scroll_config_supplier(supplier: Callable[[], ScrollConfig]) -> None:
    global _config_supplier, _cached_lines, _cached_chars
    _config_supplier = supplier
    _cached_lines = None
    _cached_chars = None


def current_scroll_config() -> ScrollConfig:
    return _config_supplier()


def refresh_windows_scroll_cache() -> None:
    """Drop cached SPI values (call after settings change or OS setting change)."""
    global _cached_lines, _cached_chars
    _cached_lines = None
    _cached_chars = None


def _system_parameter_uint(param: int) -> int:
    value = ctypes.c_uint()
    if not ctypes.windll.user32.SystemParametersInfoW(param, 0, ctypes.byref(value), 0):
        return 3
    return int(value.value)


def get_wheel_scroll_lines() -> int:
    """Lines per wheel notch (SPI_GETWHEELSCROLLLINES). 0 = smooth pixel scroll."""
    global _cached_lines
    if sys.platform != "win32":
        return 3
    if _cached_lines is None:
        _cached_lines = _system_parameter_uint(SPI_GETWHEELSCROLLLINES)
    return _cached_lines


def get_wheel_scroll_chars() -> int:
    """Characters per horizontal wheel notch (Shift+wheel)."""
    global _cached_chars
    if sys.platform != "win32":
        return 3
    if _cached_chars is None:
        _cached_chars = _system_parameter_uint(SPI_GETWHEELSCROLLCHARS)
    return _cached_chars


def vertical_canvas_units(delta: int, *, line_pixels: int | None = None) -> int:
    """Signed scroll amount for canvas ``yview`` units (yscrollincrement=1 → pixels)."""
    cfg = _config_supplier()
    if not cfg.use_windows_settings or sys.platform != "win32":
        return -int(delta / 6)
    line_px = line_pixels or cfg.line_pixels
    mult = cfg.multiplier
    lines = get_wheel_scroll_lines()
    if lines == 0:
        return int(round(-delta * mult))
    notches = delta / float(WHEEL_DELTA)
    return int(round(-notches * lines * line_px * mult))


def horizontal_canvas_units(delta: int, *, char_pixels: int = 8) -> int:
    """Signed scroll amount for canvas ``xview`` units."""
    cfg = _config_supplier()
    if not cfg.use_windows_settings or sys.platform != "win32":
        return -int(delta / 6)
    mult = cfg.multiplier
    chars = get_wheel_scroll_chars()
    if chars == 0:
        return int(round(-delta * mult))
    notches = delta / float(WHEEL_DELTA)
    return int(round(-notches * chars * char_pixels * mult))


def vertical_text_units(delta: int) -> int:
    """Signed scroll amount for tkinter Text ``yview_scroll(..., 'units')`` (line units)."""
    cfg = _config_supplier()
    if not cfg.use_windows_settings or sys.platform != "win32":
        return int(-delta / 120) or (-1 if delta > 0 else 1)
    mult = cfg.multiplier
    lines = get_wheel_scroll_lines()
    if lines == 0:
        # Smooth scroll on Text: approximate with fractional lines from delta.
        return int(round(-(delta / float(WHEEL_DELTA)) * mult)) or (-1 if delta > 0 else 1)
    notches = delta / float(WHEEL_DELTA)
    units = int(round(-notches * lines * mult))
    return units or (-1 if delta > 0 else 1)


def horizontal_text_units(delta: int) -> int:
    cfg = _config_supplier()
    if not cfg.use_windows_settings or sys.platform != "win32":
        return int(-delta / 120) or (-1 if delta > 0 else 1)
    mult = cfg.multiplier
    chars = get_wheel_scroll_chars()
    if chars == 0:
        return int(round(-(delta / float(WHEEL_DELTA)) * mult)) or (-1 if delta > 0 else 1)
    notches = delta / float(WHEEL_DELTA)
    units = int(round(-notches * chars * mult))
    return units or (-1 if delta > 0 else 1)
